import numpy as np
from scipy.integrate import odeint
from typing import Tuple


class Balloon:
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

    def __init__(self, acceleration_field= lambda position: (0.0, 0.0, 0.0)):
        self.time: float = 0.0
        self.position = (0.0, 0.0, 0.0)
        self.velocity = (0.0, 0.0, 0.0)
        self.temperature = 1.0
        self.fuel = 0.0
        self.vent = 0.0
        self.acceleration_field = acceleration_field 

    def get_time(self):
        return self.time * self.k_ratio_time

    def get_position(self):
        return (
            self.position[0],
            self.position[1],
            self.position[2] * self.k_ratio_height,
        )

    def get_velocity(self):
        return (
            self.velocity[0],
            self.velocity[1],
            self.velocity[2] * self.k_ratio_height / self.k_ratio_time,
        )

    def get_temperature(self):
        return self.temperature * self.k_ratio_temperature - 273.15

    def set_fuel(self, value):
        self.fuel = value / self.k_ratio_fuel

    def set_vent(self, value):
        self.vent = value / self.k_ratio_vent

    def derivative(self, x, _):
        (
            position_x,
            position_y,
            position_z,
            velocity_x,
            velocity_y,
            velocity_z,
            temperature,
        ) = x
        temperature_at_height = 1.0 - self.k_delta * position_z

        ddt_position_x = velocity_x
        ddt_position_y = velocity_y
        ddt_position_z = velocity_z

        ddt_velocity_x = 0.0
        ddt_velocity_y = 0.0
        ddt_velocity_z = (
            self.k_alpha
            * self.k_mu
            * (temperature_at_height ** (self.k_gamma - 1.0))
            * (1.0 - (temperature_at_height / temperature))
            - self.k_mu
            - self.k_omega * velocity_z * abs(velocity_z)
        )

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

    def step(self, duration):
        time_delta = duration / self.k_ratio_time

        time_start = self.time
        time_end = time_start + time_delta
        time_span = (time_start, time_end)

        x_start = self.position + self.velocity + (self.temperature,)
        x = odeint(self.derivative, x_start, time_span)
        x_end = x[-1].tolist()

        self.position = tuple(x_end[0:3])
        self.velocity = tuple(x_end[3:6])
        self.temperature = x_end[6]

        if self.position[2] <= 0.0:
            self.position = (0.0, 0.0, 0.0)
            self.velocity = (0.0, 0.0, 0.0)

        self.time = time_end


def hab(x, t, alpha, gamma, mu, omega, delta, beta, u0, u1):
    # This function evaluates the ode right hand side
    #  for the hot air balloon simulation.

    # Calculate derivatives
    dxdt = np.zeros(3)
    Ths = 1 - delta * x[0]
    dxdt[0] = x[1]
    dxdt[1] = (
        alpha * mu * (Ths ** (gamma - 1)) * (1 - (Ths / x[2]))
        - mu
        - omega * x[1] * np.abs(x[1])
    )
    dxdt[2] = -(x[2] - Ths) * (beta + u1) + u0
    return dxdt


# Set hot air balloon parameters
alpha = 5.098
gamma = 5.257
mu = 0.1961
omega = 8.544
delta = 0.0255
beta = 0.01683

# Set the variable scaling parameters

hr = 1000  # meters
tr = 10.10  # seconds
Tr = 288.2  # K
fr = 4870  # %
pr = 1485  # %

# Initialize simulation variables

t0 = 0
tf = 5000
dt = 0.25
N = int(round((tf - t0) / dt) + 1)
# xstart   = [0.0 0.0 1.244] # neutral buoyancy
xstart = [0.0, 0.0, 1.000]  # ambient temperature
tstart = 0
fk = np.zeros(N)
pk = np.zeros(N)
uk = np.zeros((N, 2))
xk = np.zeros((N, 3))
yk = np.zeros((N, 3))
tm = np.zeros(N)
xk[0] = xstart
C = np.eye(3)
yk[0] = np.dot(C, xstart)
tm[0] = 0

# Initial conditions
fk = np.zeros(N)
pk = np.zeros(N)
fk[0:1000] = 0.0
pk[0:1000] = 0.0

# Warm up to nuetral buoyancy
fk[1000:3000] = 20.0
pk[1000:3000] = 0.0

# Takeoff
fk[3000:5000] = 25.0
pk[3000:5000] = 0.0

# Climb higher
fk[5000:7000] = 30.0
pk[5000:7000] = 0.0

# Open the vent
fk[7000:9000] = 30.0
pk[7000:9000] = 5.0

# Close the vent
fk[9000:11000] = 30.0
pk[9000:11000] = 0.0

# Descend
fk[11000:13000] = 22.0
pk[11000:13000] = 0.0

# Descend
fk[13000:15000] = 21.0
pk[13000:15000] = 0.0

# Land
fk[15000:17000] = 20.0
pk[15000:17000] = 0.0

# Close fuel valve and open the vent valve
fk[17000:N] = 0.0
pk[17000:N] = 5.0

# Make inputs dimensionless
uk[:, 0] = fk / fr
uk[:, 1] = pk / pr

# Run the simulation
for k in range(N):

    # Output iteration count
    # print('iteration ' + str(k))

    # Integrate the model for this time step
    parms = (alpha, gamma, mu, omega, delta, beta, uk[k, 0], uk[k, 1])
    tstop = tstart + dt
    tspan = [tstart, tstop]
    x = odeint(hab, xstart, tspan, parms)

    # Impose constraints when on the ground
    if x[-1, 0] <= 0.0:
        x[-1, 0] = 0.0
        x[-1, 1] = 0.0

    # Store solution
    xk[k] = x[-1]
    yk[k] = np.dot(C, xk[k])
    tm[k] = tr * tstop

    # Set initial state
    xstart = xk[k]
    tstart = tstop

# Recover dimensional outputs

hk = yk[:, 0] * hr
vk = yk[:, 1] * hr / tr
Tik = yk[:, 2] * Tr - 273.2

# Convert time to minutes

tmm = tm / 60

# Test
hk = []
vk = []
Tik = []
tmm = []

ballon = Balloon()

for k in range(N):
    if k == 1000:
        ballon.set_fuel(20.0)
    elif k == 3000:
        ballon.set_fuel(25.0)
    elif k == 5000:
        ballon.set_fuel(30.0)
    elif k == 7000:
        ballon.set_vent(5.0)
    elif k == 9000:
        ballon.set_vent(0.0)
    elif k == 11000:
        ballon.set_fuel(22.0)
    elif k == 13000:
        ballon.set_fuel(21.0)
    elif k == 15000:
        ballon.set_fuel(20.0)
    elif k == 17000:
        ballon.set_fuel(0.0)
        ballon.set_vent(5.0)

    ballon.step(dt * tr)

    tmm.append(ballon.get_time() / 60)
    hk.append(ballon.get_position()[2])
    vk.append(ballon.get_velocity()[2])
    Tik.append(ballon.get_temperature())

# Plot results
import matplotlib.pyplot as plt

plt.figure(1)

plt.subplot(5, 1, 1)
plt.plot(tmm, hk)
plt.xlim([1, tmm[-1]])
plt.ylim([-100, 4000])
plt.grid()
plt.ylabel("altitude (m)")

plt.subplot(5, 1, 2)
plt.plot(tmm, vk)
plt.xlim([1, tmm[-1]])
plt.ylim([-4, 4])
plt.grid()
plt.ylabel("velocity (m/s)")

plt.subplot(5, 1, 3)
plt.plot(tmm, Tik)
plt.xlim([1, tmm[-1]])
plt.ylim([14, 100])
plt.grid()
plt.ylabel("temperature (C)")

plt.subplot(5, 1, 4)
plt.plot(tmm, fk)
plt.xlim([1, tmm[-1]])
plt.ylim([-1, 31])
plt.grid()
plt.ylabel("fuel valve (%)")

plt.subplot(5, 1, 5)
plt.plot(tmm, pk)
plt.xlim([1, tmm[-1]])
plt.ylim([-1, 6])
plt.grid()
plt.ylabel("vent valve (%)")
plt.xlabel("time (minutes)")

plt.show()
