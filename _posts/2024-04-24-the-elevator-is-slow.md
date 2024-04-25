---
layout: post
title: "The Elevator Is Slow"
date: 2024-04-24
features: [chart, highlight]
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

This algorithm is not the one that results in the lowest request latency, but is very close to the observed behavior of the elevator system in my building. There are some efficiency tradeoffs that have been made. For example, it is possible for a stopped elevator which is closer to a requested floor to not activate at all because another moving elevator is targeting the same floor. Empirically, this performs very well (within 5% for both mean and max latencies for tested distributions) compared to having no efficiency optimizations. 

## Implementation

We describe a few key details of the simulation and its modelling in SimPy. The full implementation can be found [here](https://github.com/bobbyluig/bobbyluig.github.io/blob/main/content/the-elevator-is-slow/elevator.py). Note that this is not thoroughly tested, so there could be small bugs that affect the behavior of the simulation. However, the implementation seems to behave reasonably on a few small examples as well as the requested distributions used in the analysis.

### Parameters

There is a set of parameters that we want to model and tune when performing simulation analysis. The initial values are chosen based on a rough estimate of what they are in my building's elevator system. For simplicity, some parameters are reciprocals of their normal units.

| Parameter                  | Description                                                                           | Value |
|----------------------------|---------------------------------------------------------------------------------------|-------|
| `k_building_floors`        | The number of floors in the building.                                                 | 20    |
| `k_elevator_acceleration`  | The penalty in seconds for the elevator to stop or start moving.                      | 1.5   |
| `k_elevator_capacity`      | The capacity of each elevator.                                                        | 10    |
| `k_elevator_count`         | The number of elevators in the building.                                              | 2     |
| `k_elevator_door_velocity` | The number of seconds it takes the door to open or close.                             | 3     |
| `k_elevator_door_wait`     | The number of seconds the door will wait before closing after door sensor is tripped. | 5     |
| `k_elevator_velocity`      | The number of seconds for the elevator to travel one floor.                           | 1.5   |
| `k_person_velocity`        | The average number of seconds it takes for a person to get in or out of the elevator. | 1     |
| `k_request_rate`           | The average number of seconds between requests.                                       | 60    |

### Modelling

There are four distinct objects that we model in the simulation: `Request`, `Elevator`, `Building`, and `Controller`. We describe each in more detail.

- A request contains the start and end floors. It also keeps track of the start and end simulation times corresponding to when it began waiting for the elevator to when it exited on the destination floor.
- An elevator maintains state about which buttons are pressed, which floor it is currently on, which direction it is heading, which floor it is heading to, the requests that are currently inside, etc. Most of the metadata is used by the controller to make routing decisions.
- The building maintains state about which directional buttons are pressed and which requests are waiting on each floor. It does not keep track of elevators.
- The controller contains all elevators and the building. It interacts with the environment to operate the elevators and update any relevant state. In addition, the controller has a method which allows it to accept requests.

In addition, we also need to model the request distribution and input format. It is easier to reason about repeatability if we materialize the sequence of requests prior to starting the simulation. Therefore, we first generate all requests and corresponding start times according to the following distribution (which is a very rough approximation of what I assume people in the building do).

- With 45% probability, a request starts on the first floor and ends on a random residential floor.
- With 45% probability, a request starts on a random residential floor and ends on the first floor.
- With 5% probability, a request starts on a random residential floor and ends on a random non-residential floor.
- With 5% probability, a request starts on a random non-residential floor and ends on a random residential floor.

```python
def run_requests(
    env: simpy.Environment,
    controller: Controller,
    requests: List[Tuple[float, Request]],
):
    for start_time, request in requests:
        yield env.timeout(start_time - env.now)
        controller.new_request(request)

if __name__ == "__main__":
    env = simpy.Environment()
    building = Building()
    elevators = [Elevator() for _ in range(k_elevator_count)]
    controller = Controller(env, building, elevators)

    for i in range(len(elevators)):
        env.process(controller.run_elevator(i))
    env.process(run_requests(env, controller, random_requests(100000)))
    env.run()
```

Given the list of input requests, it is fairly straightforward to run the entire simulation. We just need to wait until the start time of each request before sending it to the controller. An example snippet above shows the high level setup where we first run the control loop for each elevator in a separate process before starting a final process to send the requests.  

### Control Loop

The main control loop for each elevator involves evaluating a policy and choosing one of three actions to take. A snippet of this is shown below. The policy is currently just the multi-elevator control algorithm described before, but could be any arbitrary function that examines the state of the system and outputs an action.

```python
@dataclass
class Action_Arrive:
    direction: int

@dataclass
class Action_Move:
    floor: int

@dataclass
class Action_Stop:
    pass

def run_elevator(self, elevator_index: int):
    while True:
        action = self.policy(elevator_index)
        match action:
            case Action_Arrive():
                yield from self.action_arrive(elevator_index, action)
            case Action_Move():
                yield from self.action_move(elevator_index, action)
            case Action_Stop():
                yield from self.action_stop(elevator_index, action)
```

One important implementation detail is that elevators operate one floor at a time. This makes the `Move` action discrete such that it is not possible to interrupt an elevator while it is moving between floors. However, the controller will reevaluate the target of an elevator once it completes the `Move` action. This should be a close enough approximation of what happens in a real elevator system.

When an elevator arrives at a target floor, it is necessary to specify a direction to the `Arrive` action. This is because buttons in the building are directional, and requests will only board the elevator if it is heading in the right direction. In our implementation, the `Arrive` action also handles moving any requests in and out of the elevator.

### Stop Events

When an elevator no longer has any requests that it needs to serve, it will stop on the current floor. However, in discrete event simulation, we need a way to signal to the control loop that the elevator should resume operation. SimPy offers an event mechanism that allows us to handle this scenario without polling.

```python
def action_stop(self, elevator_index: int, action: Action_Stop):
    # ...
    yield self.wake_events[elevator_index]

def new_request(self, request: Request):
    # ...
    for i, wake_event in enumerate(self.wake_events):
        wake_event.succeed()
        self.wake_events[i] = self.env.event()
    # ...
```

Each elevator is associated with a wake event. When an elevator runs the `Stop` action, it yields the event, which effectively pauses the control loop until the event is triggered. On any new request, wake events for all of the elevators are triggered to resume their control loops. We then recreate the events since an event can only be triggered once. Note that it may be possible for an elevator to immediately stop again after resuming because it does not need to serve the new request.

### Capacity

When an elevator is full, it can no longer serve additional requests. However, it must continue to stop on floors along its direction since capacity is observed by requests and not by the controller. For simplicity, we model this in the `Arrive` action. We assume that requests are well-behaved and will wait for the elevator to depart before re-pressing the button on the floor.

```python
def action_arrive(self, elevator_index: int, action: Action_Arrive):
    # ...
    if at_capacity:
        def skip_floor(buttons, floor, direction):
            yield self.env.timeout(0)
            buttons[floor] = self.needs_button(direction, floor)

        self.env.process(skip_floor(buttons, floor, direction))
    # ...
```

We can implement this by creating a new process that re-presses the same directional button after the elevator leaves this floor. The timeout is necessary because the current process should not see the button pressed when deciding which floor to go to next. Otherwise, we get stuck in an infinite loop. In this case, `buttons` is already associated with a direction. Note that it is not always necessary to press the button again because in rare cases, a different elevator can service the request.

### Door Interruption

There are cases where a request arrives while the elevator door is waiting to close. When this happens, we assume that the timer for the door resets (usually because someone holds the door open). This is not a hard concept to describe, but it is somewhat interesting to implement in the SimPy framework.

```python
def interrupt_door(self, elevator_index: int):
    elevator = self.elevators[elevator_index]
    process = self.door_processes[elevator_index]

    if elevator.count < k_elevator_capacity and process is not None:
        process.interrupt()

def action_arrive(self, elevator_index: int, action: Action_Arrive):
    # ...
    while True:
        # ...
        try:
            door_close_event = self.env.event()

            def wait_door_close():
                try:
                    yield self.env.timeout(k_elevator_door_wait)
                    door_close_event.succeed()
                except simpy.Interrupt as e:
                    door_close_event.fail(e)
                finally:
                    self.door_processes[elevator_index] = None

            self.door_processes[elevator_index] = self.env.process(
                wait_door_close()
            )
            yield door_close_event

            # ...
            break
        except simpy.Interrupt:
            pass
    # ...
```

We rely on the fact that processes can be interrupted. However, timers are not processes in SimPy, so we need to wrap them in a process in order to interrupt the wait. The `Arrive` action creates a new event that it waits on. It also starts a process that succeeds the event after the timeout, or fails the event with an interrupt exception if the process was interrupted. If the timeout runs without interrupt, then we break out of the while loop. Otherwise, we catch the exception and continue attempting to move requests from the current floor into the elevator.

## Analysis

With the simulation built, we can now analyze various aspects of the elevator system. Unless otherwise stated, we use 100k requests drawn from the previously described distribution with a fixed seed for all of the experiments below.

### Floor Latency

It is interesting to see how living on different floors of the building affect the overall time spent in the elevator. We show the mean and max latencies of requests grouped by each floor (i.e., requests that start or end at a given floor fall into the group for that floor). 

{% raw %}
<div class="chart"><canvas id="chart-floor-latency-mean-max"></canvas></div>
<script>
  document.addEventListener('DOMContentLoaded', () => {
    new Chart(document.getElementById('chart-floor-latency-mean-max'), {
      type: 'bar',
      data: {
        labels: [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
        datasets: [
          {
            label: 'Mean',
            data: [38.70291918383377, 40.68860665516036, 42.65609258123861, 44.76554586575107, 46.471043307795675, 48.44538091897792, 50.26455864726403, 53.00678411862765, 54.41530391970092, 56.719102754388146, 58.70396701055558, 61.101082047403814, 63.86222393886232, 66.62162959382948, 68.47235843364575, 71.62452590066998, 74.07766553082584],
          },
          {
            label: 'Max',
            data: [133.37152319849702, 149.5396094409516, 149.52741525904275, 159.82521815155633, 148.14974494627677, 141.87939180643298, 138.72756127710454, 174.47362796554808, 157.35112143610604, 168.0848355323542, 145.21891872095875, 156.69267152022803, 178.90530922776088, 180.5266194837168, 176.50148904777598, 186.59320912277326, 183.14009668445215],
          },
        ]
      },
      options: {
        scales: {
          x: {
            title: {
              display: true,
              text: 'Floor',
            },
          },
          y: {
            beginAtZero: false,
            title: {
              display: true,
              text: 'Latency (s)',
            },
          },
        },
      }
    });
  });
</script>
{% endraw %}

There is around half a minute of difference in the mean request latencies between floor 3 and floor 20, with each floor contributing around 2.2 seconds. The relationship between max latency and floor is not as clear, but it is generally increasing as we go up in the building. Max latencies are also fairly sensitive to the exact sequence of requests and could increase a bit if we simulated more requests.

{% raw %}
<div class="chart"><canvas id="chart-floor-latency-histogram"></canvas></div>
<script>
  document.addEventListener('DOMContentLoaded', () => {
    new Chart(document.getElementById('chart-floor-latency-histogram'), {
      type: 'bar',
      data: {
        labels: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180],
        datasets: [
          {
            label: 'Floor 4',
            data: [4, 1636, 1453, 974, 463, 237, 121, 53, 36, 8, 5, 6, 4, 0, 0, 0, 0, 0],
          },
          {
            label: 'Floor 12',
            data: [0, 2, 1014, 1364, 1153, 638, 342, 217, 131, 73, 39, 15, 9, 1, 2, 0, 0, 0],
          },
          {
            label: 'Floor 20',
            data: [0, 0, 0, 659, 846, 923, 995, 538, 428, 233, 177, 98, 42, 36, 20, 2, 2, 1],
          },
        ]
      },
      options: {
        scales: {
          x: {
            title: {
              display: true,
              text: 'Latency (s)',
            },
          },
          y: {
            title: {
              display: true,
              text: 'Count',
            },
          },
        },
      }
    });
  });
</script>
{% endraw %}

In the histogram above, we show the latencies of the middle 5k requests (when the system is closer to steady state) for the lowest, middle, and highest residential floors. The fastest way for a request to be fulfilled is for an elevator to already be on the starting floor, accept one request, and then for the elevator to travel to the ending floor uninterrupted. We do see a small percentage of requests that get fairly close to the theoretical minimum latency for their floors.

### Elevator Count

There are frequently residents moving in to or out of the building. When that happens, one of the two elevators becomes reserved for a few hours and cannot be used for serving normal requests. We show the request latencies as a function of the number of elevators in the chart below. Mean and max values are computed from all requests regardless of starting and ending floor.

{% raw %}
<div class="chart"><canvas id="chart-elevator-count"></canvas></div>
<script>
  document.addEventListener('DOMContentLoaded', () => {
    new Chart(document.getElementById('chart-elevator-count'), {
      type: 'bar',
      data: {
        labels: [1, 2, 3, 4, 5],
        datasets: [
          {
            label: 'Mean',
            data: [117.954068641431, 55.29700344923757, 46.57176647707238, 44.015681663871305, 42.75975713609125],
          },
          {
            label: 'Max',
            data: [414.3429391204845, 186.59320912277326, 157.90575060830452, 141.0790516170673, 138.57926610531285],
          },
        ]
      },
      options: {
        scales: {
          x: {
            title: {
              display: true,
              text: 'Number of Elevators',
            },
          },
          y: {
            title: {
              display: true,
              text: 'Latency (s)',
            },
          },
        },
      }
    });
  });
</script>
{% endraw %}

We see that there are diminishing returns when using more than two elevators, but only having one elevator increases both the mean and max latencies by more than a factor of two. This definitely matches my empirical observations of occasionally having to wait a few minutes before the elevator will even arrive on my floor if the other elevator is reserved.

### System Throughput

We can find the max throughput of the elevator system by comparing the mean request latencies between 200k requests and 100k requests. Below the threshold, we expect the ratio to be close to one. Above the threshold, we expect the ratio to be much larger than one because requests are arriving faster than the system can process them. As a result, more simulated requests lead to higher mean latencies.

{% raw %}
<div class="chart"><canvas id="chart-system-throughput"></canvas></div>
<script>
  document.addEventListener('DOMContentLoaded', () => {
    new Chart(document.getElementById('chart-system-throughput'), {
      type: 'bar',
      data: {
        labels: [20, 19, 18, 17, 16, 15],
        datasets: [
          {
            label: 'Dataset',
            data: [
              186.1835094959234 / 186.31329990812952,
              215.82737066987357 / 214.49205722318948,
              304.7135737046539 / 306.52797741267506,
              26585.631230024308 / 12543.125026929107,
              93040.87735298941 / 45249.710744333715,
              160528.16941428368  /79523.81772432546,
            ],
          },
        ]
      },
      options: {
        scales: {
          x: {
            title: {
              display: true,
              text: 'Mean Time Between Requests (s)',
            },
          },
          y: {
            beginAtZero: false,
            title: {
              display: true,
              text: 'Ratio',
            },
          },
        },
      }
    });
  });
</script>
{% endraw %}

We see that from the chart above that the max throughput is around 18 seconds between requests, or 3.33 requests per minute for the default parameters. At this rate, each request takes an average of 5 minutes to get from the starting floor to the ending floor. If we assume that the building has around 200 residents, and all of them need to use the elevator within a one hour window, then we actually get fairly close to the max throughput of the system.

### Parameter Impact

One last analysis that we want to perform is to see which parameter has the largest impact on mean request latency. To measure this, we will double or halve parameters in a direction that reduces latency and compare the their mean request latencies against the baseline. The results are shown in the chart below and sorted based on latency reduction.

{% raw %}
<div class="chart"><canvas id="chart-system-parameter"></canvas></div>
<script>
  document.addEventListener('DOMContentLoaded', () => {
    new Chart(document.getElementById('chart-system-parameter'), {
      type: 'bar',
      data: {
        labels: ['e_vel','e_d_vel',  'e_d_wai', 'e_acc', 'p_vel', 'e_cap'],
        datasets: [
          {
            label: 'Dataset',
            data: [
              37.8393639353616 / 55.29700344923757, 
              47.448846883705926 / 55.29700344923757,
              49.923684426869826 / 55.29700344923757,
              50.897573266073756 / 55.29700344923757,
              53.39151825313947 / 55.29700344923757,
              55.29700344923757 / 55.29700344923757,
            ],
          },
        ]
      },
      options: {
        scales: {
          x: {
            title: {
              display: true,
              text: 'Parameter',
            },
          },
          y: {
            beginAtZero: false,
            title: {
              display: true,
              text: 'Ratio',
            },
          },
        },
      }
    });
  });
</script>
{% endraw %}

Increasing the velocity of the elevator helps the most. This makes sense since a majority of each trip is spent waiting for the elevator to travel between floors. Increasing the capacity is not effective because there are no cases for the default distribution and arrival rate where the elevator is full. Surprisingly, reducing the wait time of the elevator door by half decreases the mean request latency by around 10%. This is actually something that we can adjust in the real world by pressing the door close button!

## References

[^simpy]: Team SimPy (2023). [Simpy documentation](https://simpy.readthedocs.io/en/latest/).
[^dispatch]: Elevatorpedia (2024). [Destination dispatch](https://elevation.fandom.com/wiki/Destination_dispatch).
[^scan]: Wikipedia (2024). [Elevator algorithm](https://en.wikipedia.org/wiki/Elevator_algorithm).
[^look]: Wikipedia (2024). [LOOK algorithm](https://en.wikipedia.org/wiki/LOOK_algorithm).
