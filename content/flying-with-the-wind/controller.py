from dataclasses import dataclass
from typing import Callable, Sequence, Tuple

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


class SequenceController:
    def __init__(self, sequence: Sequence[Tuple[float, ControllerOutput]]):
        self.sequence = sorted(sequence, key=lambda t: t[0], reverse=True)
        self.last_output = ControllerOutput(fuel=0.0, vent=0.0)

    def __call__(self, input: ControllerInput) -> ControllerOutput:
        while self.sequence and self.sequence[-1][0] <= input.time:
            self.last_output = self.sequence.pop()[1]

        return self.last_output
