from dataclasses import dataclass
from typing import Callable

from balloon import Balloon
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


def make_pid_controller(target_height: float) -> Controller:
    """
    Creates a PID controller for a given target height.
    """

    k_p = 0.1
    k_i = 0.01
    k_d = 0.1

    integral = 0

    def controller(input: ControllerInput) -> ControllerOutput:
        nonlocal integral
        error = target_height - input.position[2]
        integral += error
        derivative = (error - (input.position[2] - input.velocity[2] * 0.1)) / 0.1
        target_velocity = max(min(-error * k_p - integral * k_i - derivative * k_d, 2), -2)
        fuel = max(min(target_velocity - input.velocity[2], 40), 0)
        return ControllerOutput(fuel, 0)

    return controller

