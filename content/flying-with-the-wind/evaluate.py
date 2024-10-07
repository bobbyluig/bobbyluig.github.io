import multiprocessing

import numpy as np
from balloon import Balloon
from controller import (
    GreedyPositionController,
    SearchPositionController,
    VerticalPositionController,
)
from field import make_random_field
from monitor import Monitor
from simulation import run
from tqdm import tqdm
from vector import Vector3


def penalty(target: Vector3, monitor: Monitor) -> float:
    position_xy = np.array(monitor.position)
    position_xy[:, 2] = 0

    target_xy = np.array(target)
    target_xy[2] = 0

    distance = np.linalg.norm(position_xy - target_xy, axis=1)
    return np.min(distance)


def evaluate_one(seed):
    generator = np.random.default_rng(seed)

    magnitude = Vector3(10.0, 10.0, 0.0)
    dimensions = Vector3(10000.0, 10000.0, 2000.0)
    num_dimension_points = Vector3(10, 10, 5)
    target = Vector3(1000.0, 1000.0, 500.0)

    wind_field = make_random_field(
        magnitude, dimensions, num_dimension_points, generator=generator
    )
    # controller = SearchPositionController(target, dimensions, wind_field)
    # controller = GreedyPositionController(target, dimensions, wind_field)
    controller = VerticalPositionController(500)
    monitor = run(
        balloon=Balloon(wind_field),
        controller=controller,
        time_step=5.0,
        total_time=7200.0,
        show_progress=False,
    )

    return penalty(target, monitor)


def evaluate(num_simulations: int = 200) -> float:
    with multiprocessing.Pool() as pool:
        results = list(
            tqdm(pool.imap(evaluate_one, range(num_simulations)), total=num_simulations)
        )

    return float(np.mean(results))


if __name__ == "__main__":
    # Greedy: 749.9118591409356
    # Search Time: 832.7060207959227
    print(evaluate())
