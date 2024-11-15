import copy
from typing import List, Union, cast, Tuple

import matplotlib.pyplot as plt
import numpy as np
from balloon import Balloon
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D
from vector import Vector3


class Monitor:
    """
    Represents a monitor for a balloon.
    """

    def __init__(self):
        """
        Initializes the monitor with an empty state.
        """
        self.time: List[float] = []
        self.position: List[Vector3] = []
        self.velocity: List[Vector3] = []
        self.temperature: List[float] = []
        self.fuel: List[float] = []
        self.vent: List[float] = []

    def update(self, balloon: Balloon):
        """
        Updates the monitor's internal state. This should be called for every simulation step after
        the balloon's state has been updated.
        """
        self.time.append(balloon.get_time())
        self.position.append(balloon.get_position())
        self.velocity.append(balloon.get_velocity())
        self.temperature.append(balloon.get_temperature())
        self.fuel.append(balloon.get_fuel())
        self.vent.append(balloon.get_vent())

    def plot_state(self, filename: Union[str, None] = None):
        """
        Plots the balloon's state over time. If a filename is provided, the plot will be saved to
        that file. Otherwise, it will be shown.
        """
        _, axs = plt.subplots(5, 1, sharex=True)
        axs[0].plot(self.time, [p.z for p in self.position])
        axs[0].set_ylabel("Height (m)")
        axs[0].grid(True)
        axs[1].plot(self.time, [v.z for v in self.velocity])
        axs[1].set_ylabel("Velocity (m/s)")
        axs[1].grid(True)
        axs[2].plot(self.time, self.temperature)
        axs[2].set_ylabel("Temperature (K)")
        axs[2].grid(True)
        axs[3].plot(self.time, self.fuel)
        axs[3].set_ylabel("Fuel (%)")
        axs[3].grid(True)
        axs[4].plot(self.time, self.vent)
        axs[4].set_ylabel("Vent (%)")
        axs[4].set_xlabel("Time (s)")
        axs[4].grid(True)

        if filename:
            plt.savefig(filename)
        else:
            plt.show()

    def plot_trajectory(self, filename: Union[str, None] = None):
        """
        Plots the balloon's trajectory over time, using color as time.
        """
        points = np.array(self.position)
        time = np.array(self.time)
        x_bounds, y_bounds, z_bounds = self.get_square_bounds()

        fig = plt.figure()
        ax: Axes3D = cast(Axes3D, fig.add_subplot(projection="3d"))
        ax.scatter(
            points[:, 0],
            points[:, 1],
            points[:, 2],  # type: ignore
            c=time,
            cmap="viridis",
            s=1,
        )
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_zlabel("z (m)")
        ax.set_xlim3d(*x_bounds)
        ax.set_ylim3d(*y_bounds)
        ax.set_zlim3d(*z_bounds)
        ax.set_aspect("equal")

        if filename:
            plt.savefig(filename)
        else:
            plt.show()

    def animate_trajectory(self, duration: float, filename: Union[str, None] = None):
        """
        Animates the balloon's trajectory over time. The duration is in seconds.
        """
        points = np.array(self.position)
        x_bounds, y_bounds, z_bounds = self.get_square_bounds()

        fig = plt.figure()
        ax: Axes3D = cast(Axes3D, fig.add_subplot(projection="3d"))
        (line,) = ax.plot([], [], [])
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_zlabel("z (m)")
        ax.set_xlim3d(*x_bounds)
        ax.set_ylim3d(*y_bounds)
        ax.set_zlim3d(*z_bounds)
        ax.set_aspect("equal")

        counter = ax.text2D(
            0.01, 0.99, "", transform=ax.transAxes, fontsize=16, ha="left", va="top"
        )

        def update(num, line, points):
            line.set_data(points[:num, 0], points[:num, 1])
            line.set_3d_properties(points[:num, 2])
            counter.set_text(f"Time: {(self.time[num] / 60):.2f} minutes")
            return (line, counter)

        interval = int(1000 * duration / len(points))
        ani = FuncAnimation(
            fig, update, len(points), fargs=(line, points), interval=interval, blit=True
        )

        if filename:
            ani.save(filename, writer="ffmpeg")
        else:
            plt.show()

    def get_square_bounds(
        self,
    ) -> Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]:
        """
        Returns the square bounds of the position.
        """
        points = np.array(self.position).reshape(-1, 3)
        limit = np.max(np.ptp(points, axis=0))
        center = (points.max(axis=0) + points.min(axis=0)) / 2

        x_bounds = (center[0] - limit / 2, center[0] + limit / 2)
        y_bounds = (center[1] - limit / 2, center[1] + limit / 2)
        z_bounds = (0, limit)
        return x_bounds, y_bounds, z_bounds

    def interpolate(self, max_points: int) -> "Monitor":
        """
        Returns a monitor containing interpolated data with a fixed maximum number of points.
        """
        if len(self.time) <= max_points:
            return copy.deepcopy(self)

        np_time = np.array(self.time)
        np_position = np.array(self.position)
        np_velocity = np.array(self.velocity)
        np_temperature = np.array(self.temperature)
        np_fuel = np.array(self.fuel)
        np_vent = np.array(self.vent)

        i_time = np.linspace(np_time[0], np_time[-1], num=max_points)
        i_position = np.array(
            [np.interp(i_time, np_time, np_position[:, i]) for i in range(3)]
        ).T
        i_velocity = np.array(
            [np.interp(i_time, np_time, np_velocity[:, i]) for i in range(3)]
        ).T
        i_temperature = np.interp(i_time, np_time, np_temperature)
        i_fuel = np.interp(i_time, np_time, np_fuel)
        i_vent = np.interp(i_time, np_time, np_vent)

        monitor = Monitor()
        monitor.time = i_time.tolist()
        monitor.position = [Vector3(*p) for p in i_position.tolist()]
        monitor.velocity = [Vector3(*v) for v in i_velocity.tolist()]
        monitor.temperature = i_temperature.tolist()
        monitor.fuel = i_fuel.tolist()
        monitor.vent = i_vent.tolist()

        return monitor
