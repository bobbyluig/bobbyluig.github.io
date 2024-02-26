import simpy
from typing import cast, Any, List, Union, Generator
import random


class Elevator:
    def __init__(self, env: simpy.Environment, floors: int) -> None:
        """
        Creates a new elevator.
        """
        self._env: simpy.Environment = env
        self._k_speed: float = 1.0
        self._k_delay: float = 10.0
        self._floor: int = 0
        self._floors: int = floors
        self._direction: int = 0
        self._buttons: List[bool] = [False] * self._floors
        self._events: List[List[simpy.Event]] = [[] for _ in range(self._floors)]

    def press_button(self, floor: int) -> simpy.Event:
        self._buttons[floor] = True
        wait_event = self._env.event()
        self._events[floor].append(wait_event)
        return wait_event
    
    def enter(self) -> simpy.Event:
        wait_event = self._env.event()
        self._events[self._floor].append(wait_event)
        return wait_event

    def move(self, direction: int):
        self._direction = direction
        yield self._env.timeout(1 / self._k_speed)
        self._floor += self._direction

    def stop(self):
        self._direction = 0

    def floor(self):
        return self._floor

    def direction(self):
        return self._direction
    
    def flip_direction(self):
        self._direction *= -1
    
    def open_close_doors(self):
        self._buttons[self._floor] = False
        yield self._env.timeout(self._k_delay / 2)
        for event in self._events[self._floor]:
            event.succeed()
        self._events[self._floor] = []
        yield self._env.timeout(self._k_delay / 2)

    def next_floor_above(self) -> Union[int, None]:
        """
        Returns the first floor where the button pressed is equal or above the specified floor.
        """
        for test_floor in range(self._floor, self._floors):
            if self._buttons[test_floor]:
                return test_floor
        return None

    def next_floor_below(self) -> Union[int, None]:
        """
        Returns the first floor where the button is pressed equal or below the specified floor.
        """
        for test_floor in reversed(range(self._floor + 1)):
            if self._buttons[test_floor]:
                return test_floor
        return None


class Building:
    def __init__(
        self, env: simpy.Environment, floors: int, elevators: List[Elevator]
    ) -> None:
        """
        Creates a new building with the specified number of floors and elevators.
        """
        self._env: simpy.Environment = env
        self._floors: int = floors
        self._up_buttons: List[bool] = [False] * self._floors
        self._down_buttons: List[bool] = [False] * self._floors
        self._elevators: List[Elevator] = elevators
        self._wake_event: simpy.Event = self._env.event()
        self._up_events: List[List[simpy.Event]] = [[] for _ in range(self._floors)]
        self._down_events: List[List[simpy.Event]] = [[] for _ in range(self._floors)]

    def run(self):
        while True:
            elevator = self._elevators[0]

            next_elevator_floor_above = elevator.next_floor_above()
            next_elevator_floor_below = elevator.next_floor_below()
            next_building_floor_above = self.next_floor_above(elevator.floor())
            next_building_floor_below = self.next_floor_below(elevator.floor())
            any_up_floor = self.next_floor_above(0)
            any_down_floor = self.next_floor_below(self._floors - 1)

            floor = None

            if elevator.direction() >= 0:
                if (
                    next_elevator_floor_above is not None
                    and next_building_floor_above is not None
                ):
                    floor = min(next_elevator_floor_above, next_building_floor_above)
                elif next_elevator_floor_above is not None:
                    floor = next_elevator_floor_above
                elif next_building_floor_above is not None:
                    floor = next_building_floor_above
            elif elevator.direction() <= 0:
                if (
                    next_elevator_floor_below is not None
                    and next_building_floor_below is not None
                ):
                    floor = max(next_elevator_floor_below, next_building_floor_below)
                elif next_elevator_floor_below is not None:
                    floor = next_elevator_floor_below
                elif next_building_floor_below is not None:
                    floor = next_building_floor_below

            if floor is None:
                if any_up_floor is not None and any_down_floor is not None:
                    floor = max(any_up_floor, any_down_floor)
                elif any_up_floor is not None:
                    floor = any_up_floor
                elif any_down_floor is not None:
                    floor = any_down_floor

            if elevator.floor() == floor:
                if elevator.direction() >= 0:
                    if (
                        next_building_floor_above is not None
                        or next_elevator_floor_above is not None
                    ):
                        self.arrive_up(elevator, elevator.floor())
                    else:
                        elevator.flip_direction()
                        self.arrive_down(elevator, elevator.floor())
                elif elevator.direction() <= 0:
                    if (
                        next_building_floor_below is not None
                        or next_elevator_floor_below is not None
                    ):
                        self.arrive_down(elevator, elevator.floor())
                    else:
                        elevator.flip_direction()
                        self.arrive_up(elevator, elevator.floor())
                yield self._env.process(elevator.open_close_doors())
            elif floor is not None:
                direction = 1 if elevator.floor() < floor else -1
                yield self._env.process(elevator.move(direction))
            else:
                elevator.stop()
                yield self._wake_event

    def floors(self) -> int:
        """
        Returns the number of floors in the building.
        """
        return self._floors

    def press_up_button(self, floor: int) -> simpy.Event:
        """
        Presses the up button for the floor.
        """
        self._up_buttons[floor] = True
        wait_event = self._env.event()
        self._up_events[floor].append(wait_event)
        self._wake_event.succeed()
        self._wake_event = self._env.event()
        return wait_event

    def press_down_button(self, floor: int) -> simpy.Event:
        """
        Presses the down button for the floor.
        """
        wait_event = self._env.event()
        self._down_buttons[floor] = True
        self._down_events[floor].append(wait_event)
        self._wake_event.succeed()
        self._wake_event = self._env.event()
        return wait_event

    def arrive_up(self, elevator: Elevator, floor: int) -> None:
        """
        Indicates an elevator arrived at the floor going up.
        """
        self._up_buttons[floor] = False
        for event in self._up_events[floor]:
            event.succeed(elevator)
        self._up_events[floor] = []

    def arrive_down(self, elevator: Elevator, floor: int) -> None:
        """
        Indicates an elevator arrived at the floor going down.
        """
        self._down_buttons[floor] = False
        for event in self._down_events[floor]:
            event.succeed(elevator)
        self._down_events[floor] = []

    def next_floor_above(self, floor: int) -> Union[int, None]:
        """
        Returns the first floor where the up button pressed is equal or above the specified floor.
        """
        for test_floor in range(floor, self._floors):
            if self._up_buttons[test_floor]:
                return test_floor
        return None

    def next_floor_below(self, floor: int) -> Union[int, None]:
        """
        Returns the first floor where the down button is pressed equal or below the specified floor.
        """
        for test_floor in reversed(range(floor + 1)):
            if self._down_buttons[test_floor]:
                return test_floor
        return None


class Monitor:
    def __init__(self) -> None:
        self._values: List[float] = []

    def mean(self):
        return sum(self._values) / len(self._values)
    
    def track(self, value):
        self._values.append(value)


class Request:
    def __init__(
        self, env: simpy.Environment, building: Building, monitor: Monitor, start: int, end: int
    ) -> None:
        self._env: simpy.Environment = env
        self._building: Building = building
        self._start: int = start
        self._end: int = end
        self._name = random.randint(0, 999999999999)
        self._monitor = monitor

    def run(self):
        start_time = self._env.now
        print(f"r{self._name}, t{self._env.now}: waiting for elevator.")

        elevator_event = (
            self._building.press_up_button(self._start)
            if self._start < self._end
            else self._building.press_down_button(self._start)
        )
        yield elevator_event
        print(f"r{self._name}, t{self._env.now}: elevator arrived at floor {self._start}.")

        elevator: Elevator = cast(Elevator, elevator_event.value)
        yield elevator.enter()
        print(f"r{self._name}, t{self._env.now}: entered elevator at floor {self._start}.")

        yield elevator.press_button(self._end)
        print(f"r{self._name}, t{self._env.now}: elevator arrived at floor {self._end}.")

        self._monitor.track(self._env.now - start_time)



env = simpy.Environment()

elevator = Elevator(env, 20)
building = Building(env, 20, [elevator])
monitor = Monitor()


def generate_requests(env: simpy.Environment):
    while True:
        yield env.timeout(random.randint(0, 30))
        if random.random() >= 0.5:
            env.process(Request(env, building, monitor, 0, random.randint(1, 19)).run())
        else:
            env.process(Request(env, building, monitor, random.randint(1, 19), 0).run())

env.process(building.run())
env.process(generate_requests(env))
env.run(3600 * 24)

print(monitor.mean())
