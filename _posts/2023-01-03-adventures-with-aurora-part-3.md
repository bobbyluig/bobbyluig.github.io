---
layout: single
title: "Adventures with Aurora (Part 3)"
date: 2023-01-03
last_modified_at: 2023-01-03
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

Let's look at how the optimizer deals with various datasets. In the table below, we show how the number of rows in the table, the cardinality of the index for `col_0`, and the number of equality ranges in the query affect the query plan. All results are generated using the schema and query shown before. However, the query is expected to return no rows because none of values in the `IN` predicate match any row in the inserted data.

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

### Cost Estimation

### Statistics Calculation

### Race Condition

### Bug Replication

## Data Store Migration

### Workload

### Migration Strategy

### Results

## Learnings