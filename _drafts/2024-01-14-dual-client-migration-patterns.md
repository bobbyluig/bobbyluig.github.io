---
layout: post
title: "Dual-Client Migration Patterns"
date: 2024-01-14
---

It is often said that all problems in computer science can be solved by another level of indirection. In the case of migrations, I have found this to a surprisingly accurate aphorism. By introducing an additional layer in client logic that conditionally routes to traffic to two different targets, we can perform migrations for a variety of different scenarios in a safe and transparent manner.

### 