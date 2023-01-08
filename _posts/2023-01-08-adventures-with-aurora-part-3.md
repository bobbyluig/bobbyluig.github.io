---
layout: single
title: "Adventures with Aurora (Part 3)"
date: 2023-01-08
last_modified_at: 2023-01-08
toc: true
---

We had successfully mitigated our database's I/O bottleneck by batching high throughput transactions in the application layer. However, Aurora had one last trick up its sleeve. Meanwhile, an upcoming project gave us the opportunity to implement a long-term fix for our database load issues.

## Equality Range

Consider a query that contains an `IN` predicate over a non-unique indexed column. In the example below, `col_0` is non-unique because it is the first column of a composite primary key index. When running queries of this form, the optimizer needs to estimate the number of rows it will scan to accurately determine the query cost. For more details on query optimization, refer to the [MySQL Reference Manual](https://dev.mysql.com/doc/refman/5.6/en/select-optimization.html).

```sql
CREATE TABLE example(
	col_0 INT NOT NULL,
	col_1 INT NOT NULL,
	col_2 INT NOT NULL,
	PRIMARY KEY (col_0, col_1)
);
SELECT * FROM example WHERE col_0 IN (?);
```

Even though an index is available, the optimizer may choose to not use it if the index has a high selectivity value or if the table is small. Using the index could actually result in worse performance since there is overhead for each index access.

The optimizer would like an accurate estimate of how many rows will be scanned if the index is used. This can be achieved using [index dives](https://dev.mysql.com/doc/refman/5.6/en/range-optimization.html) for each equality range (i.e., each value inside of the `IN` predicate). However, index dives become expensive if there are a lot of values. In those cases, MySQL will instead rely on index statistics to provide a faster but less accurate row estimation.

In MySQL 5.6, the default threshold for index dives is 10. That means if there are less than 10 equality ranges in an expression, the optimizer will perform index dives. Otherwise, it will use index statistics. The threshold can be set using the  `eq_range_index_dive_limit` database parameter.

Let's look at how the optimizer deals with various datasets. In the table below, we show how the number of rows in the table, the cardinality of the index for `col_0`, and the number of equality ranges in the query affect the query plan. All results are generated using the schema and query shown before. However, the query is expected to return no rows because none of the values in the `IN` predicate match any row in the inserted data.

| Table Rows | Index Cardinality | Equality Ranges | Index Used | Row Estimate |
|:----------:|:-----------------:|:---------------:|:----------:|:------------:|
|     10     |         1         |        4        |     Yes    |       4      |
|     10     |         1         |        5        |     No     |      10      |
|     10     |         10        |        4        |     Yes    |       4      |
|     10     |         10        |        5        |     No     |      10      |
|    1,000   |         1         |        9        |     Yes    |       9      |
|    1,000   |         1         |        10       |     No     |     1,000    |
|    1,000   |       1,000       |        9        |     Yes    |       9      |
|    1,000   |       1,000       |        10       |     Yes    |      10      |

Notice that when the table is small, MySQL prefers to not use the index (perform a full scan) even if the index has a low selectivity value. When the table is larger and the index has a high selectivity value, using index dives gives a much better query plan than using index statistics. In the worst case, even though no rows should be returned, MySQL can decide to perform a full scan of the table because it doesn't think the index is very useful by just looking at statistics. 

## Catastrophic Full Scan

For a few weeks, our database hummed along without any issues. After all, many nights had been spent mitigating I/O bottlenecks and avoiding long running queries. We were done with Aurora, but Aurora was not done with us. One morning, we woke up to a severely degraded database. Both CPU and I/O waits increased significantly.

An interesting metric change was that `innodb_rows_read.avg` (the number of rows read per second) had spiked by a factor of 10. This indicated that one or more queries were performing a full scan (on a table with more than 2 billion rows). Upon inspecting the running queries, we found that there were more than 40 queries which had been running for half an hour. We quickly killed those queries, which resolved the database degradation.

Of course, we avoided running full scans in our online databases, so we were quite confused as to how this happened. The query performing the full scan was a simple `SELECT` query with an `IN` predicate. We ran `EXPLAIN` multiple times and confirmed that the query should have been using the index. Upon closer inspection of the metrics, we noticed that similar full scans had happened intermittently over the past week, although there were not enough concurrent full scans to cause our alerts to fire.

It was time to pull out the MySQL debugging hat once again. Given the intermittent nature of these full scans and the fact that these queries should have used the index, we suspected it had something to do with the query optimizer and index updates. We scoured for MySQL bugs and stumbled on [#82969](https://bugs.mysql.com/bug.php?id=82969), which describes a race condition associated with the computation of index statistics.

### Cost Estimation

The first step in understanding how these full scans manifested was to look at how MySQL estimates the cost of a query. Given that our query used equality ranges, we tracked down the function responsible for estimating the number of rows that will be scanned. A simplified version of the function is shown below.

```cpp
uint64_t handler::multi_range_read_info_const(...) {
	int64_t total_rows = 0;
	
	// Go through each equality range.
	while (...) {
		if ((range.range_flag & UNIQUE_RANGE) && 
				!(range.range_flag & NULL_RANGE)) {
			// Index is unique. There is at most one row.
			rows = 1;
		}
		else if ((range.range_flag & EQ_RANGE) &&
						 (range.range_flag & USE_INDEX_STATISTICS) &&
						 (keyparts_used = my_count_bits(range.start_key.keypart_map)) &&
						 table->key_info[keyno].rec_per_key[keyparts_used - 1] &&
						 !(range.range_flag & NULL_RANGE)) {
			// Estimate using index statistics.
			rows = table->key_info[keyno].rec_per_key[keyparts_used - 1];
		}
		else {
			// Perform index dive.
			rows = this->records_in_range(...);
		}
		total_rows += rows;
	}

	return total_rows;
}
```

We were performing an `IN` query on a composite primary key index and only using the first part of the key (similar to the example table shown before). Therefore, the index was not unique. From the implementation, we can see that the row estimate depended on whether the optimizer chose to perform an index dive or to use index statistics.

```cpp
int ha_innobase::info_low(uint flag, ...) {
	// [snip]

	if (flag & HA_STATUS_CONST) {
		for (i = 0; i < table->s->keys; i++) {
			for (j = 0; j < table->key_info[i].actual_key_parts; j++) {
				rec_per_key = innodb_rec_per_key(index, j, stats.records);
				if (rec_per_key == 0) {
					rec_per_key = 1;
				}
				table->key_info[i].rec_per_key[j] = rec_per_key;
			}
		}
	}

	// [snip]
}

uint64_t innodb_rec_per_key(...) {
	uint64_t n_diff = index->stat_n_diff_key_vals[i];

	if (n_diff == 0) {
		rec_per_key = records;
	}

	// [snip]
}
```

Index statistics relies on the `rec_per_key` value. The above code is a simplified version of how it gets populated. Lower `rec_per_key` means that the index is more selective and better at filtering out rows. There is a special condition that when `n_diff` is zero (such as when statistics are not initialized), `rec_per_key` is set to the total number of rows in the table. This will be important later.

### Statistics Calculation

Table statistics need to be updated occasionally so that the query optimizer can generate good plans. In MySQL, this happens automatically when a table undergoes changes to more than 10% of its rows ([source](https://dev.mysql.com/doc/refman/5.6/en/innodb-persistent-stats.html)). Let's look at the functions responsible for updating table statistics.

```cpp
dberr_t dict_stats_update_persistent(...) {
	// Analyze clustered index first.
	dict_index_t* index = dict_table_get_first_index(table);
	dict_stats_analyze_index(index);

	// Analyze other indexes.
	// [snip]
}

void dict_stats_analyze_index(...) {
	// Empty the index first.
	dict_stats_empty_index(index);
	
	// [snip]

	// Compute and populate index statistics.
	dict_stats_analyze_index_level(index, 0,  index->stat_n_diff_key_vals);

	// [snip]
}

void dict_stats_empty_index(...) {
	for (...) {
		index->stat_n_diff_key_vals[i] = 0;
		index->stat_n_sample_sizes[i] = 1;
		index->stat_n_non_null_key_vals[i] = 0;
	}

	// [snip]
}
```

When index statistics are updated, all statistics values are first reset. In particular, `stat_n_diff_key_vals` is zeroed before it is populated. This could cause problems if the query optimizer reads index statistics while they are being updated.

### Race Condition

An audit of the queries executed during the incident showed that they all had 10 or more values in the `IN` predicate. This was not a coincidence because it was the exact threshold at which 1.x Aurora would switch from index dives to index statistics. We now describe a race condition that can happen for `SELECT` queries using equality ranges.

1. The database determines that table statistics need to be updated.
2. A background thread runs `dict_stats_analyze_index`, but is preempted before it can actually populate the index statistics.
3. A transaction running a `SELECT` query is processed and runs `info_low` to get updated table statistics. Because the statistics were reset, `rec_per_key` is set to be the number of rows in the table.
4. The transaction has an `IN` predicate with 10 or more values. Therefore, the query optimizer uses index statistics. However, it incorrectly determines that the index is not useful at all because it has a very high selectivity value.
5. The transaction decides to perform a full scan instead.

Note that if the query optimizer decided to use index dives instead, it would get a correct estimate and not perform a full scan. This is consistent with what we observed in our system. Under high concurrency, it is possible for many transactions to see an incorrect value for `rec_per_key` before the background thread is able to populate the index statistics.

### Bug Replication

As with the previous MySQL bug that we discovered, we needed to replicate this bug in our load testing environment to gain confidence of the root cause and to verify that our mitigations worked. Fortunately, there is a way to force the database to update table statistics.

```sql
ANALYZE TABLE ...;
```

By repeatedly analyzing the table, we were able to force the database to update index statistics more frequently. Then, all we had to do was run the problematic `SELECT` query at high rate. We were able to replicate the full scan bug consistently in only a few minutes. However, we now needed a way to make sure that our existing queries never performed a full scan even in the presence of this bug. Some research led us to [index hints](https://dev.mysql.com/doc/refman/5.6/en/index-hints.html), which were a way to influence MySQL's query plans.

> "The `FORCE INDEX` hint acts like `USE INDEX (index_list)`, with the addition that a table scan is assumed to be very expensive. In other words, a table scan is used only if there is no way to use one of the named indexes to find rows in the table."  
> — MySQL 5.6 Reference Manual

After adding `FORCE INDEX` to all of our queries that contained `IN` predicates, we verified in our load testing environment that these `SELECT` queries always used the index instead of performing full scans even when table statistics were being updated. However, we're not sure when MySQL fixed this bug.

## Data Store Migration

A major contributor to all of our database problems was that we were pushing our Aurora instance to the limit. We needed a more permanent solution to our database issues in addition to the existing mitigations. We looked at our workload to see if there were pieces that could be migrated to a different data store.

### Workload

It turned out that a significant part of our database load was coming from a use case that stored transient metadata. We had a scheduling system that processed around 1,000 recurring tasks per second. For each task, it would write some metadata to a row, perform the task, and then clear the metadata from the row once it persisted the task's results. The system needed the metadata to make various scheduling decisions.

This workload was more appropriate for Redis. SQL databases, and especially Aurora, are not designed for high-throughput update workloads. Redis, on the other hand, excels at storing transient data that needs to be updated and read frequently. Therefore, we decided to migrate the metadata out of Aurora and into Redis.

### Unexpected Results

After the migration was complete, the load on the database decrease by over 80% (as measured by average active sessions). This was unexpected, because we hadn't actually reduced the number of queries, only the amount of data that the queries had to write. The metadata fields were also pretty small compared to the other data we had in the table.

After a bit of investigation, we discovered two contributors to the unexpected load decrease. The first was that the query at the beginning of every task only updated the metadata columns (and very occasionally inserted a row if it did not exist) while the query at the end also wrote to other columns. This meant that by removing metadata writes, we had effectively turned a write transaction into a read transaction.

The second was that one of the metadata columns had a secondary index defined. This index was no longer used, but was left because removing the index would require locking the entire table. Vanilla MySQL optimizes secondary index writes using the [change buffer](https://dev.mysql.com/doc/refman/5.6/en/innodb-change-buffer.html), which caches changes to secondary indexes in memory.

> "Unlike clustered indexes, secondary indexes are usually nonunique, and inserts into secondary indexes happen in a relatively random order. Similarly, deletes and updates may affect secondary index pages that are not adjacently located in an index tree. Merging cached changes at a later time, when affected pages are read into the buffer pool by other operations, avoids substantial random access I/O that would be required to read secondary index pages into the buffer pool from disk."
> — MySQL 5.6 Reference Manual

Unfortunately, the shared storage architecture of Aurora means that the change buffer had to be disabled. There is no way to cache changes to secondary indexes on the writer since the readers can't directly access the writer's buffer pool. This meant that by removing secondary index updates, we were able to substantially reduce I/O operations.

## Learnings

Finally, we are at the end of our Aurora journey. There are a few more important learnings that I wanted to share.

- For large tables, use index hints if you need a particular query behavior. The optimizer can generate catastrophic query plans due to various bugs or edge cases.
- Avoid secondary indexes in Aurora to improve write throughput. Vanilla MySQL may outperform its Aurora counterparts for update-heavy workloads, especially if there are secondary indexes.
- Pushing a database to the limit can have unintended consequences. Some types of database bugs only manifest at high concurrency. A single bad query is more likely to wreak havoc if the database already has too much load.