import numpy as np
from balloon import Balloon
from bayes_opt import BayesianOptimization
from controller import PositionController, SequenceController, VelocityController
from simulation import run


def simulate_velocity(k_p, k_i, k_d):
    controller = SequenceController(
        (0.0, VelocityController(3.0, k_p, k_i, k_d)),
        (1000.0, VelocityController(-2.0, k_p, k_i, k_d)),
        (1500.0, VelocityController(1.0, k_p, k_i, k_d)),
        (2000.0, VelocityController(0.0, k_p, k_i, k_d)),
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
    monitor, target_velocity = simulate_velocity(k_p, k_i, k_d)
    velocity = np.array([velocity.z for velocity in monitor.velocity])
    error = np.mean(np.abs(velocity - target_velocity))
    return -error


def tune_velocity():
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

    # Sample Outputs:
    # {'target': -0.4672799464529887, 'params': {'k_d': 124.25863289470911, 'k_i': 34.790141360779124, 'k_p': 10.874548503904872}}


def simulate_position(k_p, k_i, k_d):
    controller = SequenceController(
        (0.0, PositionController(2000.0, k_p, k_i, k_d)),
        (1500.0, PositionController(1000.0, k_p, k_i, k_d)),
        (3000.0, PositionController(2500.0, k_p, k_i, k_d)),
        (4500.0, PositionController(2000.0, k_p, k_i, k_d)),
    )

    monitor = run(
        balloon=Balloon(),
        controller=controller,
        time_step=1.0,
        total_time=6000.0,
    )

    target_position = np.zeros(len(monitor.time))
    target_position[0:1500] = 2000.0
    target_position[1500:3000] = 1000.0
    target_position[3000:4500] = 2500.0
    target_position[4500:6000] = 2000.0

    return monitor, target_position


def objective_position(k_p, k_i, k_d):
    monitor, target_position = simulate_position(k_p, k_i, k_d)
    position = np.array([position.z for position in monitor.position])
    error = np.mean(np.abs(position - target_position))
    return -error


def tune_position():
    bounds = {"k_p": (0, 0.02), "k_i": (0, 0), "k_d": (0, 0)}
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

    # Sample Outputs:
    # {'target': -220.9116116824867, 'params': {'k_d': 0.0, 'k_i': 0.0, 'k_p': 0.008965567179058827}}

if __name__ == "__main__":
    tune_velocity()
    tune_position()
