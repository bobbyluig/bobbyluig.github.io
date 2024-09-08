from dataclasses import dataclass
from typing import Callable, Sequence, Tuple

from balloon import Balloon
from vector import Vector3
from simple_pid import PID


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


class FixedSequenceController:
    """
    A controller that returns a sequence of pre-defined outputs. The outputs are associated with
    times, and the controller will return the most recent output for which the time is less than or
    equal to the input time.
    """

    def __init__(self, sequence: Sequence[Tuple[float, ControllerOutput]]):
        """
        Initializes the controller with a sequence of outputs.
        """
        self.sequence = sorted(sequence, key=lambda t: t[0], reverse=True)
        self.last_output = ControllerOutput(fuel=0.0, vent=0.0)

    def __call__(self, input: ControllerInput) -> ControllerOutput:
        """
        Returns the controller output for the given input.
        """
        while self.sequence and self.sequence[-1][0] <= input.time:
            self.last_output = self.sequence.pop()[1]

        return self.last_output


class TimeSwitchingController:
    """
    A controller that switches between different controllers based on time.
    """

    def __init__(self, controllers: Sequence[Tuple[float, Controller]]):
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


class PIDController:
    """
    A controller that uses a PID algorithm to control the vent and fuel of the balloon.
    """

    def __init__(
        self,
        set_point: float,
        input_fn: Callable[[ControllerInput], float],
        k_p: float = 1.0,
        k_i: float = 0.0,
        k_d: float = 0.0,
    ):
        """
        Initializes the controller with the given tuning parameters.
        """
        self.now = 0
        self.input_fn = input_fn
        self.pid = PID(
            Kp=k_p,
            Ki=k_i,
            Kd=k_d,
            setpoint=set_point,
            sample_time=1,
            output_limits=(-1, 1),
            time_fn=lambda: self.now,
        )

    def __call__(self, input: ControllerInput) -> ControllerOutput:
        """
        Returns the controller output for the given input.
        """
        self.now = input.time

        output = self.pid(self.input_fn(input))
        if output is None:
            output = 0

        if output < 0:
            return ControllerOutput(fuel=0, vent=-round(10*output)*10)
        else:
            return ControllerOutput(fuel=100*output, vent=0)
