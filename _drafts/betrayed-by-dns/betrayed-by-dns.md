---
layout: post
title: "Betrayed by DNS"
date: 2025-02-09
features: [highlight]
---

Many things can go wrong when you shard a MongoDB cluster under heavy load. DNS issues did not make it anywhere near the top of that list, yet they somehow ended up being the most problematic. My illusion that systems automatically handled all the details of DNS by default was shattered.

## Background

We were sharding our MongoDB deployment because it only had a month of storage headroom left and could not keep up with the update-heavy workload. The managed MongoDB Atlas service makes the actual sharding operation fairly straightforward. First, convert the deployment to one with a single shard. Then, redeploy all services to ensure that they connect to the `mongos` instances. Finally, increase the number of shards and run `sh.shardCollection()` on the desired collections.

Our services connect to MongoDB using Prisma, which relies on `mongo-rust-driver`[^prisma] under the hood. They are deployed on EC2 nodes through ECS. We tested the entire operation in staging, and everything seemed to work without any downtime. As you can already guess, the production migration did not go as smoothly.

## One to Two

When we increased the number of shards from one to two, a mysterious new error started showing up in our services (reformatted slightly for easier viewing).

```text
Error in connector: error creating a database connection.
(Kind: An error occurred during DNS resolution: no record found for Query {
  name: Name("_mongodb._tcp.***.***.mongodb.net.ec2.internal."),
  query_type: SRV,
  query_class: IN
}, labels: {})
```

This was quite concerning because it seemed like our services could not resolve the DNS for the cluster and were failing to connect to the database entirely. We made a few immediate observations.

- The error only occurred on a small fraction of nodes.
- The error spiked during deploys and then subsided over time. However, it never fully went away.
- The error was not isolated to a particular service or subnet.

### Large SRV Records

At this point, it definitely seemed like there was some transient error resolving DNS records. However, it wasn't immediately clear what changed about those records that could have caused this. We found two nodes in the same subnet, one which had issues connecting and one which did not. Then, we connected to those machines directly to debug.

MongoDB connection strings for modern drivers start with `mongodb+srv://` and do not specify the addresses of individual nodes in the cluster. This is flexible, but requires drivers to perform a lookup of the SRV records for the cluster followed by lookups of A records for individual nodes in the response[^srv]. Below is an example output of the SRV records from the working machine. The command hangs on the non-working machine with a timeout error.

```text
~$ nslookup -q=SRV _mongodb._tcp.***.***.mongodb.net
;; Truncated, retrying in TCP mode.
Server:   10.0.0.2
Address:  10.0.0.2#53

Non-authoritative answer:
_mongodb._tcp.***.***.mongodb.net  service = 0 0 27016 ***-00-00.***.mongodb.net.
_mongodb._tcp.***.***.mongodb.net  service = 0 0 27016 ***-00-01.***.mongodb.net.
_mongodb._tcp.***.***.mongodb.net  service = 0 0 27016 ***-00-02.***.mongodb.net.
_mongodb._tcp.***.***.mongodb.net  service = 0 0 27016 ***-01-00.***.mongodb.net.
_mongodb._tcp.***.***.mongodb.net  service = 0 0 27016 ***-01-01.***.mongodb.net.
_mongodb._tcp.***.***.mongodb.net  service = 0 0 27016 ***-01-02.***.mongodb.net.
```

Something that immediately caught our attention was the `Truncated` part. Why was the SRV record getting truncated? It turns out that the resolver first tries to query over UDP, but because the response is larger than 512 bytes, it can be truncated. This signals to the resolver to retry over TCP, which succeeds. Now, it became clear what change caused the errors. By increasing the number of shards from one to two, the SRV records became larger than 512 bytes, and this led to transient SRV record lookup failures.

### DNS Rate Limits

We still had not gotten to the root cause of why lookups of large DNS records over TCP sometimes failed. We suspected that there might be some rate limit in effect. After all, we had recently switched to very large EC2 nodes to save on Datadog host costs. Each node could be home to more than 50 isolated application processes. After some searching, we came upon a relevant AWS post.

> Amazon-provided DNS servers enforce a limit of 1024 packets per second per elastic network interface. Amazon provided DNS servers reject any traffic exceeding this limit.[^limit]

This could be it! A DNS lookup over TCP likely consumes more than 5 times the number of packets compared to that of a lookup over UDP due to overhead from the TCP handshake and ACKs. We did not see any dropped packets due to PPS rate allowance for the ENA. However, we still suspected that DNS lookups were being rate limited since there were few alternative explanations.

The recommended solution was to enable DNS caching, which I had assumed was already enabled given that we were using Amazon Linux 2023 as the AMI, and Amazon has rate limits for their default DNS configuration.

### Docker DNS Caching

Fortunately, there is a great post[^still] that describes this exact issue with Amazon Linux 2023. It turns out that `systemd-resolved` (which can perform DNS caching) is installed, but disabled by default. We use a user data script to initialize the EC2 instances. Below is an example addition that enables DNS caching through a local stub resolver. 

```bash
# Enable the stub listener.
rm /usr/lib/systemd/resolved.conf.d/resolved-disable-stub-listener.conf
systemctl restart systemd-resolved

# Link the stub resolver configuration to /etc/resolv.conf.
ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
```

Now, looking at `/etc/resolv.conf`, we see that the nameserver is `127.0.0.53`. This indicates that DNS queries should be going through the local stub resolver and getting cached. We did some tests on the nodes to ensure that DNS resolution continued to work correctly and that there were cache hits.

When we rolled out this change out to staging, there was a massive spike of errors from services failing to connect to Elasticache and other services on AWS. This time, it affected all services in a persistent manner. It seemed like enabling DNS caching somehow made it so that services could no longer resolve addresses in private subnets.

We tested the resolution of those addresses on the nodes, so why are the services unable to resolve them? It turns out that Docker uses a different DNS configuration from that of the host[^docker]. In particular, it will copy the host's `/etc/resolv.conf`, exclude any local nameservers, then add default public DNS servers if there are nameservers remaining. The solution is to ensure that the local stub resolver also listens on the `docker0` interface and configure Docker to use that DNS server.

```bash
# Get the address of the Docker bridge interface.
systemctl start docker
DOCKER_BRIDGE_IP=$(ip addr show docker0 | grep -Po 'inet \K[\d.]+')

# Enable the stub listener and ensure it also listens on the bridge interface.
rm /usr/lib/systemd/resolved.conf.d/resolved-disable-stub-listener.conf
echo "DNSStubListenerExtra=${DOCKER_BRIDGE_IP}" | tee -a /etc/systemd/resolved.conf
systemctl restart systemd-resolved

# Create a copy of the stub resolver configuration so we can add a nameserver that
# Docker can use when it copes the host's /etc/resolv.conf.
cp /run/systemd/resolve/stub-resolv.conf /etc/stub-resolv.conf
echo "nameserver ${DOCKER_BRIDGE_IP}" | tee -a /etc/stub-resolv.conf

# Link the updated stub resolver configuration to /etc/resolv.conf.
ln -sf /etc/stub-resolv.conf /etc/resolv.conf

# Restart Docker to ensure changes are picked up.
systemctl restart docker
```

After deploying this change to all of the nodes, DNS resolution errors fully subsided. Alternatively, we could have specified the DNS address for Docker through ECS container definitions, but this would have been much harder to deploy alongside the DNS caching changes to the underlying nodes. The above script requires no modification to existing container definitions and could be rolled back by cancelling the instance refresh.


## Two to Four

## References

[^prisma]: Github Discussions (2022). [What mongodb driver does Prisma use?](https://github.com/prisma/prisma/discussions/12886).
[^srv]: Drumgoole, Joe (2021). [MongoDB 3.6: Here to SRV you with easier replica set connections](https://www.mongodb.com/developer/products/mongodb/srv-connection-strings/).
[^truncation]: MyF5 (2021). [K91537308: Overview of the truncating rule when DNS response size is over 512 Bytes](https://my.f5.com/manage/s/article/K91537308).
[^limit]: AWS re:Post (2024). [How can I determine whether my DNS queries to the Amazon-provided DNS server are failing due to VPC DNS throttling?](https://repost.aws/knowledge-center/vpc-find-cause-of-failed-dns-queries).
[^still]: Still, Michael (2024). [Amazon Linux 2023, DNS, and systemd-resolved — a story of no caching](https://www.madebymikal.com/amazon-linux-2023-dns-and-systemd-resolved-a-story-of-no-caching/).
[^docker]: Stack Overflow (2016). [Docker cannot resolve DNS on private network [closed]](https://stackoverflow.com/questions/39400886/docker-cannot-resolve-dns-on-private-network).