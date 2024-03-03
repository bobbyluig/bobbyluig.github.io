import random
from typing import Generator, List, Union

import simpy

k_velocity: float = 1.0
k_door: float = 3.0
k_person: float = 0.5
k_floors: int = 20
k_capacity: int = 10
k_acceleration: float = 1.0


class Request:
    counter = 0

    def __init__(self, start: int, end: int) -> None:
        self.start: int = start
        self.end: int = end
        self.start_time: float = 0
        self.end_time: float = 0
        self.name: int = Request.counter
        Request.counter += 1

    def on_wait(self, env: simpy.Environment):
        self.start_time = env.now
        print(f"{env.now}: request {self.name} waiting at floor {self.start} to go to {self.end}")

    def on_enter(self, env: simpy.Environment):
        print(f"{env.now}: request {self.name} entering at floor {self.start} to go to {self.end}")

    def on_exit(self, env: simpy.Environment):
        self.end_time = env.now
        print(f"{env.now}: request {self.name} exiting at floor {self.end}")


class Elevator:
    def __init__(self) -> None:
        self.open: bool = False
        self.floor: int = 0
        self.direction: int = 0
        self.count: int = 0
        self.moving: bool = False
        self.target: Union[int, None] = None
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
        self.times: List[float] = []

    def new_request(self, request: Request):
        while True:
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

            return

    def arrive(self, elevator_index: int):
        elevator = self.elevators[elevator_index]

        if elevator.moving:
            yield self.env.timeout(k_acceleration)
            elevator.moving = False

        elevator.buttons[elevator.floor] = False

        if elevator.direction > 0 and self.next_floor_above(elevator_index) is None:
            elevator.direction = -1
        elif elevator.direction < 0 and self.next_floor_below(elevator_index) is None:
            elevator.direction = 1

        print(
            f'{env.now}: elevator {elevator_index} arriving at {elevator.floor} heading {elevator.direction}'
        )

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
            request = elevator.requests[elevator.floor].pop()
            yield self.env.timeout(k_person)
            elevator.count -= 1
            request.on_exit(self.env)
            self.times.append(request.end_time - request.start_time)

        while building_requests[elevator.floor] and elevator.count < k_capacity:
            request = building_requests[elevator.floor].pop(0)
            yield self.env.timeout(k_person)
            elevator.requests[request.end].append(request)
            elevator.buttons[request.end] = True
            elevator.count += 1
            request.on_enter(self.env)

        at_capacity = False
        if building_requests[elevator.floor]:
            print(f'{env.now}: elevator {elevator_index} at capacity')
            at_capacity = True

        elevator.open = False
        yield self.env.timeout(k_door)

        if at_capacity:
            floor = elevator.floor
            building_buttons[floor] = False
            def skip_floor():
                yield self.env.timeout(1)
                building_buttons[floor] = True
            self.env.process(skip_floor())

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
    
    def stop_elevator(self, elevator_index: int):
        elevator = self.elevators[elevator_index]
        wake_event = self.wake_events[elevator_index]

        if elevator.moving:
             yield self.env.timeout(k_acceleration)

        elevator.direction = 0
        elevator.target = None
        elevator.moving = False

        yield wake_event

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
                print(f'{env.now}: elevator {elevator_index} has no requests')
                yield self.env.process(self.stop_elevator(elevator_index))
                continue

            if elevator.direction == 0 and any(
                i != elevator_index
                and other_elevator.target == floor
                for i, other_elevator in enumerate(self.elevators)
            ):
                print(f"{env.now}: elevator {elevator_index} being lazy")
                yield self.env.process(self.stop_elevator(elevator_index))
                continue

            elevator.target = floor

            previous_direction = elevator.direction

            if floor > elevator.floor:
                elevator.direction = 1
            elif floor < elevator.floor:
                elevator.direction = -1

            if elevator.direction == 0:
                if self.building.up_buttons[elevator.floor]:
                    elevator.direction = 1
                elif self.building.down_buttons[elevator.floor]:
                    elevator.direction = -1
                else:
                    raise Exception('unreachable')

            print(f'{env.now}: elevator {elevator_index} heading to floor {floor} from {elevator.floor}')

            if elevator.floor == floor:
                yield self.env.process(self.arrive(elevator_index))
                continue

            if elevator.moving and previous_direction != elevator.direction:
                assert(abs(previous_direction - elevator.direction) == 2)
                yield self.env.timeout(2 * k_acceleration)
            elif not elevator.moving:
                yield self.env.timeout(k_acceleration)
                elevator.moving = True

            yield self.env.timeout(k_velocity)
            elevator.floor += elevator.direction


def test_requests(env: simpy.Environment, controller: Controller):
    controller.new_request(Request(0, 1))

    yield env.timeout(100)

    controller.new_request(Request(10, 0))
    controller.new_request(Request(10, 2))
    controller.new_request(Request(9, 0))
    controller.new_request(Request(0, 12))


def random_requests(env: simpy.Environment, controller: Controller):
    while True:
        yield env.timeout(random.randint(0, 10))
        if random.randint(0, 1) == 0:
            controller.new_request(Request(0, random.randint(1, 19)))
        else:
            controller.new_request(Request(random.randint(1, 19), 0))


env = simpy.Environment()
building = Building()
elevators = [Elevator() for _ in range(2)]
controller = Controller(env, building, elevators)

for i in range(len(elevators)):
    env.process(controller.run_elevator(i))
env.process(random_requests(env, controller))
env.run(3600 * 24)

print(sum(controller.times) / len(controller.times))
