import simpy
from typing import cast, Any, List, Union, Generator, Dict
import random

k_move: float = 1.0
k_door: float = 3.0
k_person: float = 0.5
k_floors: int = 20


class Request:
    def __init__(self, start: int, end: int) -> None:
        self.start: int = start
        self.end: int = end

    def on_wait(self, env: simpy.Environment):
        print(f'{env.now}: waiting for elevator at floor {self.start}')

    def on_enter(self, env: simpy.Environment):
        print(f'{env.now}: entering elevator at floor {self.start}')

    def on_exit(self, env: simpy.Environment):
        print(f'{env.now}: exiting elevator at floor {self.end}')


class Elevator:
    def __init__(self) -> None:
        self.open: bool = False
        self.floor: int = 0
        self.direction: int = 0
        self.buttons: List[bool] = [False for _ in range(k_floors)]
        self.requests: List[List[Request]] = [[] for _ in range(k_floors)]

    def next_floor_above(self) -> Union[int, None]:
        for test_floor in range(self.floor, k_floors):
            if self.buttons[test_floor]:
                return test_floor
        return None

    def next_floor_below(self) -> Union[int, None]:
        for test_floor in reversed(range(self.floor + 1)):
            if self.buttons[test_floor]:
                return test_floor
        return None


class Building:
    def __init__(self) -> None:
        self.up_buttons: List[bool] = [False for _ in range(k_floors)]
        self.down_buttons: List[bool] = [False for _ in range(k_floors)]
        self.up_requests: List[List[Request]] = [[] for _ in range(k_floors)]
        self.down_requests: List[List[Request]] = [[] for _ in range(k_floors)]

    def next_floor_above(self, floor: int) -> Union[int, None]:
        for test_floor in range(floor, k_floors):
            if self.up_buttons[test_floor]:
                return test_floor
        return None

    def next_floor_below(self, floor: int) -> Union[int, None]:
        for test_floor in reversed(range(floor + 1)):
            if self.down_buttons[test_floor]:
                return test_floor
        return None


class Controller:
    def __init__(
        self, env: simpy.Environment, building: Building, elevators: List[Elevator]
    ) -> None:
        self.env: simpy.Environment = env
        self.building: Building = building
        self.elevators: List[Elevator] = elevators
        self.wake_events: List[simpy.Event] = [
            self.env.event() for _ in range(len(self.elevators))
        ]

    def new_request(self, request: Request):
        direction = 1 if request.end > request.start else -1

        if direction > 0:
            building_buttons = self.building.up_buttons
            building_requests = self.building.up_requests
        else:
            building_buttons = self.building.down_buttons
            building_requests = self.building.down_requests

        needs_button = True
        for elevator in self.elevators:
            if (
                elevator.floor == request.start
                and elevator.direction == direction
                and elevator.open
            ):
                needs_button = False
                break

        building_requests[request.start].append(request)
        if needs_button:
            building_buttons[request.start] = True

        request.on_wait(self.env)

        for i, wake_event in enumerate(self.wake_events):
            wake_event.succeed()
            self.wake_events[i] = self.env.event()

    def arrive(self, elevator_index: int):
        elevator = self.elevators[elevator_index]
        elevator.buttons[elevator.floor] = False
        
        if elevator.direction > 0 and self.next_floor_above(elevator_index) is None:
            elevator.direction = -1
        elif elevator.direction < 0 and self.next_floor_below(elevator_index) is None:
            elevator.direction = 1

        print(f'{env.now}: elevator arriving at {elevator.floor} going {elevator.direction}')

        if elevator.direction > 0:
            building_buttons = self.building.up_buttons
            building_requests = self.building.up_requests
        else:
            building_buttons = self.building.down_buttons
            building_requests = self.building.down_requests

  
        building_buttons[elevator.floor] = False

        yield self.env.timeout(k_door)
        elevator.open = True

        while elevator.requests[elevator.floor]:
            yield self.env.timeout(k_person)
            request = elevator.requests[elevator.floor].pop()
            request.on_exit(self.env)

        while building_requests[elevator.floor]:
            yield self.env.timeout(k_person)
            request = building_requests[elevator.floor].pop(0)
            elevator.requests[request.end].append(request)
            elevator.buttons[request.end] = True
            request.on_enter(self.env)

        elevator.open = False
        yield self.env.timeout(k_door)

    def next_floor_above(self, elevator_index: int):
        elevator = self.elevators[elevator_index]
        return min(
            (
                floor
                for floor in (
                    elevator.next_floor_above(),
                    self.building.next_floor_above(elevator.floor),
                )
                if floor is not None
            ),
            default=None,
        )

    def next_floor_below(self, elevator_index: int):
        elevator = self.elevators[elevator_index]
        return max(
            (
                floor
                for floor in (
                    elevator.next_floor_below(),
                    self.building.next_floor_below(elevator.floor),
                )
                if floor is not None
            ),
            default=None,
        )

    def highest_building_floor_button(self):
        return max(
            (
                floor
                for floor in (
                    self.building.next_floor_above(0),
                    self.building.next_floor_below(k_floors - 1),
                )
                if floor is not None
            ),
            default=None,
        )

    def run_elevator(self, elevator_index: int):
        elevator = self.elevators[elevator_index]

        while True:
            floor = None
            if elevator.direction >= 0:
                floor = self.next_floor_above(elevator_index)
            else:
                floor = self.next_floor_below(elevator_index)
           
            if floor is None:
                floor = self.highest_building_floor_button()

            if floor is None:
                elevator.direction = 0
                print(f'{env.now}: elevator has no requests')
                yield self.wake_events[elevator_index]
                continue

            if elevator.direction == 0:
                if floor > elevator.floor:
                    elevator.direction = 1
                elif floor < elevator.floor:
                    elevator.direction = -1
                elif self.building.up_buttons[elevator.floor]:
                    elevator.direction = 1
                elif self.building.down_buttons[elevator.floor]:
                    elevator.direction = -1
                else:
                    raise Exception('unreachable')

            if elevator.floor == floor:
                yield self.env.process(self.arrive(elevator_index))
                continue

            yield self.env.timeout(k_move)
            elevator.floor += elevator.direction


def requests(env: simpy.Environment, controller: Controller):
    controller.new_request(Request(0, 1))

    yield env.timeout(100)

    controller.new_request(Request(10, 0))
    controller.new_request(Request(10, 2))
    controller.new_request(Request(9, 0))
    controller.new_request(Request(0, 12))


env = simpy.Environment()
building = Building()
elevators = [Elevator() for _ in range(1)]
controller = Controller(env, building, elevators)

env.process(controller.run_elevator(0))
env.process(requests(env, controller))
env.run()
