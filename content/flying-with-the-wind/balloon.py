from typing import Callable, List

import numpy as np
from field import Field3, UniformField
from numba import jit
from scipy.integrate import odeint
from vector import Vector3


class Balloon:
    """
    Represents a hot air balloon in 3D space. Much of the dynamics is based on the script here:
    https://github.com/APMonitor/applications/blob/master/ASEE_Summer_School_2017/Demo2_Hot_Air_Balloon/Python/HotAirBalloon.py.
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

    def __init__(self, wind_field: Field3 = UniformField(Vector3(0.0, 0.0, 0.0))):
        """
        Initializes the balloon with the given acceleration field.
        """
        # Initialize mutable state.
        self.time: float = 0.0
        self.position: Vector3 = Vector3(0.0, 0.0, 0.0)
        self.velocity: Vector3 = Vector3(0.0, 0.0, 0.0)
        self.temperature: float = 1.0
        self.fuel: float = 0.0
        self.vent: float = 0.0

        # Initialize immutable state.
        self.wind_field: Field3 = wind_field

        # Compile the derivative helper.
        self.derivative_helper: Callable[
            [np.ndarray, np.ndarray, float, float], np.ndarray
        ] = self.make_derivative_helper()

    def get_time(self) -> float:
        """
        Returns the current time in seconds.
        """
        return self.time * self.k_ratio_time

    def get_position(self) -> Vector3:
        """
        Returns the current position in meters.
        """
        return self.position * self.k_ratio_distance

    def get_velocity(self) -> Vector3:
        """
        Returns the current velocity in meters per second.
        """
        return self.velocity * (self.k_ratio_distance / self.k_ratio_time)

    def get_temperature(self) -> float:
        """
        Returns the current temperature in kelvin.
        """
        return self.temperature * self.k_ratio_temperature

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

    def derivative(self, x: np.ndarray, _) -> np.ndarray:
        """
        Returns the derivative for computing the balloon's simulation trajectory.
        """
        # Evaluate the wind velocity at the current position.
        dimensionless_position = Vector3(*x[0:3])
        wind_velocity = np.array(
            self.wind_field(dimensionless_position * self.k_ratio_distance)
            * (self.k_ratio_time / self.k_ratio_distance),
            dtype=np.float64,
        )

        # Defer to the compiled derivative helper.
        return self.derivative_helper(x, wind_velocity, self.fuel, self.vent)

    @staticmethod
    def make_derivative_helper():
        """
        Returns a compiled derivative helper function with all constants captured.
        """
        # Capture constants in closure.
        k_alpha = Balloon.k_alpha
        k_beta = Balloon.k_beta
        k_delta = Balloon.k_delta
        k_gamma = Balloon.k_gamma
        k_mu = Balloon.k_mu
        k_omega = Balloon.k_omega

        # Define the function to be compiled.
        def derivative_helper(
            x: np.ndarray,
            wind_velocity: np.ndarray,
            fuel: float,
            vent: float,
        ) -> np.ndarray:
            # Unpack the state vector.
            position = x[0:3]
            velocity = x[3:6]
            temperature = x[6]

            # Evaluate the relatively wind velocity.
            relative_wind_velocity = wind_velocity - velocity

            # Evaluate the temperature at the current height.
            temperature_at_height = 1.0 - k_delta * position[2]

            # Compute the derivative of position.
            ddt_position = velocity

            # Compute the derivative of velocity. First, account for the drag force due to wind.
            # Then, apply buoyancy force and gravitation force.
            ddt_velocity = (
                k_omega * relative_wind_velocity**2 * np.sign(relative_wind_velocity)
            )
            ddt_velocity[2] += (
                k_alpha
                * k_mu
                * (temperature_at_height ** (k_gamma - 1.0))
                * (1.0 - (temperature_at_height / temperature))
                - k_mu
            )

            # Compute the derivative of temperature.
            ddt_temperature = (
                -(temperature - temperature_at_height) * (k_beta + vent) + fuel
            )

            # Concatenate the derivatives into a single vector.
            ddt_state = np.empty(7, dtype=np.float64)
            ddt_state[0:3] = ddt_position
            ddt_state[3:6] = ddt_velocity
            ddt_state[6] = ddt_temperature
            return ddt_state

        # Return the compiled function.
        return jit(derivative_helper)

    def step(self, duration: float):
        """
        Simulates the balloon for the given duration in seconds.
        """
        time_delta = duration / self.k_ratio_time

        time_start = self.time
        time_end = time_start + time_delta
        time_span = [time_start, time_end]

        x_start = np.empty(7, dtype=np.float64)
        x_start[0:3] = self.position
        x_start[3:6] = self.velocity
        x_start[6] = self.temperature
        x_end = odeint(self.derivative, x_start, time_span)[-1]

        self.position = Vector3(*x_end[0:3])
        self.velocity = Vector3(*x_end[3:6])
        self.temperature = x_end[6]

        if self.position.z <= 0.0:
            self.position = Vector3(self.position.x, self.position.y, 0.0)
            self.velocity = Vector3(0.0, 0.0, 0.0)

        self.time = time_end
