---
layout: post
title: "Dual-Client Migration Patterns"
date: 2024-01-14
---

It is often said that all problems in computer science can be solved by another level of indirection. In the case of migrations, I have found this to a surprisingly accurate aphorism. By introducing an additional layer in client logic that conditionally routes to traffic to two different targets, we can perform migrations for a variety of different scenarios in a safe and transparent manner.

## Background

I have worked on various migrations over the last few years at my job. Although they are certainly not the most exciting tasks in software engineering (in my opinion), I think they present interesting challenges when done safely at scale. I wanted to share three different scenarios spanning different types of online migrations. The common thread is that they all use two clients managed at the application level. While it is possible in some cases to perform migrations at the network or load balancer layer, there are distinct advantages to the dual-client approach that we will discuss in individual sections.

## Cluster Migration

The first scenario is that we want to migrate a service from one cluster to another in a controlled way. The main reason for not switching over all of the traffic at once is that we are not sure whether the new cluster behaves in the same way as the existing cluster. For example, slight configuration differences can lead to new errors or performance degradations that are only noticeable at scale. By shifting traffic in smaller increments, we can reduce the likelihood and magnitude of service downtime.

One approach is to do this at the networking layer. This is usually implemented through weighted DNS records (i.e., the calling services probabilistically see either the old or new cluster when looking up the DNS records for the service being migrated). A major disadvantage is that this requires more than one calling service since DNS records are cached. We unfortunately had a singleton caller that was sending a lot of traffic to the migrating service. In addition, we wanted to migrate less critical traffic first, and this was only possible by examining the gRPC requests.

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

## Database Migration