from dataclasses import dataclass
from typing import List, Sequence, cast

import numpy as np
import numpy.typing as npt
from scipy.integrate import odeint
from shared import Field3, Vector3, make_zero_field


class Balloon:
    """
    Represents a hot air balloon in 3D space.
    """

    # Simulation parameters.
    k_alpha = 5.098
    k_beta = 0.01683
    k_delta = 0.0255
    k_gamma = 5.257
    k_mu = 0.1961
    k_omega = 8.544

    # Scaling parameters.
    k_ratio_height = 1000.0  # meters
    k_ratio_time = 10.1  # seconds
    k_ratio_temperature = 288.2  # kelvin
    k_ratio_fuel = 4870.0  # %
    k_ratio_vent = 1485.0  # %

    def __init__(self, acceleration_field: Field3 = make_zero_field()):
        """
        Initializes the balloon with the given acceleration field.
        """
        self.time: float = 0.0
        self.position: Vector3 = (0.0, 0.0, 0.0)
        self.velocity: Vector3 = (0.0, 0.0, 0.0)
        self.temperature: float = 1.0
        self.fuel: float = 0.0
        self.vent: float = 0.0
        self.acceleration_field = acceleration_field

    def get_time(self) -> float:
        """
        Returns the current time in seconds.
        """
        return self.time * self.k_ratio_time

    def get_position(self) -> Vector3:
        """
        Returns the current position in meters.
        """
        return (
            self.position[0],
            self.position[1],
            self.position[2] * self.k_ratio_height,
        )

    def get_velocity(self) -> Vector3:
        """
        Returns the current velocity in meters per second.
        """
        return (
            self.velocity[0],
            self.velocity[1],
            self.velocity[2] * self.k_ratio_height / self.k_ratio_time,
        )

    def get_temperature(self) -> float:
        """
        Returns the current temperature in kelvin.
        """
        return self.temperature * self.k_ratio_temperature - 273.15

    def get_fuel(self) -> float:
        """
        Returns the current fuel percentage.
        """
        return self.fuel * self.k_ratio_fuel

    def get_vent(self) -> float:
        """
        Returns the current vent percentage.
        """
        return self.vent * self.k_ratio_vent

    def set_fuel(self, value: float):
        """
        Sets the current fuel percentage.
        """
        self.fuel = value / self.k_ratio_fuel

    def set_vent(self, value: float):
        """
        Sets the current vent percentage.
        """
        self.vent = value / self.k_ratio_vent

    def derivative(self, x: Sequence[float], _) -> npt.NDArray:
        """
        Returns the derivative of the balloon's state in the given state.
        """
        (
            position_x,
            position_y,
            position_z,
            velocity_x,
            velocity_y,
            velocity_z,
            temperature,
        ) = x
        acceleration_x, acceleration_y, acceleration_z = self.acceleration_field(
            (position_x, position_y, position_z)
        )
        temperature_at_height = 1.0 - self.k_delta * position_z

        ddt_position_x = velocity_x
        ddt_position_y = velocity_y
        ddt_position_z = velocity_z

        ddt_velocity_x = acceleration_x
        ddt_velocity_y = acceleration_y
        ddt_velocity_z = (
            self.k_alpha
            * self.k_mu
            * (temperature_at_height ** (self.k_gamma - 1.0))
            * (1.0 - (temperature_at_height / temperature))
            - self.k_mu
            - self.k_omega * velocity_z * abs(velocity_z)
        ) + acceleration_z

        ddt_temperature = (
            -(temperature - temperature_at_height) * (self.k_beta + self.vent)
            + self.fuel
        )

        return np.array(
            (
                ddt_position_x,
                ddt_position_y,
                ddt_position_z,
                ddt_velocity_x,
                ddt_velocity_y,
                ddt_velocity_z,
                ddt_temperature,
            ),
            dtype=np.float64,
        )

    def step(self, duration: float):
        """
        Simulates the balloon for the given duration in seconds.
        """
        time_delta = duration / self.k_ratio_time

        time_start = self.time
        time_end = time_start + time_delta
        time_span = (time_start, time_end)

        x_start = self.position + self.velocity + (self.temperature,)
        x = odeint(self.derivative, x_start, time_span)
        x_end: List[float] = x[-1].tolist()

        self.position = cast(Vector3, tuple(x_end[0:3]))
        self.velocity = cast(Vector3, tuple(x_end[3:6]))
        self.temperature = x_end[6]

        if self.position[2] <= 0.0:
            self.position = (0.0, 0.0, 0.0)
            self.velocity = (0.0, 0.0, 0.0)

        self.time = time_end
