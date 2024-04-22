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

For a single elevator, the problem of servicing requests is remarkably similar to hard disk scheduling, so much so that the SCAN[^scan] scheduling algorithm is also named the elevator algorithm. However, for efficiency reasons, elevators do not scan all the way up and down the building continually to service requests. Instead, they more closely follow the LOOK[^look] scheduling algorithm, which we describe in more detail here.

1. The elevator starts on any floor and remains stationary until there is a request.
2. On receiving a request, the elevator adopts a direction based on that request.
3. The elevator continues to move in that direction until there are no more requests in that direction. It will stop to service any requests along the way that are traveling in the same direction.
4. If there are requests in the other direction after one direction is fully serviced, the elevator switches directions. Otherwise, it stops on the current floor until there is a request.

Note that this is not necessarily the most optimal way to handle any request distribution, but it is fairly simple to implement and avoids starvation. To handle directional buttons, we just need to tweak the algorithm so that the elevator will only stop on a floor if there is a button pressed in the same direction of travel (e.g., an elevator going up will not stop on a floor with the down button pressed).

### Multiple Elevators

Initially, it may seem like the multi-elevator case is a lot more complex. However, there are constraints that make this problem simpler. A moving elevator must generally follow the same algorithm described before for the single elevator case. It would be frustrating if an elevator passed through a floor but did not let passengers on or off. Therefore, we only need to consider scenarios where an elevator is not already moving in a direction (i.e., it is not actively servicing requests). Otherwise, each elevator in the multi-elevator case behaves as if it were the only elevator.

When multiple elevators are stopped, the controller should pick the elevator that is closest to a new request to use, since that would minimize travel time. We would also like to not send multiple elevators to service the same floor and direction. Therefore, if a stopped elevator sees that another elevator is already heading to the same floor with the same direction that it would, it will remain stopped. The only exception is that if the stopped elevator is on the same floor as the request, then it should service it regardless (to reduce the frustration of seeing an elevator on your floor, but for it to not open).

This algorithm is not the one that results in the lowest request latency, but is very close to the observed behavior of the elevator system in my building. There are some efficiency tradeoffs that have been made. For example, it is possible for a stopped elevator which is closer to a requested floor to not activate at all because another moving elevator is targeting the same floor. Empirically, this performs very well (within 5% for both mean and max latency for tested distributions) compared to having no efficiency optimizations. 

## Implementation

We describe a few key details of the simulation and its modelling in SimPy. The full implementation can be found [here](https://github.com/bobbyluig/bobbyluig.github.io/blob/main/content/the-elevator-is-slow/elevator.py). 

### Parameters

There is a set of parameters that we want to model and tune when performing simulation analysis. The initial values are chosen based on a rough estimate of what they are in my building's elevator system. For simplicity, some parameters are reciprocals of their normal units.

| Parameter                  | Description                                                                           | Value |
|----------------------------|---------------------------------------------------------------------------------------|-------|
| `k_building_floors`        | The number of floors in the building.                                                 | 20    |
| `k_elevator_acceleration`  | The penalty in seconds for the elevator to stop or start moving.                      | 1     |
| `k_elevator_capacity`      | The capacity of each elevator.                                                        | 10    |
| `k_elevator_count`         | The number of elevators in the building.                                              | 2     |
| `k_elevator_door_velocity` | The number of seconds it takes the door to open or close.                             | 3     |
| `k_elevator_door_wait`     | The number of seconds the door will wait before closing after door sensor is tripped. | 5     |
| `k_elevator_velocity`      | The number of seconds for the elevator to travel one floor.                           | 1     |
| `k_person_velocity`        | The average number of seconds it takes for a person to get in or out of the elevator. | 0.5   |
| `k_request_rate`           | The average number of seconds between requests.                                       | 60    |

### Modelling

### Control Loop

### Stop Events

### Capacity

### Door Interruption

## Analysis

## References

[^simpy]: Team SimPy (2023). [Simpy documentation](https://simpy.readthedocs.io/en/latest/).
[^dispatch]: Elevatorpedia (2024). [Destination dispatch](https://elevation.fandom.com/wiki/Destination_dispatch).
[^scan]: Wikipedia (2024). [Elevator algorithm](https://en.wikipedia.org/wiki/Elevator_algorithm).
[^look]: Wikipedia (2024). [LOOK algorithm](https://en.wikipedia.org/wiki/LOOK_algorithm).
