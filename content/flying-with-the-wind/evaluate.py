import multiprocessing

import numpy as np
import os
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
from functools import partial


def penalty(target: Vector3, monitor: Monitor) -> float:
    position_xy = np.array(monitor.position)
    position_xy[:, 2] = 0

    target_xy = np.array(target)
    target_xy[2] = 0

    distance = np.linalg.norm(position_xy - target_xy, axis=1)
    return np.min(distance)


def evaluate_one(controller_type, seed):
    generator = np.random.default_rng(seed)

    magnitude = Vector3(10.0, 10.0, 0.0)
    dimensions = Vector3(4000.0, 4000.0, 2000.0)
    num_dimension_points = Vector3(20, 20, 10)

    theta = generator.uniform(0, 2 * np.pi)
    x = 2000.0 * np.cos(theta)
    y = 2000.0 * np.sin(theta)
    target = Vector3(x, y, 500.0)

    wind_field = make_random_field(
        magnitude, dimensions, num_dimension_points, generator=generator
    )
    if controller_type == "VerticalPositionController":
        controller = VerticalPositionController(500)
    elif controller_type == "SearchPositionController":
        controller = SearchPositionController(target, dimensions, wind_field)
    elif controller_type == "GreedyPositionController":
        controller = GreedyPositionController(target, dimensions, wind_field)
    else:
        raise ValueError(f"Unknown controller type {controller_type}")
    monitor = run(
        balloon=Balloon(wind_field),
        controller=controller,
        time_step=1.0,
        total_time=7200.0,
        show_progress=False,
    )

    return penalty(target, monitor)


def evaluate(controller_type, num_simulations: int = 200):
    with multiprocessing.Pool() as pool:
        results = list(
            tqdm(
                pool.imap(
                    partial(evaluate_one, controller_type), range(num_simulations)
                ),
                total=num_simulations,
            )
        )

    return float(np.mean(results)), float(np.median(results))


if __name__ == "__main__":
    print(evaluate("VerticalPositionController"))
    print(evaluate("GreedyPositionController"))
    print(evaluate("SearchPositionController"))

