---
layout: post
title: "Dual-Client Migration Patterns"
date: 2024-01-14
---

It is often said that all problems in computer science can be solved by another level of indirection. In the case of migrations, I have found this to a surprisingly accurate aphorism. By introducing an additional layer in client logic that conditionally routes to traffic to two different targets, we can perform migrations for a variety of different scenarios in a safe and transparent manner.

## Background

I have worked on various migrations over the last few years at my job. Although they are certainly not the most exciting tasks in software engineering (in my opinion), I think they present interesting challenges when done safely at scale. I wanted to share three different scenarios spanning different types of online migrations. The common thread is that they all use two clients managed at the application level. While it is possible in some cases to perform migrations at the network or load balancer layer, there are distinct advantages to the dual-client approach that we will discuss in individual sections.

## Cluster Migration



## Redis Migration

## Database Migration