from dataclasses import dataclass
from typing import Callable

from balloon import Balloon
from vector import Vector3


@dataclass
class ControllerInput:
    """
    Represents inputs for the controller.
    """

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


def make_proportional_controller(target_height: float, k_p: float = 0.1) -> Controller:
    """
    Returns a controller that targets a given height using a proportional controller.
    """

    def controller(controller_input: ControllerInput) -> ControllerOutput:
        height_diff = target_height - controller_input.position[2]
        fuel = -k_p * height_diff
        vent = k_p * height_diff
        return ControllerOutput(fuel=min(max(fuel, 0), 1), vent=min(max(vent, 0), 1))

    return controller
