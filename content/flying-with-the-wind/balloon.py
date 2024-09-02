from dataclasses import dataclass
from typing import List, Sequence, cast

import numpy as np
import numpy.typing as npt
from field import Field3, make_uniform_field
from scipy.integrate import odeint
from vector import Vector3


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
    k_ratio_distance = 1000.0  # meters
    k_ratio_time = 10.1  # seconds
    k_ratio_temperature = 288.2  # kelvin
    k_ratio_fuel = 4870.0  # %
    k_ratio_vent = 1485.0  # %

    def __init__(self, wind_field: Field3 = make_uniform_field((0.0, 0.0, 0.0))):
        """
        Initializes the balloon with the given acceleration field.
        """
        self.time: float = 0.0
        self.position: Vector3 = (0.0, 0.0, 0.0)
        self.velocity: Vector3 = (0.0, 0.0, 0.0)
        self.temperature: float = 1.0
        self.fuel: float = 0.0
        self.vent: float = 0.0
        self.wind_field = wind_field

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
            self.position[0] * self.k_ratio_distance,
            self.position[1] * self.k_ratio_distance,
            self.position[2] * self.k_ratio_distance,
        )

    def get_velocity(self) -> Vector3:
        """
        Returns the current velocity in meters per second.
        """
        return (
            self.velocity[0] * self.k_ratio_distance / self.k_ratio_time,
            self.velocity[1] * self.k_ratio_distance / self.k_ratio_time,
            self.velocity[2] * self.k_ratio_distance / self.k_ratio_time,
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
        Returns the derivative for computing the balloon's simulation trajectory.
        """
        # Unpack the state vector.
        x_array = np.array(x, dtype=np.float64)
        position = x_array[0:3]
        velocity = x_array[3:6]
        temperature = x_array[6]

        # Evaluate the wind field at the current position.
        wind_velocity = (
            np.array(self.wind_field(tuple(position)), dtype=np.float64)
            / self.k_ratio_distance
            * self.k_ratio_time
        )
        relative_wind_velocity = wind_velocity - velocity

        # Evaluate the temperature at the current height.
        temperature_at_height = 1.0 - self.k_delta * position[2]

        # Compute the derivative of position.
        ddt_position = velocity

        # Compute the derivative of velocity. First, account for the wind speed and drag force.
        # Then, apply the buoyancy force.
        ddt_velocity = (
            self.k_omega * relative_wind_velocity**2 * np.sign(relative_wind_velocity)
        )
        ddt_velocity[2] += (
            self.k_alpha
            * self.k_mu
            * (temperature_at_height ** (self.k_gamma - 1.0))
            * (1.0 - (temperature_at_height / temperature))
            - self.k_mu
            - self.k_omega * velocity[2] ** 2 * np.sign(velocity[2])
        )

        # Compute the derivative of temperature.
        ddt_temperature = (
            -(temperature - temperature_at_height) * (self.k_beta + self.vent)
            + self.fuel
        )

        # Concatenate the derivatives into a single vector.
        return np.concatenate(
            (ddt_position, ddt_velocity, [ddt_temperature]), dtype=np.float64
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
