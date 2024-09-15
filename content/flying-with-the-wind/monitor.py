from typing import List, Union, cast

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
        axs[2].set_ylabel("Temperature (°C)")
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

    def plot_trajectory(
        self, num_points: int = 5000, filename: Union[str, None] = None
    ):
        """
        Plots the balloon's trajectory over time, using color as time.
        """
        num_points = min(num_points, len(self.position))
        indices = np.linspace(0, len(self.position) - 1, num_points, dtype=np.int64)
        points = np.array(self.position)[indices].reshape(-1, 3)
        time = np.array(self.time)[indices]

        fig = plt.figure()
        ax: Axes3D = cast(Axes3D, fig.add_subplot(projection="3d"))
        ax.scatter(
            points[:, 0],
            points[:, 1],
            points[:, 2], # type: ignore
            c=time,
            cmap="viridis",
            s=1,
        )
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_zlabel("z (m)")
        ax.set_aspect("equal")

        if filename:
            plt.savefig(filename)
        else:
            plt.show()

    def animate_trajectory(self, num_points: int = 5000, filename: Union[str, None] = None):
        """
        Animates the balloon's trajectory over time.
        """
        num_points = min(num_points, len(self.position))
        indices = np.linspace(
            0, len(self.position) - 1, num_points, dtype=np.int64, endpoint=False
        )
        points = np.array(self.position)[indices].reshape(-1, 3)

        fig = plt.figure()
        ax: Axes3D = cast(Axes3D, fig.add_subplot(projection="3d"))
        (line,) = ax.plot([], [], [])
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_zlabel("z (m)")
        limit = np.max(np.ptp(points, axis=0))
        center = (points.max(axis=0) + points.min(axis=0)) / 2
        ax.set_xlim3d(center[0] - limit / 2, center[0] + limit / 2)
        ax.set_ylim3d(center[1] - limit / 2, center[1] + limit / 2)
        ax.set_zlim3d(0, limit)
        ax.set_aspect("equal")

        counter = ax.text2D(
            0.01, 0.99, "", transform=ax.transAxes, fontsize=16, ha="left", va="top"
        )

        def update(num, line, points):
            line.set_data(points[:num, 0], points[:num, 1])
            line.set_3d_properties(points[:num, 2])
            counter.set_text(f"Time: {(self.time[num] / 60):.2f} minutes")
            return (line, counter)

        ani = FuncAnimation(
            fig, update, num_points, fargs=(line, points), interval=5, blit=True
        )

        if filename:
            ani.save(filename, writer="ffmpeg")
        else:
            plt.show()
