---
layout: post
title: "Compressing Sentry Ownership Rules"
date: 2023-11-24
---

I had to solve a fun problem at work related to Sentry's ownership rules because my changes put us over the character limit. It felt very much like an interview problem. However, I think the ideal implementation is not one which has the optimal time complexity or compression ratio.

## Background

To understand the problem I was facing, we first have to understand what ownership rules are and how our project managed to reach the (somewhat arbitrary) character limit in the first place. 

For a given project, Sentry allows you to define a set of ownership rules to automatically route issues to appropriate teams based on a few attributes. This is particularly useful for platform services that many other teams build on top of. For example, while the platform layer of our API service was owned one team, the individual API routes were owned by many different product teams.

Instead of manually defining the ownership rules, we generated them from our own internal CLI tool that relied on configuration data that looked very similar to CODEOWNERS files.