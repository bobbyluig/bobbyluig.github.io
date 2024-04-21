---
layout: post
title: "The Elevator Is Slow"
date: 2024-04-20
features: [highlight]
---

I live in a 20-story building with two elevators, and sometimes it seems like they take forever to show up. After missing the bus multiple times due to unexpectedly long waits for the elevator, I decided to write a simulation to better understand the source of my misery.

## Setup

We are interested in creating a detailed discrete-event simulation of multiple elevators in a n-story building with various parameters to experiment with. To that end, we will use SimPy[^simpy] as the underlying simulation framework.

Although there are many types of elevator setups, we are mainly concerned with ones where there are both up and down buttons on each floor with no destination dispatch system[^dispatch]. All elevators service all floors, and there is no preferential treatment of different floors (i.e., the controller does not assume a distribution of requests and optimize based on that). This is effectively the setup of my building, but I think it is also fairly common for mid-rise to high-rise buildings (excluding skyscrapers).

In order for us to get meaningful simulation results, we need to establish the input request distribution (i.e., how often people need to use the elevator and what floors they are trying to get to). My building is somewhat interesting in that the second and third floors only contain amenities. Therefore, the likelihood of requests starting or ending there is much less than that of other floors. We assume that requests are equally likely to be up or down with arrival times following a poisson distribution. However, for simplicity (and because I never do this), no requests start and end at residential floors.

## Algorithm

We first summarize a simple routing algorithm that works for a single elevator and then extend it to the multi-elevator case with directional buttons.

### Single Elevator

### Multiple Elevators

## Implementation

## Analysis

## References

[^simpy]: Team SimPy (2023). [Simpy documentation](https://simpy.readthedocs.io/en/latest/).
[^dispatch]: Elevatorpedia (2024). [Destination dispatch](https://elevation.fandom.com/wiki/Destination_dispatch).
