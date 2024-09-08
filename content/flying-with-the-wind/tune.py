import numpy as np

from bayes_opt import BayesianOptimization
from balloon import Balloon
from controller import PIDController, TimeSwitchingController
from field import make_uniform_field
from simulation import run
from vector import Vector3


def make_velocity_pid_controller(k_p, k_i, k_d, target_velocity):
    return PIDController(
        target_velocity,
        lambda controller_input: controller_input.velocity.z,
        k_p=k_p,
        k_i=k_i,
        k_d=k_d,
    )


def simulate(k_p, k_i, k_d):
    balloon = Balloon(make_uniform_field(Vector3(0.0, 0.0, 0.0)))

    controller = TimeSwitchingController(
        [
            (0.0, make_velocity_pid_controller(k_p, k_i, k_d, 3.0)),
            (1000.0, make_velocity_pid_controller(k_p, k_i, k_d, -2.0)),
            (1500.0, make_velocity_pid_controller(k_p, k_i, k_d, 1.0)),
            (2000.0, make_velocity_pid_controller(k_p, k_i, k_d, -1.0)),
        ]
    )

    monitor = run(
        balloon=balloon,
        controller=controller,
        time_step=1.0,
        total_time=2500.0,
    )

    target_velocity = np.zeros(len(monitor.time))
    target_velocity[0:1000] = 3.0
    target_velocity[1000:1500] = -2.0
    target_velocity[1500:2000] = 1.0
    target_velocity[2000:2500] = -1.0

    return monitor, target_velocity


def objective(k_p, k_i, k_d):
    monitor, target_velocity = simulate(k_p, k_i, k_d)
    velocity = np.array([velocity.z for velocity in monitor.velocity])
    above_target_velocity = np.abs(velocity) > np.abs(target_velocity)
    below_target_velocity = ~above_target_velocity
    error = np.sum(
        np.abs(velocity[below_target_velocity] - target_velocity[below_target_velocity])
    )
    error += 2 * np.sum(
        np.abs(velocity[above_target_velocity] - target_velocity[above_target_velocity])
    )
    return -error


def tune():
    bounds = {"k_p": (0, 200), "k_i": (0, 200), "k_d": (0, 200)}
    optimizer = BayesianOptimization(
        f=objective,
        pbounds=bounds,
        verbose=2,
    )
    optimizer.probe({'k_d': 195.44582449686348, 'k_i': 40.43108955096633, 'k_p': 14.19792930422495})
    optimizer.maximize(n_iter=50)

    if optimizer.max is not None:
        print(optimizer.max)
        params = optimizer.max["params"]
        monitor, _ = simulate(**params)
        monitor.plot_state()


if __name__ == "__main__":
    tune()


# {'target': -825.6118759849973, 'params': {'k_d': 196.79360086849547, 'k_i': 40.87914486929718, 'k_p': 14.701424506041244}}
# {'target': -816.1735224939667, 'params': {'k_d': 195.44582449686348, 'k_i': 40.43108955096633, 'k_p': 14.19792930422495}}