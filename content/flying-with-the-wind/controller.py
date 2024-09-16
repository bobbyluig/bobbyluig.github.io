import heapq
import math
from dataclasses import dataclass
from typing import Callable, Dict, Generator, List, Tuple, Union

from balloon import Balloon
from field import Field3
from simple_pid import PID
from vector import Vector3


@dataclass
class ControllerInput:
    """
    Represents inputs for the controller.
    """

    time: float
    position: Vector3
    velocity: Vector3
    temperature: float
    fuel: float
    vent: float


@dataclass
class ControllerOutput:
    """
    Represents the output of the controller.
    """

    fuel: float
    vent: float


type Controller = Callable[[ControllerInput], ControllerOutput]
"""
Represents a controller for the balloon.
"""


def get_controller_input(balloon: Balloon) -> ControllerInput:
    """
    Takes a balloon and returns a ControllerInput with its state.
    """
    return ControllerInput(
        time=balloon.get_time(),
        position=balloon.get_position(),
        velocity=balloon.get_velocity(),
        temperature=balloon.get_temperature(),
        fuel=balloon.get_fuel(),
        vent=balloon.get_vent(),
    )


def apply_controller_output(
    balloon: Balloon, controller_output: ControllerOutput
) -> None:
    """
    Takes a balloon and a ControllerOutput and applies the output to the balloon.
    """
    balloon.set_fuel(controller_output.fuel)
    balloon.set_vent(controller_output.vent)


class FixedController:
    """
    A controller that returns a fixed output.
    """

    def __init__(self, output: ControllerOutput):
        """
        Initializes the controller with a fixed output.
        """
        self.output = output

    def __call__(self, input: ControllerInput) -> ControllerOutput:
        """
        Returns the controller output for the given input.
        """
        return self.output


class SequenceController:
    """
    A controller that returns a sequence of pre-defined outputs. The outputs are associated with
    times, and the controller will return the most recent output for which the time is less than or
    equal to the input time.
    """

    def __init__(self, *controllers: Tuple[float, Controller]):
        """
        Initializes the controller with a sequence of controllers.
        """
        self.controllers = sorted(controllers, key=lambda t: t[0], reverse=True)
        self.last_controller = None

    def __call__(self, input: ControllerInput) -> ControllerOutput:
        """
        Returns the controller output for the given input.
        """
        while self.controllers and self.controllers[-1][0] <= input.time:
            self.last_controller = self.controllers.pop()[1]

        if self.last_controller is None:
            return ControllerOutput(fuel=0.0, vent=0.0)

        return self.last_controller(input)


class VerticalVelocityController:
    """
    A controller that targets a constant vertical velocity. It embeds a PID controller. Fuel and
    vent inputs are discretized to 1%.
    """

    def __init__(
        self,
        target: float,
        k_p: float = 10.874548503904872,
        k_i: float = 34.790141360779124,
        k_d: float = 124.25863289470911,
    ):
        """
        Initializes the controller with the given tuning parameters.
        """
        self.now = 0
        self.pid = PID(
            Kp=k_p,
            Ki=k_i,
            Kd=k_d,
            setpoint=target,
            sample_time=1,
            output_limits=(-1.0, 1.0),
            time_fn=lambda: self.now,
        )

    def __call__(self, input: ControllerInput) -> ControllerOutput:
        """
        Returns the controller output for the given input.
        """
        self.now = input.time

        output = self.pid(input.velocity.z)
        if output is None:
            output = 0

        output = round(100 * output)

        if output < 0:
            return ControllerOutput(fuel=0, vent=-output)
        else:
            return ControllerOutput(fuel=output, vent=0)


class VerticalPositionController:
    """
    A controller that targets a constant vertical position. It embeds a PID controller whose output
    is fed into a VelocityController. Velocity input is discretized to 0.1 m/s and capped at 4 m/s
    in either direction.
    """

    def __init__(
        self,
        target: float,
        k_p: float = 0.008965567179058827,
        k_i: float = 0.0,
        k_d: float = 0.0,
    ):
        """
        Initializes the controller with the given tuning parameters.
        """
        self.now = 0
        self.pid = PID(
            Kp=k_p,
            Ki=k_i,
            Kd=k_d,
            setpoint=target,
            sample_time=1,
            output_limits=(-1.0, 1.0),
            time_fn=lambda: self.now,
        )
        self.last_velocity = 0.0
        self.last_velocity_controller = VerticalVelocityController(0.0)

    def __call__(self, input: ControllerInput) -> ControllerOutput:
        """
        Returns the controller output for the given input.
        """
        self.now = input.time

        output = self.pid(input.position.z)
        if output is None:
            output = 0

        output *= 4
        output = round(output * 10) / 10
        if math.isclose(output, self.last_velocity):
            return self.last_velocity_controller(input)

        self.last_velocity = output
        self.last_velocity_controller = VerticalVelocityController(output)
        return self.last_velocity_controller(input)


class PositionController:
    def __init__(
        self,
        target: Vector3,
        dimensions: Vector3,
        wind_field: Field3,
        grid_size: int = 100,
    ):
        self.target: Vector3 = target
        self.dimensions: Vector3 = dimensions
        self.wind_field: Field3 = wind_field
        self.grid_size: int = grid_size

        self.target_grid: Vector3 = self.position_to_grid(self.target)
        self.current_grid: Vector3 = Vector3(0, 0, 0)
        self.next_grid: Vector3 = Vector3(0, 0, 0)
        self.controller: VerticalPositionController = VerticalPositionController(
            grid_size / 2
        )

        self.update_controller()

    def __call__(self, input: ControllerInput) -> ControllerOutput:
        """
        Returns the controller output for the given input.
        """
        current_grid = self.position_to_grid(input.position)
        if current_grid != self.current_grid:
            self.current_grid = current_grid
            self.update_controller()

        return self.controller(input)

    def position_to_grid(self, position: Vector3) -> Vector3:
        """
        Converts the given position to a discretized grid position.
        """
        return Vector3(
            int(position.x / self.grid_size),
            int(position.y / self.grid_size),
            int(position.z / self.grid_size),
        )

    def grid_to_position(self, grid: Vector3) -> Vector3:
        """
        Converts the given grid position to a continuous position in the middle of the grid.
        """
        return grid * self.grid_size + self.grid_size / 2

    def grid_in_bounds(self, grid: Vector3) -> bool:
        """
        Checks if the given grid position is within the bounds of the dimensions.
        """
        position = self.grid_to_position(grid)
        return (
            abs(position.x) <= self.dimensions.x / 2
            and abs(position.y) <= self.dimensions.y / 2
            and 0 <= position.z <= self.dimensions.z
        )

    def grid_distance(self, a: Vector3, b: Vector3) -> float:
        """
        Calculates the euclidean distance between two grid positions.
        """
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2) ** 0.5

    def update_controller(self):
        """
        Updates the current controller by searching for the best path to the target.
        """
        # Find the best path to the target grid position.
        path = self.search()

        # If there is no next grid position, do nothing.
        if len(path) == 1:
            return

        # If the next grid position is the same as the target, do nothing.
        old_next_grid_z = self.next_grid.z
        self.next_grid = path[1]
        if self.next_grid.z == old_next_grid_z:
            return

        # Update the controller.
        next_position = self.grid_to_position(self.next_grid)
        print(next_position)
        self.controller = VerticalPositionController(
            next_position.z + self.grid_size / 2
        )

    def search(self) -> List[Vector3]:
        """
        Searches for the best path to the target grid position from the current grid position using
        A* search. If it is not possible to reach the target grid position, the path that gets
        closest is returned. The returned path is a list of grid positions.
        """
        open_set: List[Tuple[float, Vector3]] = [
            (self.grid_distance(self.current_grid, self.target_grid), self.current_grid)
        ]
        came_from: Dict[Vector3, Union[Vector3, None]] = {self.current_grid: None}
        g_score: Dict[Vector3, float] = {self.current_grid: 0}

        while open_set:
            score, current = heapq.heappop(open_set)
            if current == self.target_grid:
                break
            for neighbor in self.neighbors(current):
                if neighbor not in g_score:
                    g_score[neighbor] = float("inf")
                tentative_g_score = g_score[current] + self.grid_distance(
                    current, neighbor
                )
                if tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    heapq.heappush(
                        open_set,
                        (
                            tentative_g_score
                            + self.grid_distance(neighbor, self.target_grid),
                            neighbor,
                        ),
                    )

        current = min(
            came_from, key=lambda grid: self.grid_distance(grid, self.target_grid)
        )
        path = []
        while current is not None:
            path.append(current)
            current = came_from[current]
        path.reverse()

        return path

    def neighbors(self, grid: Vector3) -> Generator[Vector3, None, None]:
        """
        Returns valid neighbors of the given grid position.
        """
        # Yield vertical neighbors if they are in bounds.
        for dz in (-1, 1):
            n = Vector3(grid.x, grid.y, grid.z + dz)
            if self.grid_in_bounds(n):
                yield n

        # Get the wind field at the given grid position.
        wind_field = self.wind_field(self.grid_to_position(grid))

        # Compute horizontal neighbor by taking the dominant direction.
        if abs(wind_field.x) > abs(wind_field.y):
            dx = 1 if wind_field.x > 0 else -1
            dy = 0
        else:
            dx = 0
            dy = 1 if wind_field.y > 0 else -1

        # Yield the horizontal neighbor if it is in bounds.
        n = Vector3(grid.x + dx, grid.y + dy, grid.z)
        if self.grid_in_bounds(n):
            yield n
