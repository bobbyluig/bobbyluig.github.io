import random
from dataclasses import dataclass
from typing import Callable, List, Set, Tuple, Union

import simpy
import simpy.events


k_building_floors: int = 20
k_door_velocity: float = 3.0
k_door_wait: float = 5.0
k_elevator_acceleration: float = 1.0
k_elevator_capacity: int = 10
k_elevator_count: int = 2
k_elevator_velocity: float = 1.0
k_person_velocity: float = 0.5
k_request_rate: float = 2

k_debug: bool = False


def debug(env: simpy.Environment, message):
    if k_debug:
        print(f"{round(env.now, 2)}: {message}")


@dataclass
class Action_Arrive:
    direction: int


@dataclass
class Action_Move:
    floor: int


@dataclass
class Action_Stop:
    pass


type Action = Union[Action_Arrive, Action_Move, Action_Stop]


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
        debug(
            env,
            f"request {self.name} waiting at floor {self.start} to go to {self.end}",
        )

    def on_enter(self, env: simpy.Environment):
        debug(
            env,
            f"request {self.name} entering at floor {self.start} to go to {self.end}",
        )

    def on_exit(self, env: simpy.Environment):
        self.end_time = env.now
        debug(env, f"request {self.name} exiting at floor {self.end}")


class Elevator:
    def __init__(self) -> None:
        self.arrived: bool = False
        self.floor: int = 0
        self.direction: int = 0
        self.count: int = 0
        self.moving: bool = False
        self.target: Union[int, None] = None
        self.buttons: List[bool] = [False for _ in range(k_building_floors)]
        self.requests: List[List[Request]] = [[] for _ in range(k_building_floors)]

    def next_floor_above(self) -> Union[int, None]:
        for test_floor in range(self.floor, k_building_floors):
            if self.buttons[test_floor]:
                return test_floor
        return None

    def next_floor_below(self) -> Union[int, None]:
        for test_floor in reversed(range(self.floor + 1)):
            if self.buttons[test_floor]:
                return test_floor
        return None

    def floors(self) -> Set[int]:
        return {floor for floor in range(k_building_floors) if self.buttons[floor]}


class Building:
    def __init__(self) -> None:
        self.up_buttons: List[bool] = [False for _ in range(k_building_floors)]
        self.down_buttons: List[bool] = [False for _ in range(k_building_floors)]
        self.up_requests: List[List[Request]] = [[] for _ in range(k_building_floors)]
        self.down_requests: List[List[Request]] = [[] for _ in range(k_building_floors)]

    def next_floor_above(self, floor: int) -> Union[int, None]:
        for test_floor in range(floor, k_building_floors):
            if self.up_buttons[test_floor]:
                return test_floor
        return None

    def next_floor_below(self, floor: int) -> Union[int, None]:
        for test_floor in reversed(range(floor + 1)):
            if self.down_buttons[test_floor]:
                return test_floor
        return None

    def up_floors(self) -> Set[int]:
        return {floor for floor in range(k_building_floors) if self.up_buttons[floor]}

    def down_floors(self) -> Set[int]:
        return {floor for floor in range(k_building_floors) if self.down_buttons[floor]}


class Controller:
    def __init__(
        self, env: simpy.Environment, building: Building, elevators: List[Elevator]
    ) -> None:
        self.env: simpy.Environment = env
        self.building: Building = building
        self.elevators: List[Elevator] = elevators
        self.door_processes: List[Union[simpy.Process, None]] = [
            None for _ in range(len(self.elevators))
        ]
        self.wake_events: List[simpy.Event] = [
            self.env.event() for _ in range(len(self.elevators))
        ]
        self.policy: Callable[[int], Action] = self.simple_policy

    def interrupt_door(self, elevator_index: int):
        process = self.door_processes[elevator_index]
        if process is not None:
            process.interrupt()

    def needs_button(self, direction: int, floor: int) -> bool:
        if direction > 0:
            building_buttons = self.building.up_buttons
        else:
            building_buttons = self.building.down_buttons

        if building_buttons[floor]:
            return False

        for elevator_index, elevator in enumerate(self.elevators):
            if (
                elevator.floor == floor
                and elevator.arrived
                and elevator.direction == direction
            ):
                self.interrupt_door(elevator_index)
                return False

        for elevator_index, elevator in enumerate(self.elevators):
            if elevator.floor == floor and elevator.arrived and elevator.direction == 0:
                elevator.direction = direction
                self.interrupt_door(elevator_index)
                return False

        return True

    def new_request(self, request: Request):
        direction = 1 if request.end > request.start else -1

        if direction > 0:
            building_buttons = self.building.up_buttons
            building_requests = self.building.up_requests
        else:
            building_buttons = self.building.down_buttons
            building_requests = self.building.down_requests

        building_requests[request.start].append(request)

        if self.needs_button(direction, request.start):
            building_buttons[request.start] = True

        request.on_wait(self.env)

        for i, wake_event in enumerate(self.wake_events):
            wake_event.succeed()
            self.wake_events[i] = self.env.event()

    def next_scan_up_floor(self, elevator_index: int):
        elevator = self.elevators[elevator_index]
        floor = min(
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
        if floor is None:
            down_floor = self.building.next_floor_below(k_building_floors - 1)
            if down_floor is not None and down_floor > elevator.floor:
                floor = down_floor
        return floor

    def next_scan_down_floor(self, elevator_index: int):
        elevator = self.elevators[elevator_index]
        floor = max(
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
        if floor is None:
            up_floor = self.building.next_floor_above(0)
            if up_floor is not None and up_floor < elevator.floor:
                floor = up_floor
        return floor

    def closest_floor_with_request(self, elevator_index: int):
        elevator = self.elevators[elevator_index]
        return min(
            self.building.up_floors() | self.building.down_floors(),
            key=lambda floor: abs(elevator.floor - floor),
            default=None,
        )

    def action_stop(self, elevator_index: int, action: Action_Stop):
        elevator = self.elevators[elevator_index]
        wake_event = self.wake_events[elevator_index]

        if elevator.moving:
            yield self.env.timeout(k_elevator_acceleration)

        elevator.direction = 0
        elevator.target = None
        elevator.moving = False

        yield wake_event

    def action_arrive(self, elevator_index: int, action: Action_Arrive):
        elevator = self.elevators[elevator_index]
        elevator.arrived = True
        elevator.buttons[elevator.floor] = False
        elevator.direction = action.direction

        if elevator.direction > 0:
            self.building.up_buttons[elevator.floor] = False
        elif elevator.direction < 0:
            self.building.down_buttons[elevator.floor] = False

        debug(
            self.env,
            f"elevator {elevator_index} arriving at {elevator.floor} heading {elevator.direction}",
        )

        if elevator.moving:
            yield self.env.timeout(k_elevator_acceleration)
            elevator.moving = False

        debug(self.env, f"elevator {elevator_index} door start opening")
        yield self.env.timeout(k_door_velocity)
        debug(self.env, f"elevator {elevator_index} door done opening")

        at_capacity = False
        while not at_capacity:
            while elevator.requests[elevator.floor]:
                request = elevator.requests[elevator.floor].pop()
                yield self.env.timeout(k_person_velocity)
                elevator.count -= 1
                request.on_exit(self.env)

            if elevator.direction > 0:
                building_buttons = self.building.up_buttons
                building_requests = self.building.up_requests
            else:
                building_buttons = self.building.down_buttons
                building_requests = self.building.down_requests

            while (
                building_requests[elevator.floor]
                and elevator.count < k_elevator_capacity
            ):
                request = building_requests[elevator.floor].pop(0)
                yield self.env.timeout(k_person_velocity)
                elevator.requests[request.end].append(request)
                elevator.buttons[request.end] = True
                elevator.count += 1
                request.on_enter(self.env)

            if building_requests[elevator.floor]:
                debug(self.env, f"elevator {elevator_index} at capacity")
                at_capacity = True

            try:
                door_close_event = self.env.event()

                def wait_door_close():
                    try:
                        yield self.env.timeout(k_door_wait)
                        door_close_event.succeed()
                    except simpy.Interrupt as e:
                        door_close_event.fail(e)
                    finally:
                        self.door_processes[elevator_index] = None

                self.door_processes[elevator_index] = self.env.process(
                    wait_door_close()
                )
                debug(self.env, f"elevator {elevator_index} door start waiting")
                yield door_close_event
                debug(self.env, f"elevator {elevator_index} door end waiting")

                elevator.arrived = False
                debug(self.env, f"elevator {elevator_index} door start closing")
                yield self.env.timeout(k_door_velocity)
                debug(self.env, f"elevator {elevator_index} door done closing")

                if at_capacity:

                    def skip_floor(building_buttons, floor, direction):
                        yield self.env.timeout(1)
                        building_buttons[floor] = self.needs_button(direction, floor)
                        debug(self.env, f"re-pressing button on floor {floor}")

                    self.env.process(
                        skip_floor(
                            building_buttons,
                            elevator.floor,
                            1 if elevator.direction > 0 else -1,
                        )
                    )

                break
            except simpy.Interrupt:
                debug(self.env, f"elevator {elevator_index} door wait interrupted")

    def action_move(self, elevator_index: int, action: Action_Move):
        elevator = self.elevators[elevator_index]

        debug(
            self.env,
            f"elevator {elevator_index} heading to floor {action.floor} from {elevator.floor}",
        )

        if elevator.floor == action.floor:
            return

        elevator.target = action.floor
        previous_direction = elevator.direction

        if action.floor > elevator.floor:
            elevator.direction = 1
        elif action.floor < elevator.floor:
            elevator.direction = -1

        if elevator.moving and previous_direction != elevator.direction:
            assert abs(previous_direction - elevator.direction) == 2
            yield self.env.timeout(2 * k_elevator_acceleration)
        elif not elevator.moving:
            yield self.env.timeout(k_elevator_acceleration)
            elevator.moving = True

        yield self.env.timeout(k_elevator_velocity)
        elevator.floor += elevator.direction

    def simple_policy(self, elevator_index: int) -> Action:
        elevator = self.elevators[elevator_index]

        floor = None
        if elevator.direction > 0:
            floor = self.next_scan_up_floor(elevator_index)
        elif elevator.direction < 0:
            floor = self.next_scan_down_floor(elevator_index)

        if floor is None:
            floor = self.closest_floor_with_request(elevator_index)

        if floor is None:
            debug(self.env, f"elevator {elevator_index} has no requests")
            return Action_Stop()

        if elevator.direction == 0 and any(
            i != elevator_index and other_elevator.target == floor
            for i, other_elevator in enumerate(self.elevators)
        ):
            debug(self.env, f"elevator {elevator_index} being lazy (already targeted)")
            return Action_Stop()

        if elevator.direction == 0 and any(
            i != elevator_index
            and other_elevator.direction == 0
            and abs(other_elevator.floor - floor) < abs(elevator.floor - floor)
            for i, other_elevator in enumerate(self.elevators)
        ):
            debug(self.env, f"elevator {elevator_index} being lazy (other closer)")
            return Action_Stop()

        if floor != elevator.floor:
            return Action_Move(floor)

        arrive_direction = elevator.direction

        button_pressed = elevator.buttons[elevator.floor]
        elevator.buttons[elevator.floor] = False
        if (
            len(elevator.floors())
            + len(self.building.up_floors())
            + len(self.building.down_floors())
            == 0
        ):
            arrive_direction = 0
        elif elevator.direction > 0 and self.next_scan_up_floor(elevator_index) is None:
            arrive_direction = -1
        elif (
            elevator.direction < 0 and self.next_scan_down_floor(elevator_index) is None
        ):
            arrive_direction = 1
        elevator.buttons[elevator.floor] = button_pressed

        if elevator.direction == 0:
            if self.building.up_buttons[elevator.floor]:
                arrive_direction = 1
            elif self.building.down_buttons[elevator.floor]:
                arrive_direction = -1
            else:
                raise Exception("unreachable")

        return Action_Arrive(arrive_direction)

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


def test_requests() -> List[Tuple[float, Request]]:
    return [
        (0, Request(0, 1)),
        (100, Request(10, 0)),
        (100, Request(10, 2)),
        (100, Request(9, 0)),
        (100, Request(0, 12)),
    ]


def random_requests(count: int) -> List[Tuple[float, Request]]:
    requests: List[Tuple[float, Request]] = []
    start_time: float = 0

    distribution = [
        (47.5, lambda: Request(0, random.randint(3, k_building_floors - 1))),
        (47.5, lambda: Request(random.randint(3, k_building_floors - 1), 0)),
        (
            2.5,
            lambda: Request(
                random.randint(1, 2), random.randint(3, k_building_floors - 1)
            ),
        ),
        (
            2.5,
            lambda: Request(
                random.randint(3, k_building_floors - 1), random.randint(1, 2)
            ),
        ),
    ]
    weights = [x[0] for x in distribution]

    for _ in range(count):
        start_time += random.uniform(0, 60.0 / k_request_rate)
        choice = random.choices(list(range(len(distribution))), weights=weights)[0]
        requests.append((start_time, distribution[choice][1]()))

    return requests


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

    random.seed(0)
    for i in range(len(elevators)):
        env.process(controller.run_elevator(i))
    requests = random_requests(10000)
    # requests = test_requests()
    env.process(run_requests(env, controller, requests))
    env.run()

    request_times = [request.end_time - request.start_time for _, request in requests]
    print(f"mean latency: {sum(request_times) / len(request_times)}")
    print(f"max latency: {max(request_times)}")

    times_by_floor = {}
    for _, request in requests:
        floor = None
        if request.start > 2:
            floor = request.start
        elif request.end > 2:
            floor = request.end

        if floor is not None:
            times_by_floor.setdefault(floor, []).append(
                request.end_time - request.start_time
            )

    mean_latencies = []
    max_latencies = []

    for i in range(k_building_floors):
        if i in times_by_floor:
            request_times = times_by_floor[i]
            mean_latencies.append(sum(request_times) / len(request_times))
            max_latencies.append(max(request_times))
        else:
            mean_latencies.append(None)
            max_latencies.append(None)

    print(f"mean latency by floor: {mean_latencies}")
    print(f"max latency by floor: {max_latencies}")
