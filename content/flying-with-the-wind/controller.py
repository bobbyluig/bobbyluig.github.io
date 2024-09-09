import math
from dataclasses import dataclass
from typing import Callable, Tuple

from balloon import Balloon
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


class VelocityController:
    """
    A controller that targets a constant vertical velocity. It embeds a PID controller.
    """

    def __init__(
        self,
        target_velocity: float,
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
            setpoint=target_velocity,
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

        if output < 0:
            return ControllerOutput(fuel=0, vent=-100 * output)
        else:
            return ControllerOutput(fuel=100 * output, vent=0)


class PositionController:
    """
    A controller that targets a constant vertical position. It embeds a PID controller whose output
    is fed into a VelocityController. Velocity input is discretized to 0.1 m/s and capped at 4 m/s
    in either direction.
    """

    def __init__(
        self,
        target_position: float,
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
            setpoint=target_position,
            sample_time=1,
            output_limits=(-1.0, 1.0),
            time_fn=lambda: self.now,
        )
        self.last_velocity = 0.0
        self.last_velocity_controller = VelocityController(0.0)

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
        self.last_velocity_controller = VelocityController(output)
        return self.last_velocity_controller(input)
