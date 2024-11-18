import numpy as np
from balloon import Balloon
from bayes_opt import BayesianOptimization
from controller import (
    SequenceController,
    VerticalPositionController,
    VerticalVelocityController,
)
from simulation import run


def simulate_velocity(k_p, k_i, k_d):
    """
    Simulate the balloon with the given parameters for the velocity controller.
    """
    controller = SequenceController(
        (0.0, VerticalVelocityController(3.0, k_p, k_i, k_d)),
        (1000.0, VerticalVelocityController(-2.0, k_p, k_i, k_d)),
        (1500.0, VerticalVelocityController(1.0, k_p, k_i, k_d)),
        (2000.0, VerticalVelocityController(0.0, k_p, k_i, k_d)),
    )

    monitor = run(
        balloon=Balloon(),
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


def objective_velocity(k_p, k_i, k_d):
    """
    Objective function for the velocity controller tuning.
    """
    monitor, target_velocity = simulate_velocity(k_p, k_i, k_d)
    velocity = np.array([velocity.z for velocity in monitor.velocity])
    error = np.mean(np.abs(velocity - target_velocity))
    return -error


def tune_velocity():
    """
    Tunes the velocity controller.
    """
    bounds = {"k_p": (0, 200), "k_i": (0, 200), "k_d": (0, 200)}
    optimizer = BayesianOptimization(
        f=objective_velocity,
        pbounds=bounds,
        verbose=2,
    )
    optimizer.maximize(n_iter=100)

    if optimizer.max is not None:
        print(optimizer.max)
        params = optimizer.max["params"]
        monitor, _ = simulate_velocity(**params)
        monitor.plot_state()


def simulate_position(k_p, k_i, k_d):
    """
    Simulate the balloon with the given parameters for the position controller.
    """
    controller = SequenceController(
        (0.0, VerticalPositionController(1000.0, k_p, k_i, k_d)),
        (1500.0, VerticalPositionController(500.0, k_p, k_i, k_d)),
        (3000.0, VerticalPositionController(750.0, k_p, k_i, k_d)),
        (4500.0, VerticalPositionController(250.0, k_p, k_i, k_d)),
    )

    monitor = run(
        balloon=Balloon(),
        controller=controller,
        time_step=1.0,
        total_time=6000.0,
    )

    target_position = np.zeros(len(monitor.time))
    target_position[0:1500] = 1000.0
    target_position[1500:3000] = 500.0
    target_position[3000:4500] = 750.0
    target_position[4500:6000] = 250.0

    return monitor, target_position


def objective_position(k_p, k_i, k_d):
    """
    Objective function for the position controller.
    """
    monitor, target_position = simulate_position(k_p, k_i, k_d)
    position = np.array([position.z for position in monitor.position])
    error = np.mean(np.abs(position - target_position))
    return -error


def tune_position():
    """
    Tune the position controller.
    """
    bounds = {"k_p": (0, 0.02), "k_i": (0, 0.0), "k_d": (0, 0.0)}
    optimizer = BayesianOptimization(
        f=objective_position,
        pbounds=bounds,
        verbose=2,
    )
    optimizer.maximize(n_iter=100)

    if optimizer.max is not None:
        print(optimizer.max)
        params = optimizer.max["params"]
        monitor, _ = simulate_position(**params)
        monitor.plot_state()


if __name__ == "__main__":
    tune_velocity()
    tune_position()
