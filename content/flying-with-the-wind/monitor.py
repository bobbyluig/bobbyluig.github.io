from typing import Union

import matplotlib.pyplot as plt
from balloon import Balloon
from field import make_uniform_field

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

    def plot(self, filename: Union[str, None] = None):
        """
        Plots the balloon's state over time. If a filename is provided, the plot will be saved to
        that file. Otherwise, it will be shown.
        """
        _, axs = plt.subplots(5, 1, sharex=True)
        axs[0].plot(self.time, self.position)
        axs[0].set_ylabel("Position (m)")
        axs[1].plot(self.time, self.velocity)
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


if __name__ == "__main__":
    balloon = Balloon(make_uniform_field((5.0, 0.0, 0.0)))
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

    monitor.plot()
