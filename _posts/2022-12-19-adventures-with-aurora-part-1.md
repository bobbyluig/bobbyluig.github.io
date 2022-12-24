---
layout: single
title: "Adventures with Aurora (Part 1)"
date: 2022-12-19
toc: true
---

I have been battling with an Aurora MySQL database at work for the past few months. As a result, I learned a lot about the internals of MySQL and how to debug database-related issues. In this three-part series, I wanted to share some of the challenges that we encountered and how we solved them.

## Performance Cliff

One day, out of nowhere, my team's database started acting up. We saw significant latency increases across many database operations that we could not attribute to a particular spike in traffic or increase in transaction load. Unfortunately, this database was in the critical path of the user onboarding flow, so it was important for us to resolve these latency issues.

After a more thorough investigation, we determined that the database had hit some kind of I/O limit. The telltale signs were a disproportionate increase in the wait times of two operations when looking at performance insights:

- `wait/io/redo_log_flush`
- `wait/synch/cond/sql/MYSQL_BIN_LOG::COND_wait`

We will dive more into the details of these operations later, but this was somewhat troubling because the database was not sharded and had already been vertically scaled to the largest instance size of `r5.24xlarge`. We needed a quick, zero-downtime mitigation before things got worse.

## Aurora Architecture

Before proceeding further, it will be useful to understand how Aurora MySQL differs from vanilla MySQL. One of my coworkers wrote a great [post](https://plaid.com/blog/exploring-performance-differences-between-amazon-aurora-and-vanilla-mysql/) about this exact topic (and in fact, in reference to the exact same database causing trouble three years later). I also recommend reading the original [paper](https://web.stanford.edu/class/cs245/readings/aurora.pdf) on Amazon Aurora, which has more details.

At the time the issues started, we were still running on 1.x Aurora MySQL, which is wire-compatible with Community MySQL 5.6.10a. For the purposes of this post, we only need to focus on the fact that Aurora MySQL shares a lot of code with vanilla MySQL, but differs in how replication is handled and how transactions are written to distributed storage.

## Relaxed Durability

One of the first things we tried was to relax the durability of transactions. We were not running workloads which required the default durability guarantees of MySQL. In particular, we were okay with losing a second of committed transactions during a power outage. MySQL allows control over this through the `innodb_flush_log_at_trx_commit` parameter. Normally, this value is set to `1`, which means that logs are flushed to disk after every transaction. 

To improve performance by trading off durability, we can set this parameter to `0`. This causes logs to be flushed to disk once per second, which means that a transaction can commit before the logs are persisted. We expected this to help with our I/O bottleneck, but it actually didn't do anything at all (and at times made performance worse).

The reason for this is that Aurora employs asynchronous commits along with batched writes to storage (see [paper](https://web.stanford.edu/class/cs245/readings/aurora.pdf) and [post](https://aws.amazon.com/blogs/database/planning-i-o-in-amazon-aurora/)).

> "In Aurora, transaction commits are completed asynchronously. When a client commits a transaction, the thread handling the commit request sets the transaction aside by recording its "commit LSN" as part of a separate list of transactions waiting on commit and moves on to perform other work."  
> — Amazon Aurora: Design Considerations for High Throughput Cloud-Native Relational Databases

> "Although actual log records vary in size, writes to an Aurora cluster are sent in 4 KB units when possible. If the writer has several log records at the same time that are less than 4 KB in size, they’re batched together into a single write operation.... Log records greater than 4 KB are split into 4 KB units."  
> — Planning I/O in Amazon Aurora

As a result, flushing to disk once per second does not necessarily reduce the number of I/O operations because Aurora is already able to take advantage of highly concurrent write workloads by batching log record writes between transactions. Although relaxed durability might allow transactions to commit without waiting for log flushes, the overall throughput of write transactions is still limited by the IOPS of Aurora's storage.

## Relaxed Binary Log Ordering

Our next attempt was to relax the [binary log](https://dev.mysql.com/doc/refman/5.6/en/binary-log.html) ordering. We had binary log enabled as a way to replicate data across AWS regions before [Aurora Global Database](https://aws.amazon.com/rds/aurora/global-database/) was available. There was no way to disable the binary log entirely without restarting the database and incurring downtime. However, we could change the way commits are serialized relative to the binary log through the `binlog_order_commits` parameter.

The binary log is written using group commit. The core idea is that if many transactions commit around the same time, it is more efficient to group them and only flush data to disk once. The first transaction to commit is the leader. It waits for additional followers to join the group. Once a follower joins the group, it simply waits for the leader to complete all of the commit steps. There are three steps involved in a commit. Note that transactions which do not perform writes will skip the first two stages.

1. Flush Stage: the leader serially flushes the changes of every transaction in its group to the binary log.
2. Sync Stage: the leader synchronizes the binary log to storage.
3. Commit Stage: the leader serially commits (to the storage engine) every transaction in its group. 

The leader serially performs the last stage because the order of commits to the storage engine should ideally be the same as the order of operations in the binary log. Performance could be improved if followers ran the last stage themselves in separate threads, but it could result in a different commit ordering (although this usually does not matter).

Lured by the promise of higher performance, we enabled the parameter in our load testing environment and found that it did have a positive impact on commit latency. We enabled `binlog_order_commits` in production to monitor its impact. Less than 24 hours later, the entire database goes down.

## Database Deadlock

We know that transactions can deadlock, but the database has mechanisms to remedy this (usually by aborting one of the transactions). In this case however, no transactions were able to make progress. From metrics, it appeared that transactions were all blocked on the `COMMIT` statement. Interestingly, read-only transactions were able to proceed without any issues.

Clearly, there was some kind of deadlock within the database itself, and it was triggered by us changing the value of `binlog_order_commits`. However, we wanted to understand why this happened and why we were not able to catch it in other environments. We scoured the [MySQL Bug System](https://bugs.mysql.com/) looking for clues and came across bug [#68569](https://bugs.mysql.com/bug.php?id=68569). It looked similar to the issue we ran into, but it was not immediately clear what triggered the deadlock. We had to dive deeper—straight into MySQL source code.

### Commit Implementation

We checked out [MySQL 5.6.10](https://github.com/mysql/mysql-server/releases/tag/mysql-5.6.10), which was close enough to what 1.x Aurora MySQL was using. From a full code search, there was only one place where `binlog_order_commits` was used. A simplified version of the function is shown below. For the full implementation, refer to the [code](https://github.com/mysql/mysql-server/blob/91773b1f65de78924e0cd2b30009d44f64f9dee9/sql/binlog.cc#L6301).

```cpp
int MYSQL_BIN_LOG::ordered_commit(...) {
  // (1) Flush stage.
  if (change_stage(..., NULL, &LOCK_log)) {
    finish_commit(thd);
  }
  process_flush_stage_queue(...);

  // (2) Sync stage.
  if (change_stage(..., &LOCK_log, &LOCK_sync)) {
    finish_commit(thd);
  }
  sync_binlog_file(...);

  // (3) Commit stage.
  if (opt_binlog_order_commits) {
    if (change_stage(..., &LOCK_sync, &LOCK_commit)) {
      finish_commit(thd);
    }
    process_commit_stage_queue(...);
    pthread_mutex_unlock(&LOCK_commit);
  }
  else {
    pthread_mutex_unlock(&LOCK_sync);
  }

  // Signal all follower threads that are waiting.
  stage_manager.signal_done(...);

  // Finish our own commit.
  finish_commit(thd);

  // Perform a binary log rotation if necessary.
  if (do_rotate) {
    pthread_mutex_lock(&LOCK_log);
    rotate(...);
    pthread_mutex_unlock(&LOCK_log);
  }
}
```

In each stage, the leader releases the lock for the previous stage, acquires the lock for the current stage, and performs some work. If the `change_stage` call fails, then the thread is a follower. When `opt_binlog_order_commits` is false, the leader simply releases the lock instead of processing the commit stage queue. Each thread is then individually responsible for committing when they run `finish_commit`.

```cpp
int MYSQL_BIN_LOG::finish_commit(...) {
  // Check if the transaction is already committed.
  if (thd->transaction.flags.commit_low) {
    ha_commit_low(thd, all);
    if (thd->transaction.flags.xid_written) {
      dec_prep_xids();
    }
  }
}
```

### Binary Log Rotation

After the leader commits, MySQL may need to perform a binary log rotation if the binary log file has grown too large. The maximum size of binary log files is fixed in 1.x Aurora MySQL at 128 MB (although it is adjustable in vanilla MySQL through `max_binlog_size`). During a rotation, the leader needs to make sure that no other threads can touch the binary log. This is achieved by acquiring three locks in order.

1. `LOCK_log`: this prevents any new transactions from starting the first stage. 
2. `LOCK_commit`: this ensures there are no prepared transactions. If there are prepared transactions, the leader will release the lock and wait until prepared transactions have committed. 
3. `LOCK_index`: this prevents other binary log index operations from happening at the same time. MySQL maintains a binary log index file with the names of binary log files.

```cpp
int MYSQL_BIN_LOG::new_file_impl(...) {
  // (1) `LOG_lock` is already acquired by the caller.

  // (2) If there are prepared transactions, wait on the condition variable.
  pthread_mutex_lock(&LOCK_commit);
  while (get_prep_xids() > 0) {
    pthread_cond_wait(&m_prep_xids_cond, &LOCK_commit);
  }
  
  // (3) Acquire `LOG_index`.
  pthread_mutex_lock(&LOCK_index);

  // [snip]
}
```

Note that a transaction enters the prepared state in the flush stage and exits the prepared state in the commit stage. Binary log rotation only needs to know the number of transactions in a prepared state, so tracking is done through an atomic integer. We show the implementation of the `*_prep_xids` functions below since it is relevant for our discussion.

```cpp
void inc_prep_xids() {
  my_atomic_add32(&m_prep_xids, 1);
}

void dec_prep_xids() {
  int32_t result = my_atomic_add32(&m_prep_xids, -1);
  if (result == 1) {
    pthread_cond_signal(&m_prep_xids_cond);
  }
}

int32_t get_prep_xids() {
  return my_atomic_load32(&m_prep_xids);
}
```

### Lost Wake-Up

If there are no threads waiting for the signal when `pthread_cond_signal` is called, the signal is lost. This is okay in some cases, but not if the lost signal causes a deadlock. It turns out that this is exactly the bug that caused our database to go down.

We had a hypothesis that the bug can only be triggered during a binary log rotation. That would explain why the deadlock took many hours to manifest even though we had a highly concurrent workload. Furthermore, we believed that the deadlock occurred somewhere in the `ordered_commit` function because application metrics indicated that write transactions were blocked on the `COMMIT` statement.

Given this, we were able to come up with a thread ordering that triggered a deadlock and matches the exact behavior that we observed. Consider three transactions `T1` through `T3` that are being processed by different threads. Assume for simplicity that there are no other transactions or database operations happening during this time.

1. `T1` and `T2` commit around the same time.
2. `T1` enters the flush stage first and becomes the leader.
3. `T2` also enters the flush stage but becomes a follower.
4. `T1` gets to the commit stage and sees that `opt_binlog_order_commits` is false. It releases `LOCK_sync` and signals to `T2` that it is done.
5. `T1` runs `finish_commit`. Because the commit stage was skipped, `T1` runs `ha_commit_low` to commit to the storage engine. `T1` also calls `dec_prep_xids`. After this, there is still one prepared transaction because `T2` has not committed yet.
6. `T1` notices that it needs to perform a binary log rotation. It grabs `LOCK_log` and `LOCK_commit`. `T1` checks for prepared transactions using `get_prep_xids` and sees that there is one. At this point, `T1` gets preempted.
7. `T2` runs `finish_commit`. It eventually also calls `dec_prep_xids`. Because it was the last transaction to commit, it signals `m_prep_xids_cond` to wake a waiting thread. Unfortunately, `T1` has not yet waited for the condition variable.
8. `T1` now atomically releases `LOCK_commit` and waits for `m_prep_xids_cond`. However, the wake-up has been lost, so `T1` will wait forever.
9. `T3` is now ready to commit. However, it is not able to grab `LOCK_log` because `T1` is holding it. A deadlock has occurred.

Note that this is not possible if `opt_binlog_order_commits` is true because the leader would have to first acquire `LOCK_commit` before calling `dec_prep_xids` for each of the transactions in its group. This highlights the importance of guarding condition writes with the same lock that is being used to wait on the condition variable. The bug was eventually fixed by this [commit](https://github.com/mysql/mysql-server/commit/e9fea31), which introduces a new lock to guard reads and writes of `m_prep_xids`.

### Bug Replication
          
We were not satisfied with only a theoretical understanding of the deadlock bug. After all, we needed to make sure that this incident would not occur again. The challenge with replicating concurrency bugs is that they may only occur in very specific scenarios. In this case, there had to be a binary log rotation, and that only happened once or twice per hour in our database. We thought about decreasing the maximum binary log size, but that was not possible in Aurora. Fortunately, we stumbled upon the fact that we can manually trigger binary log rotations through a SQL command.

```sql
FLUSH BINARY LOGS;
```

Flushing the binary logs effectively performed a binary log rotation regardless of the size of the current file. By manually flushing the binary logs once per second and running a concurrent workload in our load testing environment, we were able to consistently replicate the deadlock in under 10 minutes. We finally confirmed that the bug came from MySQL and that keeping `binlog_order_commits` enabled would prevent the deadlock from occurring again.

## Learnings

There are some important takeaways even though we had caused an incident and not made any progress towards alleviating database load.

- `innodb_flush_log_at_trx_commit` has limited impact in 1.x Aurora MySQL (and likely 2.x Aurora MySQL) for high throughput write workloads due to asynchronous commits and batched log writes.
- Do not disable `binlog_order_commits` if you are running on 1.x Aurora MySQL or a MySQL version before 5.6.12 or 5.7.2. Even when disabled, the performance improvement is likely not noticeable if the bottleneck is related to I/O throughput.
- Tuning database parameters can be dangerous, especially if they are not well known. Perform thorough and representative load testing before applying any changes to production.
