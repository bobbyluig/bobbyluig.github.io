import functools
import heapq
import math
import os
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
        self.target = target
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
        k_p: float = 0.009774907674593549,
        k_i: float = 0.0,
        k_d: float = 0.0,
    ):
        """
        Initializes the controller with the given tuning parameters.
        """
        self.target = target
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


class GreedyPositionController:
    """
    A controller that targets a given position taking the wind field into account. It greedily
    chooses the vertical position which would move the balloon closest to the target.
    """

    def __init__(
        self,
        target: Vector3,
        dimensions: Vector3,
        wind_field: Field3,
        grid_size: Vector3 = Vector3(100, 100, 100),
    ):
        """
        Initializes the controller with the given tuning parameters.
        """
        self.target: Vector3 = target
        self.dimensions: Vector3 = dimensions
        self.wind_field: Field3 = functools.lru_cache(maxsize=None)(wind_field)
        self.grid_size: Vector3 = grid_size

        self.controller: Union[VerticalPositionController, None] = None

    def __call__(self, input: ControllerInput) -> ControllerOutput:
        """
        Returns the controller output for the given input.
        """
        # If the balloon is in the same horizontal grid position as the target, then just target the 
        # vertical position.
        position_grid = self.position_to_grid(input.position)
        target_grid = self.position_to_grid(self.target)
        if position_grid.x == target_grid.x and position_grid.y == target_grid.y:
            self.controller = VerticalPositionController(self.target.z)
            return self.controller(input)

        # Compute the normalized vector from position to target.
        v_target = Vector3(
            self.target.x - input.position.x, self.target.y - input.position.y, 0
        ).normalize()

        # Use cosine similarity to find the best vertical position.
        best_grid = position_grid
        best_similarity = -float("inf")

        current_grid = self.position_to_grid(input.position)
        for z in range(0, int(self.dimensions.z // self.grid_size.z)):
            test_grid = Vector3(current_grid.x, current_grid.y, z)
            v_wind = self.wind_field(self.grid_to_position(test_grid))
            if v_wind.x == 0 and v_wind.y == 0:
                continue
            v_wind = Vector3(v_wind.x, v_wind.y, 0).normalize()

            similarity = v_wind.dot(v_target)
            if similarity > best_similarity:
                best_similarity = similarity
                best_grid = test_grid

        # If we are already targeting the best vertical position, then use the existing controller.
        best_z = self.grid_to_position(best_grid).z
        if self.controller is not None and best_z == self.controller.target:
            return self.controller(input)

        # Initialize a new controller.
        self.controller_z = best_z
        self.controller = VerticalPositionController(best_z)
        return self.controller(input)

    def position_to_grid(self, position: Vector3) -> Vector3:
        """
        Converts the given position to a discretized grid position.
        """
        return Vector3(
            int(position.x // self.grid_size.x),
            int(position.y // self.grid_size.y),
            int(position.z // self.grid_size.z),
        )

    def grid_to_position(self, grid: Vector3) -> Vector3:
        """
        Converts the given grid position to a continuous position in the middle of the grid.
        """
        return grid * self.grid_size + self.grid_size / 2


class SearchPositionController:
    """
    A controller that targets a given position taking the wind field into account. It uses A* to
    find the lowest cost path to the target. If the position is not reachable, then the closest
    reachable position is targeted instead (subject to the grid size specified).
    """

    def __init__(
        self,
        target: Vector3,
        dimensions: Vector3,
        wind_field: Field3,
        grid_size: Vector3 = Vector3(100, 100, 100),
        max_vertical_speed: float = 4.0,
    ):
        """
        Initializes the controller with the given tuning parameters.
        """
        self.target: Vector3 = target
        self.dimensions: Vector3 = dimensions
        self.wind_field: Field3 = functools.lru_cache(maxsize=None)(wind_field)
        self.grid_size: Vector3 = grid_size
        self.max_vertical_speed: float = max_vertical_speed

        self.target_grid: Vector3 = self.position_to_grid(self.target)
        self.unreachable_grid: Vector3 = Vector3(
            self.target_grid.x, self.target_grid.y, -1
        )

        self.controller: Union[VerticalPositionController, None] = None
        self.current_grid: Union[Vector3, None] = None
        self.parents: Union[Dict[Vector3, Union[Vector3, None]], None] = None

    def __call__(self, input: ControllerInput) -> ControllerOutput:
        """
        Returns the controller output for the given input.
        """
        # Check if we need to initialize the controller. We do not know the position of the balloon
        # until the first input is received.
        if self.current_grid is None or self.controller is None:
            # The controller is not initialized. Set a default controller that holds at the current
            # grid height and attempt to update the controller by searching for path to the target.
            self.current_grid = self.position_to_grid(input.position)
            self.controller = VerticalPositionController(
                self.grid_to_position(self.current_grid).z
            )
            self.update_controller()
        else:
            # The controller is already initialized. We only need to update the controller if the
            # current grid position has changed because no new path could be found otherwise.
            current_grid = self.position_to_grid(input.position)
            if current_grid != self.current_grid:
                self.current_grid = current_grid
                self.update_controller()

        # The controller is initialized and updated. Return the controller output.
        return self.controller(input)

    def position_to_grid(self, position: Vector3) -> Vector3:
        """
        Converts the given position to a discretized grid position.
        """
        return Vector3(
            int(position.x // self.grid_size.x),
            int(position.y // self.grid_size.y),
            int(position.z // self.grid_size.z),
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
            abs(position.x) < self.dimensions.x / 2
            and abs(position.y) < self.dimensions.y / 2
            and 0 <= position.z < self.dimensions.z
        )

    def update_controller(self):
        """
        Updates the current controller by searching for the best path to the target.
        """
        # Run search if this is the first time the controller is being updated.
        if self.parents is None:
            self.parents = self.search()

        # If there is no current grid position, do nothing.
        if self.current_grid is None:
            return

        # Find the next grid position in the path.
        next_grid = self.parents.get(self.current_grid, None)
        if next_grid is not None and next_grid != self.unreachable_grid:
            next_position = self.grid_to_position(next_grid)
            self.controller = VerticalPositionController(next_position.z)

    def grid_distance(self, grid_a: Vector3, grid_b: Vector3) -> float:
        """
        Calculates the euclidean distance between two grid positions.
        """
        return (
            self.grid_to_position(grid_b) - self.grid_to_position(grid_a)
        ).magnitude()

    def grid_cost(self, grid_a: Vector3, grid_b: Vector3) -> float:
        """
        Defines the cost between two adjacent grid positions. This is time it takes to go from one
        grid position to another taking into account the projected wind velocity. We assume that we
        can always reach the maximum vertical speed.
        """
        wind = self.wind_field(self.grid_to_position(grid_a))
        direction_unit = (grid_b - grid_a).normalize()
        velocity_z = math.copysign(self.max_vertical_speed, direction_unit.z)
        velocity = Vector3(wind.x, wind.y, velocity_z)
        return self.grid_distance(grid_a, grid_b) / velocity.dot(direction_unit)

    def search(self) -> Dict[Vector3, Union[Vector3, None]]:
        """
        Searches for the lowest cost path from all grid positions to the target using Dijkstra's
        algorithm. Builds a previous map of the reverse graph. If the target is not reachable, then
        the closest reachable position is targeted instead. Returns a map of grid positions to the
        next grid position in the path.
        """
        # Build the forward graph. Every grid position is connected to the unreachable grid position
        # with a cost proportional to the distance to the target and higher than any edges resulting
        # from neighboring reachable grid positions. Lastly, there is an edge of cost zero going 
        # from the unreachable grid position to the target grid position. This allows us to run a
        # single search pass on the reverse graph.
        forward_graph: Dict[Vector3, Dict[Vector3, Tuple[float, float]]] = {}
        for grid in self.grids():
            forward_graph[grid] = {
                neighbor: (0, self.grid_cost(grid, neighbor))
                for neighbor in self.neighbors(grid)
            }
            forward_graph[grid][self.unreachable_grid] = (
                self.grid_distance(grid, self.unreachable_grid),
                0,
            )
        forward_graph[self.unreachable_grid] = {self.target_grid: (0, 0)}

        # Build the reverse graph. We can clear the forward graph once this is done to save memory
        # since it will not be used again.
        reverse_graph: Dict[Vector3, Dict[Vector3, Tuple[float, float]]] = {}
        for grid, neighbors in forward_graph.items():
            for neighbor, cost in neighbors.items():
                if neighbor not in reverse_graph:
                    reverse_graph[neighbor] = {}
                reverse_graph[neighbor][grid] = cost
        forward_graph.clear()

        # Initialize search state. A tuple of two elements is used as the cost. The first element
        # is non-zero if the search traversed an edge from the unreachable grid. The second is the
        # normal cost to traverse between two neighbors. This means that we will always prefer to
        # not use an edge from the unreachable grid if possible.
        queue: List[Tuple[Tuple[float, float], Vector3]] = [((0, 0), self.target_grid)]
        costs: Dict[Vector3, Tuple[float, float]] = {self.target_grid: (0, 0)}
        parents: Dict[Vector3, Union[Vector3, None]] = {self.target_grid: None}

        # Run Dijkstra's search. We do not terminate early because we want to find the shortest path
        # from every possible grid position to the target (or the closest reachable position).
        while queue:
            cost, grid = heapq.heappop(queue)
            for neighbor in reverse_graph[grid]:
                if neighbor not in costs:
                    costs[neighbor] = (float("inf"), float("inf"))
                new_cost = (
                    costs[grid][0] + reverse_graph[grid][neighbor][0],
                    costs[grid][1] + reverse_graph[grid][neighbor][1],
                )
                if new_cost < costs[neighbor]:
                    parents[neighbor] = grid
                    costs[neighbor] = new_cost
                    heapq.heappush(queue, (new_cost, neighbor))

        # Return the parents map.
        return parents

    def grids(self) -> Generator[Vector3, None, None]:
        """
        Yields all grid positions within the bounds of the dimensions.
        """
        lower_bound = self.position_to_grid(
            Vector3(-self.dimensions.x / 2, -self.dimensions.y / 2, 0)
        )
        upper_bound = self.position_to_grid(
            Vector3(self.dimensions.x / 2, self.dimensions.y / 2, self.dimensions.z)
        )
        for x in range(int(lower_bound.x) + 1, int(upper_bound.x)):
            for y in range(int(lower_bound.y) + 1, int(upper_bound.y)):
                for z in range(int(lower_bound.z), int(upper_bound.z)):
                    yield Vector3(x, y, z)

    def neighbors(self, grid: Vector3) -> Generator[Vector3, None, None]:
        """
        Yields valid neighbors of the given grid position.
        """
        # Yield vertical neighbors if they are in bounds.
        for dz in (-1, 1):
            n = Vector3(grid.x, grid.y, grid.z + dz)
            if self.grid_in_bounds(n):
                yield n

        # Evaluate the wind field at the given grid position.
        wind = self.wind_field(self.grid_to_position(grid))

        # If the wind field is too close to zero at this grid position, assume no horizontal
        # neighbors because it is a dead zone.
        if math.isclose(wind.x, 0) and math.isclose(wind.y, 0):
            return

        # Compute horizontal neighbor by taking the dominant direction.
        if abs(wind.x) > abs(wind.y):
            dx = 1 if wind.x > 0 else -1
            dy = 0
        else:
            dx = 0
            dy = 1 if wind.y > 0 else -1

        # Yield the horizontal neighbor if it is in bounds.
        n = Vector3(grid.x + dx, grid.y + dy, grid.z)
        if self.grid_in_bounds(n):
            yield n
