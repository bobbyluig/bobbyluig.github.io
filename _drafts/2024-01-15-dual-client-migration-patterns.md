---
layout: post
title: "Dual-Client Migration Patterns"
date: 2024-01-15
---

It is often said that all problems in computer science can be solved by another level of indirection. In the case of migrations, I have found this to a surprisingly accurate aphorism. By introducing an additional layer in client logic that conditionally routes to traffic to two different targets, we can perform migrations for a variety of different scenarios in a safe and transparent manner.

## Background

I have worked on various migrations over the last few years at my job. Although they are certainly not the most exciting tasks in software engineering (in my opinion), I think they present interesting challenges when done safely at scale. I wanted to share three different scenarios spanning different types of online migrations. The common thread is that they all use two clients managed at the application level. While it is possible in some cases to perform migrations at the network or load balancer layer, there are distinct advantages to the dual-client approach that we will discuss in individual sections.

## Cluster Migration

The first scenario is that we want to migrate a service from one cluster to another in a controlled way. The main reason for not switching over all of the traffic at once is that we are not sure whether the new cluster behaves in the same way as the existing cluster. For example, slight configuration differences can lead to new errors or performance degradations that are only noticeable at scale. By shifting traffic in smaller increments, we can reduce the likelihood and magnitude of service downtime.

One approach is to do this at the networking layer. This is usually implemented through weighted DNS records[^devgrowth] (i.e., the calling services probabilistically see either the old or new cluster when looking up the DNS records for the service being migrated). A major disadvantage is that this requires more than one calling service since DNS records are cached. We unfortunately had a singleton caller that was sending a lot of traffic to the migrating service. In addition, we wanted to migrate less critical traffic first, and this was only possible by examining the gRPC requests.

We can use a dual-client approach to control the cluster migration. Two underlying clients are initialized at startup, one for the old cluster and one for the new cluster. A migration client wraps both underlying clients and routes between them using a flag that could be dynamically controlled. Additional logic reads metadata from each gRPC request to allow more granular migration controls.

```go
type Client interface {
    Method(request RequestType) ResponseType
    /** The client may have other methods. **/
}

type UnderlyingClient struct {
    Address string
    /** Internal state and other configuration are omitted. **/
}

func (c *UnderlyingClient) Method(request RequestType) ResponseType {
    /** Some implementation that forwards the gRPC request to the address. **/
}

type MigrationClient struct {
    OldClient Client
    NewClient Client
    /** Flag client and other configuration are omitted. **/
}

func (c *MigrationClient) Method(request RequestType) ResponseType {
    if (/** Evaluate flag with attributes from the request. **/) {
        return c.OldClient.Method(request)
    }
    return c.NewClient.Method(request)
}

/** Assuming application code is using the client interface. **/
var client Client = &MigrationClient{
    OldClient: &UnderlyingClient{Address: "old-cluster-address"},
    NewClient: &UnderlyingClient{Address: "new-cluster-address"},
}
```

As seen in the example implementation above, the `MigrationClient` allows application code to work throughout the migration process without any changes except replacing the initialized client type on startup. It also allows us to route traffic on a per-request and per-route basis, which can help de-risk the migration process. Note that we can reduce some of the boilerplate code using generics or reflection, but this is language-dependent.

## Redis Migration

The second scenario is that we want to migrate between Redis deployments. In our case, we were migrating from a Redis deployment with cluster mode disabled to a Redis deployment with cluster mode enabled. The Redis cluster was mostly being used as a distributed locking system but also handled rate limiting. Due to the overall throughput, we need to shard the keys while not incurring any downtime since this Redis was used by critical path systems.

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
    /** May include other redsync mutex methods. **/
}

type MigrationMutex struct {
    OldMutex Mutex
    NewMutex Mutex
}

type (m *MigrationMutex) Lock() error {
    if err := m.OldMutex.Lock(); err != nil {
        return err
    }
    return m.NewMutex.Lock()
}

type (m *MigrationMutex) Unlock() (bool, error) {
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

The last and most complex scenario is that we want to migrate between two database clusters with minimal or no downtime.

## References

[^devgrowth]: @devgrowth (2023). [Inside AWS Route53's Weighted Routing Policy](https://hackernoon.com/inside-aws-route53s-weighted-routing-policy).
[^rate-limiter]: Redis Glossary (2024). [Rate Limiting - What is Rate Limiting?](https://redis.com/glossary/rate-limiting/)