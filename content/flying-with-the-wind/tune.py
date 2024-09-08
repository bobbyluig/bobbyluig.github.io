import numpy as np

from bayes_opt import BayesianOptimization
from balloon import Balloon
from controller import VelocityController, SequenceController
from field import make_uniform_field
from simulation import run
from vector import Vector3


def simulate(k_p, k_i, k_d):
    balloon = Balloon(make_uniform_field(Vector3(0.0, 0.0, 0.0)))

    controller = SequenceController(
        (0.0, VelocityController(3.0, k_p, k_i, k_d)),
        (1000.0, VelocityController(-2.0, k_p, k_i, k_d)),
        (1500.0, VelocityController(1.0, k_p, k_i, k_d)),
        (2000.0, VelocityController(0.0, k_p, k_i, k_d)),
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
    error = np.mean(np.abs(velocity - target_velocity))
    return -error


def tune():
    bounds = {"k_p": (0, 200), "k_i": (0, 200), "k_d": (0, 200)}
    optimizer = BayesianOptimization(
        f=objective,
        pbounds=bounds,
        verbose=2,
    )
    optimizer.maximize(n_iter=50)

    if optimizer.max is not None:
        print(optimizer.max)
        params = optimizer.max["params"]
        monitor, _ = simulate(**params)
        monitor.plot_state()


if __name__ == "__main__":
    tune()


# {'target': -0.4669325187496112, 'params': {'k_d': 124.25863289470911, 'k_i': 34.790141360779124, 'k_p': 10.874548503904872}}
