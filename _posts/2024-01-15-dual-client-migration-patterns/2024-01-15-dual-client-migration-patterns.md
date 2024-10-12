---
layout: post
title: "Dual-Client Migration Patterns"
date: 2024-01-15
features: [highlight, mathjax]
---

It is often said that all problems in computer science can be solved by another level of indirection. In the case of migrations, I have found this to be a surprisingly accurate aphorism. By introducing an additional layer in client logic that conditionally routes traffic to two different targets, we can perform migrations for a variety of different scenarios in a safe and transparent manner.

## Background

I have worked on various migrations over the last few years at my job. Although they are certainly not the most exciting tasks in software engineering (in my opinion), I think they present interesting challenges when done safely at scale. I wanted to share three scenarios from different types of online migrations. The common thread is that they all use two clients managed at the application level. While it is possible in some cases to perform migrations at the network or load balancer layer, there are distinct advantages to the dual-client approach that we will discuss in individual sections.

## Service Migration

The first scenario is that we want to migrate a service from one cluster to another in a controlled way. The main reason for not switching over all of the traffic at once is that we are not sure whether the new cluster behaves in the same way as the existing cluster. For example, slight configuration differences can lead to new errors or performance degradations that are only noticeable at scale. By shifting traffic in smaller increments, we can reduce the likelihood and magnitude of service downtime.

One approach is to do this at the networking layer. This is usually implemented through weighted DNS records[^devgrowth] (i.e., the calling services probabilistically see either the old or new cluster when looking up the DNS records for the service being migrated). A major disadvantage is that this requires more than one calling service since DNS records are cached. We unfortunately had a singleton caller that was sending a lot of traffic to the migrating service. In addition, we wanted to migrate less critical traffic first, and this was only possible by examining the gRPC requests.

We can use a dual-client approach to control the service migration. Two underlying clients are initialized at startup, one for the old cluster and one for the new cluster. A migration client wraps both underlying clients and routes between them using a flag that could be dynamically controlled. Additional logic reads metadata from each gRPC request to allow more granular migration controls.

```go
type Client interface {
    Method(request RequestType) ResponseType
    // The client may have other methods.
}

type MigrationClient struct {
    OldClient Client
    NewClient Client
    // Flag client and other configuration are omitted.
}

func (c *MigrationClient) Method(request RequestType) ResponseType {
    if (/** Evaluate flag to see if new cluster should be used. **/) {
        return c.NewClient.Method(request)
    }
    return c.OldClient.Method(request)
}

// Assuming application code is using the client interface.
var client Client = &MigrationClient{
    OldClient: &UnderlyingClient{Address: "old-cluster-address"},
    NewClient: &UnderlyingClient{Address: "new-cluster-address"},
}
```

As seen in the example implementation above, the `MigrationClient` allows application code to work throughout the migration process without any changes except replacing the initialized client type on startup. It also allows us to route traffic on a per-request and per-route basis, which can help de-risk the migration process. Note that we can reduce some of the boilerplate code using generics or reflection, but this is language-dependent.

## Redis Migration

The second scenario is that we want to migrate between Redis deployments. In our case, we were migrating from a Redis deployment with cluster mode disabled to a Redis deployment with cluster mode enabled. The Redis cluster was mostly being used as a distributed locking system but also handled rate limiting. Due to the overall throughput, we needed to shard the keys while not incurring any downtime since this Redis was used by critical path systems.

It turns out that locking and rate limiting can be migrated using the dual-client approach without copying any existing keys between deployments. The main observation is that since these use cases operate on keys that expire, dual-writing to both deployments would result in a consistent state after the max TTL of any key in the old deployment has passed. The TTL of a lock is the configured expiry duration. The TTL of a leaky bucket rate limiter is the granularity of individual buckets[^rate-limiter] (e.g., the TTL of a per-minute rate limiter is one minute).

We list the steps that can be used to perform the migration assuming that all keys in the old deployment have reasonably finite TTL.

1. Create a new empty deployment with the desired configuration.
2. Use the dual-client approach to read and write from both deployments.
3. Wait until the max TTL has passed.
4. Remove reads and writes from the old deployment.
5. Shut down the old deployment.

For locking and rate limiting, the migration client will only consider an operation successful if it succeeds for both underlying clients. It is not necessary to use any flags for this migration unless we are not sure that the new cluster will behave correctly in step (2). In that case, the waiting time for step (3) does not begin until the flag is fully rolled out. We will show an example implementation for the locking case since there are some subtleties.

```go
type Mutex interface {
    Lock() error
    Unlock() (bool, error)
    // May include other redsync mutex methods.
}

type MigrationMutex struct {
    OldMutex Mutex
    NewMutex Mutex
}

func (m *MigrationMutex) Lock() error {
    if err := m.OldMutex.Lock(); err != nil {
        return err
    }
    return m.NewMutex.Lock()
}

func (m *MigrationMutex) Unlock() (bool, error) {
    oldOk, oldErr := m.OldMutex.Unlock()
    if !oldOk || oldErr != nil {
        return oldOk, oldErr
    }
    newOk, newErr := m.NewMutex.Unlock()
    if !newOk || newErr != nil {
        return newOk, newErr
    }
    return true, nil
}
```

Note that it is possible for `Unlock` to return an error when dual-writing starts because the new Redis deployment does not have any locks. We can check for this explicitly, but our application just logs these errors without taking any additional action. Unlike the rate limiting case where we can run operations on both the old and new deployments in parallel, locking must be applied serially to enforce ordering and avoid deadlocks.

## Database Migration

The last and most complex scenario is that we want to migrate between two database clusters. There are many ways to approach this, but in our case, we were okay with incurring a few minutes of downtime during a maintenance window if the migration could be performed without too much engineering time spent on dual-writing. We were very concerned with introducing data inconsistencies[^dual-write] and the effort it would take to prevent, detect, and correct them.

Databases usually expose some way to replicate data. For example, replication between Aurora MySQL clusters can be done through binary log[^replication]. The strategy is to snapshot the data in the old cluster, load it into the new cluster, and set up replication until the lag stabilizes. This is surprisingly fast even for very large instances. For our non-sharded Aurora MySQL database with more than 1 TiB of data and tables containing billions of rows, taking a snapshot only took a few hours and replication lag stabilized after less than a day even though the database was pretty close to write throughput limits.

Replication does not fully solve the issue of data inconsistencies since there is lag between the old and new clusters and also between clients on when they switch to using the new cluster. Fortunately, we can once again rely on the dual-client approach with a flag. The idea is that we will temporarily stop all write traffic from clients until we can be sure that the old and new clusters are in a consistent state. Then, we instruct all clients to switch over to the new cluster.

```go
type Client interface {
    WithTx(
        ctx context.Context,
        fn func(ctx context.Context, tx *sql.Tx) error,
    ) error
    // Interface could be different depending on implementation.
}

type MigrationClient struct {
    OldClient Client
    NewClient Client
    // Flag client and other configuration are omitted.
}

func (m *MigrationClient) WithTx(
    ctx context.Context,
    fn func(ctx context.Context, tx *sql.Tx) error,
) error {
    if (/** Evaluate flag to see if traffic should be stopped. **/) {
        return errors.New("stopping traffic for migration")
    }
    if (/** Evaluate flag to see if new cluster should be used. **/) {
        return m.NewClient.WithTx(ctx, fn)
    }
    return m.OldClient.WithTx(ctx, fn)
}
```

It is not necessary to stop traffic for read-only transactions at any time during the migration. For each service, we had one client for read-only traffic and one client for read-write traffic. Therefore, it was possible for us to target the flag based on the client type. An alternative is to annotate each transaction with whether it is read-only to minimize the downtime impact, but this needs to be done carefully to not accidentally cause inconsistencies during migration.

The duration to stop the traffic needs to be determined to ensure consistency across the two clusters. The flag change takes some time to propagate to every client, and the last write by a client needs to be replicated before we can switch traffic over to the new cluster. Therefore, the time to stop the traffic is the upper bound flag propagation time plus the upper bound replication lag. Using streaming flag management from LaunchDarkly, the propagation time is under one second. Reducing non-critical traffic to the database led to a replication lag under five seconds. It is also a good idea (time permitting) to verify that the replication in the new cluster has caught up before finalizing the switch for all clients.

### Zero Downtime Extension

One extension which we did not implement for our migration is to have the entire process be automated and not immediately error when traffic should be stopped. Let's assume that the traffic needs to be stopped for at least $$t$$ seconds to achieve consistency (based on flag propagation delay and replication lag) where $$2t$$ is less than most timeouts for calls involving the database. Furthermore, the longest running transaction in the system is upper bounded by $$t$$. We use a single flag that begins the migration process. Each client performs the following steps when they observe the flag change for the first time.

1. Atomically set a variable indicating that traffic should be stopped.
2. Start a task that will atomically swap the underlying client that should be used and unset the variable in step (1) after $$2t$$ seconds.
3. Prior to running `WithTx` for all writer transactions and reader transactions that cannot tolerate lag of up to $$2t$$ seconds, check if traffic should be stopped. If so, sleep until traffic is no longer stopped and then run `WithTx` on the new cluster.
4. Once the underlying client is swapped, the migration is complete and all traffic should be flowing to the new cluster.

This increases the latency of `WithTx` calls by at most $$2t$$ seconds, but assuming that $$2t$$ is sufficiently small, it should only cause increased latency for callers instead of erroring. Consistency is maintained because in the worst case, the last write to be fully replicated will be from a slow running transaction that takes $$t$$ seconds to run on the old cluster and needs another $$t$$ seconds from the flag propagation delay and replication lag to be visible in the new cluster.


## References

[^devgrowth]: @devgrowth (2023). [Inside AWS Route53's Weighted Routing Policy](https://hackernoon.com/inside-aws-route53s-weighted-routing-policy).
[^rate-limiter]: Redis Glossary (2024). [Rate Limiting - What is Rate Limiting?](https://redis.com/glossary/rate-limiting/)
[^dual-write]: Janssen, Thorben (2020). [Dual Writes – The Unknown Cause of Data Inconsistencies](https://thorben-janssen.com/dual-writes/).
[^replication]: AWS Documentation (2024). [Replication between Aurora and MySQL or between Aurora and another Aurora DB cluster (binary log replication)](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraMySQL.Replication.MySQL.html).