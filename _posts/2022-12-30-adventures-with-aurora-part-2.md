---
layout: single
title: "Adventures with Aurora (Part 2)"
date: 2022-12-30
last_modified_at: 2023-01-08
toc: true
mathjax: true
---

When we left off, we had two failed attempts at resolving Aurora MySQL I/O issues by tuning database parameters. We also managed to stumble on a 10-year-old deadlock bug in MySQL 5.6. Rather than continuing to explore risky database-level changes, we turned our attention to the application.

## On-Disk Structures

In the previous part, we discussed one type of on-disk structure known as the binary log. However, there are two other types of MySQL disk-based data structures that are relevant for our discussion.

### Redo Log

The [redo log](https://dev.mysql.com/doc/refman/5.6/en/innodb-redo-log.html) is used during crash recovery to restore data. We often refer to redo log records as log entries and will use them interchangeably. Log entries must be written to disk before a transaction can be committed. The reason is that in-memory changes are not flushed immediately. After a crash, MySQL will need to replay events in the redo log to restore the database to a consistent state. For a more detailed look at the redo log, see this [post](https://www.alibabacloud.com/blog/an-in-depth-analysis-of-redo-logs-in-innodb_598965).

In Aurora, log entries are sent directly to the storage layer, which is responsible for computing changes to pages. However, the redo log is still necessary because those changes are not directly flushed for performance reasons similar to vanilla MySQL.

### Undo Log

The [undo log](https://dev.mysql.com/doc/refman/5.6/en/innodb-undo-logs.html) is also used during crash recovery to revert the changes of uncommitted transactions. However, it also serves another important purpose: multiversion concurrency control (MVCC). MVCC is an involved topic, but we only need an intuition of how it works for this part. Consider two interleaved transactions $$T_0$$ and $$T_1$$.

```sql
/* T0 */ BEGIN;
/* T0 */ SELECT a FROM t;
/* T1 */ BEGIN;
/* T1 */ UPDATE t SET a = a + 1;
/* T1 */ COMMIT;
/* T0 */ SELECT a FROM t;
/* T0 */ COMMIT;
```

Depending on the [isolation level](https://dev.mysql.com/doc/refman/5.6/en/innodb-transaction-isolation-levels.html), $$T_0$$ might not want to see the new value of `a` written by $$T_1$$. This is the case with the default isolation level of MySQL, which is `REPEATABLE READ`. Ideally, $$T_0$$ wants a snapshot of the database from the moment it performs its first read. However, that is too expensive to implement directly. MySQL instead uses the undo log to achieve repeatable reads.

At a high level, each transaction writes out undo log records for clustered index records that it modifies. The undo log records specify how to revert the changes made by the transaction. When another transaction reads a row, it is able to repeatedly apply undo log records for that row until it reaches a point in time that is consistent with when the transaction started. For more details on the undo log and MVCC, see this [post](https://www.alibabacloud.com/blog/an-in-depth-analysis-of-undo-logs-in-innodb_598966).

The undo log is a separate on-disk data structure from the redo log. However (and this is confusing), the redo log contains record types that are used to manipulate the undo log. For example, `MLOG_UNDO_INIT` initializes a page in an undo log. This means that when a transaction commits, the redo log will also contain log entries for changes to undo log pages. For a complete list of the different types of log entries, refer to the [code](https://github.com/mysql/mysql-server/blob/91773b1f65de78924e0cd2b30009d44f64f9dee9/storage/innobase/include/mtr0mtr.h). 

## Commit Bottleneck

We knew both from application metrics and performance insights that transactions were waiting at the commit step. Breaking down the individual operations provided some insight into how we can optimize our query pattern to reduce bottlenecks.

Around half of the wait time was due to `MYSQL_BIN_LOG::COND_wait`. This is from followers waiting for the leader to complete binary log group commit. We did consider disabling binary logging entirely, but realized that we will need it to perform a database upgrade at a later date. The other half of the wait time was due to `redo_log_flush`. This is from transactions waiting for log entries to be written to storage.

From these observations, we had an idea. What if we could reduce the number of transactions without changing the behavior of the application? Each transaction introduces some I/O overhead, and reducing that overhead would mean reducing overall I/O pressure.

## Application Group Commit

We developed an abstraction similar to MySQL's binary log group commit to test our idea. However, it operated at the application layer instead of the database layer, which enabled better observability and more granular control of individual transactions. Note that we will refer to this new abstraction as group commit (not to be confused with various other abstractions with the same name at the database or storage layers).

### Overview

The core idea of group commit is that concurrent transactions can be batched together to improve performance. Consider two transactions $$T_0$$ and $$T_1$$ that run concurrently. Assume that $$T_0$$ starts slightly before $$T_1$$. Normally, this would require two transactions and two database connections. However, group commit makes it possible to use only one transaction by having the operations of $$T_1$$ run inside of the existing transaction started by $$T_0$$. This has the added benefit of reducing the number of required database connections. 

```sql
/* T0 */ BEGIN;
/* T0 */ T0_OPERATIONS();
/* T0 */ T1_OPERATIONS();
/* T0 */ COMMIT;
```

In this example, $$T_0$$ and $$T_1$$ are in a group. We consider $$T_0$$ to be the leader and $$T_1$$ to be a follower. The leader performs all the operations of its group in the transaction while a follower waits for results from its leader. We describe the happy path of group commit.

1. The leader is assigned when a transaction runs and there is no existing open group.
2. The leader opens a new group and starts a transaction.
3. The leader immediately runs its own operations within the transaction.
4. The leader waits for followers to join the group. The leader closes the group (stops allowing more followers to join) when it is full or when a timeout is reached.
5. The leader serially executes the operations of followers within the transaction as they arrive.
6. When the group is closed, the leader commits the transaction and reports the status to the followers.

The maximum group size and group timeout should be set based on the throughput of transactions and the workload's tolerance for latency increase. Let $$g_t$$ be the group timeout and $$t$$ be the average throughput of a transaction that we want to apply group commit to. We can constrain $$g_s$$, the group size, as $$g_s g_t \leq t$$. Larger group sizes are not useful since those groups will not be filled (and cause non-productive latency increases).

Group commit preserves the existing isolation level because it treats operations of individual transactions as atomic units and executes them serially within the larger transaction. During a group commit transaction, it is possible for later operations to see changes from earlier operations that would not have been possible in the concurrent scenario. However, this is okay because the concurrent nature of these transactions means that a serial ordering is also acceptable.

There are a few additional subtleties to consider in handling commit failures and application errors that could arise during a leader's processing of its group. However, these are somewhat dependent on the database interface and the language. We describe them in more detail below.

### Discussion

We implemented the initial version of group commit in Go, although this technique is generalizable to other programming languages. Consider the simplified database interface below.

```go
// Database is used to interact with an underlying database.
type Database interface {
	// WithTx runs a user-defined function within a transaction. If the function
	// returns without error, the transaction is committed. Otherwise, the
	// transaction is rolled back. Transient errors may be retried and cause the
	// function to be invoked multiple times. 
	WithTx(ctx context.Context, fn func(ctx context.Context, tx *sql.Tx) error);
}
```

In our case, `WithTx` was used throughout the application to run transactions against the database. Nothing else was known about `fn` values aside from what was specified by the interface. Surprisingly, the group commit handler can actually be a drop in replacement for `Database`. Therefore, very little code changes were necessary outside of implementing the handler.

```go
// WithTx batches operations from multiple calls into a single transaction.
type (g *GroupCommitHandler) WithTx(
	ctx context.Context, 
	fn func(ctx context.Context, tx *sql.Tx),
) error {
	// [snip]
}

// NewGroupCommitHandler creates a group commit handler from a underlying
// database.
func NewGroupCommitHandler(db Database, /*...*/) Database {
	return &GroupCommitHandler{
		// [snip]
	}
}
```

#### Extensions

We also implemented a few extensions on top of basic group commit. This was mostly for ensuring production readiness.

Our database driver automatically retried certain classes of transient errors. This was very useful for increasing reliability, but it meant that group commit also had to take this into account. We just needed to make sure that the leader tracked all operations it had seen while executing the transaction so that they could be replayed if the transaction was retried.

There are cases where an operation would fail due to a non-transient error (e.g., unexpected or inconsistent state). In the non-batched world, only one transaction would fail. However, using group commit meant that all transactions in the group would fail. This was not acceptable since group commit should not reduce the success rate of transactions. To handle this, we added a fallback mechanism where each operation would be retried in its own transaction if the group commit transaction failed.

In Go, it is important to respect the context. This is a bit tricky for group commit since there are two contexts at the time that an operation runs: the context from the leader and the context from the follower that submitted the operation. We chose to mainly rely on the leader's context, but still respect context cancellations from the follower. A better approach might be to properly merge the contexts (see [proposal](https://github.com/golang/go/issues/36503)).

Lastly, we implemented dynamic maximum group sizes and timeouts. This allowed us to tune group commit parameters without redeploying the service. Groups were started very frequently, so it was only necessary to apply parameter changes to new groups.

#### Trade-offs

Group commit represents a trade-off between latency and throughput. The operation associated with the leader will have the highest latency increase since it must wait for followers and perform their operations as well before committing. This was acceptable for our use case since a majority of the database load was coming from background tasks that were not latency sensitive.

Group commit is more effective for vertically scaled applications that require high commit throughput. Transactions can only be batched within a single process and not across replicas. This is similar to the trade-off that database connection pooling makes since connections cannot be reused across replicas unless there is an intermediate connection pooling service. Our use case specifically targeted a singleton service that generated most of the database load.

### Results

From load testing using a simulated workload, we observed that group commit was able to increase the commit throughput by over 50% with a group size of 5. Although commit throughput did increase with larger group sizes, there were diminishing returns compared to the increase in latency needed to fill these larger groups.

After we enabled group commit in production, we immediately saw a decrease in database load. The main metric we used was [average active sessions](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PerfInsights.Overview.ActiveSessions.html) (AAS). The 1-day average AAS dropped by around 50% when we applied group commit to the two highest throughput transactions, which accounted for around 80% of the total transaction throughput.

This was a very exciting moment for us since we had resolved our I/O bottleneck issue. Application metrics were also looking significantly better than before (lower commit latency, lower database connections, etc.). We thought the database was finally in a stable state and would give us a break, but Aurora had other plans.

## Latency Spikes

About a week after we enabled group commit, we noticed a concerning pattern. Slightly after midnight UTC every day, there would be a brief latency spike in all transactions that lasted less than a minute. It wasn't enough to trigger any alerts or cause service disruption, but it was concerning since it didn't happen before group commit was enabled.

We suspected that some daily job was behind this (due to the timing). We identified an airflow job that ran at midnight UTC to dump the database for offline use cases. It ran paginated queries against relevant tables. The job had not succeeded since we enabled group commit and seemed to be timing out on the first query.

The mitigation was fairly easy since there was already a company-wide initiative to move from `mysqldump` to [snapshot exports](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ExportSnapshot.html), which removed the need for running queries against read replicas. However, we needed to understand why enabling group commit caused these queries to time out and where the latency spikes came from to avoid more catastrophic issues.

### History List Length

One metric that correlated well with the start of the airflow job and latency spikes was `RollbackSegmentHistoryListLength` (HLL). HLL counts the number of undo log records generated by transactions (and are not yet cleaned up). Read replicas in Aurora depend on these undo log records to perform repeatable reads, which was our configured isolation level.

One disadvantage of Aurora's shared storage architecture is that long-running queries on read replicas can affect the writer as well. Namely, HLL can grow to really large values when there are long-running queries (see [post](https://howmun.dev/high-hll/)). This is consistent with our observations. HLL grew linearly when the job started to run and dropped sharply after the job failed.

### Undo Log Truncation

The latency spikes lined up perfectly with the moments when HLL started decreasing. This is presumably when the writer begins to truncate the undo log records. To better understand how this interacts with group commit, we first need to understand when MySQL can clean up an undo log record.

MySQL assigns an incrementing ID to each transaction when it starts. Let $$T_i$$ be the $$i$$-th transaction that started. Consider the long-running query $$T_{100}$$ on a reader using the `REPEATABLE READ` isolation level. We will work through which other transactions' undo log records are necessary for $$T_{100}$$ to run correctly. Note that because transactions are atomic, undo log records for a transaction are similarly atomic (they cannot be partially removed).

Undo log records are necessary for any transaction $$T_{i > 100}$$ while $$T_{100}$$ is running because changes from transactions that started after $$T_{100}$$ should not be visible. For any transaction $$T_{i < 100}$$, its undo log records are not needed unless it has not committed by the time $$T_{100}$$ starts. This is because an in progress transaction may alter rows that $$T_{100}$$ has already read. 

Given this, we know that undo log records for a transaction can be removed if there are no in progress transactions that depend on it. The disadvantage of Aurora is that the set of in progress transactions also includes those running on any of the read replicas.

### Transaction Size

The size of write transactions can affect the performance of long-running read queries. Consider one long-running query $$T_{100}$$ that is not using group commit. Assume during the time of its execution that it needs the undo log records from $$T_{99}$$ and $$T_{101}$$. Now, we add in group commit with a group size of 5. In the worst case, $$T_{99}$$ and $$T_{101}$$ are the end and start of their groups respectively. This means that $$T_{100}$$ now needs undo log records from all of the operations in $$\left[ T_{95}, T_{99} \right] \cup \left[ T_{101}, T_{105} \right]$$.

Because there are more undo log records, $$T_{100}$$ has to perform more undo operations to obtain a consistent view while it is executing. This will cause $$T_{100}$$ to take longer to run, which in turn causes it to need even more undo log records. We suspected that this spiral was what caused queries from our airflow job to fail after we enabled group commit, since the average size of transactions significantly increased.

## Learnings

We made significant progress towards improving our database's I/O bottleneck. Our investigations led to some important observations.

- Batching transactions through techniques such as group commit can noticeably improve throughput.
- Long-running transactions can be problematic in MySQL, but even more so in Aurora due to its shared storage architecture and MVCC. Using an isolation level below `REPEATABLE READ` could help.
