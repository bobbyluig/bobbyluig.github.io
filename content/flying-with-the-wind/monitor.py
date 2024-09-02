from typing import Union

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from balloon import Balloon
from field import make_random_field, make_uniform_field
from vector import Vector3


class Monitor:
    """
    Represents a monitor for a balloon.
    """

    def __init__(self):
        """
        Initializes the monitor with an empty state.
        """
        self.time = []
        self.position = []
        self.velocity = []
        self.temperature = []
        self.fuel = []
        self.vent = []

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
        axs[1].plot(self.time, [v.z for v in self.velocity])
        axs[1].set_ylabel("Velocity (m/s)")
        axs[2].plot(self.time, self.temperature)
        axs[2].set_ylabel("Temperature (°C)")
        axs[3].plot(self.time, self.fuel)
        axs[3].set_ylabel("Fuel (%)")
        axs[4].plot(self.time, self.vent)
        axs[4].set_ylabel("Vent (%)")
        axs[4].set_xlabel("Time (s)")

        if filename:
            plt.savefig(filename)
        else:
            plt.show()

    def plot_trajectory(
        self, num_points: int = 5000, filename: Union[str, None] = None
    ):
        """
        Plots the balloon's x/y trajectory over time, using color as time.
        """
        num_points = min(num_points, len(self.position))
        indices = np.linspace(0, len(self.position) - 1, num_points, dtype=np.int64)
        points = np.array(self.position)[indices].reshape(-1, 3)
        time = np.array(self.time)[indices]

        fig = plt.figure()
        ax = fig.add_subplot(projection="3d")
        ax.scatter(
            points[:, 0],
            points[:, 1],
            points[:, 2],
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

    def animate_trajectory(self, n: int = 5000, filename: Union[str, None] = None):
        """
        Animates the balloon's trajectory over time.
        """
        num_points = min(n, len(self.position))
        indices = np.linspace(
            0, len(self.position) - 1, num_points, dtype=np.int64, endpoint=False
        )
        points = np.array(self.position)[indices].reshape(-1, 3)

        fig = plt.figure()
        ax = fig.add_subplot(projection="3d")
        (line,) = ax.plot([], [], [])
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_zlabel("z (m)")
        ax.set_xlim3d(points[:, 0].min(), points[:, 0].max())
        ax.set_ylim3d(points[:, 1].min(), points[:, 1].max())
        ax.set_zlim3d(points[:, 2].min(), points[:, 2].max())
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


if __name__ == "__main__":
    np.random.seed(0)
    balloon = Balloon(
        make_random_field(
            Vector3(5.0, 5.0, 0.0),
            Vector3(10000.0, 10000.0, 10000.0),
        )
    )
    monitor = Monitor()

    tr = 10.10  # seconds
    # Initialize simulation variables

    t0 = 0
    tf = 5000
    dt = 0.25
    N = int(round((tf - t0) / dt) + 1)

    # Test
    for k in range(N):
        if k == 1000:
            balloon.set_fuel(20.0)
        elif k == 3000:
            balloon.set_fuel(25.0)
        elif k == 5000:
            balloon.set_fuel(30.0)
        elif k == 7000:
            balloon.set_vent(5.0)
        elif k == 9000:
            balloon.set_vent(0.0)
        elif k == 11000:
            balloon.set_fuel(22.0)
        elif k == 13000:
            balloon.set_fuel(21.0)
        elif k == 15000:
            balloon.set_fuel(20.0)
        elif k == 17000:
            balloon.set_fuel(0.0)
            balloon.set_vent(5.0)

        balloon.step(dt * tr)
        monitor.update(balloon)
        print(k, N)

    monitor.animate_trajectory()
