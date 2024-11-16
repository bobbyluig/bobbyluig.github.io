import multiprocessing
from functools import partial
from typing import List

import numpy as np
from balloon import Balloon
from controller import (
    GreedyPositionController,
    SearchPositionController,
    VerticalPositionController,
)
from field import RandomField
from monitor import Monitor
from simulation import run
from tqdm import tqdm
from vector import Vector3


def penalty(target: Vector3, monitor: Monitor) -> float:
    """
    Computes the penalty function. This is the closest distance the balloon ever got to the target
    position in the horizontal plane.
    """
    position_xy = np.array(monitor.position)
    position_xy[:, 2] = 0

    target_xy = np.array(target)
    target_xy[2] = 0

    distance = np.linalg.norm(position_xy - target_xy, axis=1)
    return np.min(distance)


def evaluate_one(controller_type: str, seed: int) -> float:
    """
    Evaluates the given controller with the given seed.
    """
    generator = np.random.default_rng(seed)

    magnitude = Vector3(10.0, 10.0, 0.0)
    dimensions = Vector3(4000.0, 4000.0, 2000.0)
    num_dimension_points = Vector3(20, 20, 10)
    wind_field = RandomField(
        magnitude, dimensions, num_dimension_points, generator=generator
    )

    theta = generator.uniform(0, 2 * np.pi)
    x = 2000.0 * np.cos(theta)
    y = 2000.0 * np.sin(theta)
    target = Vector3(x, y, 500.0)

    if controller_type == "Fixed":
        controller = VerticalPositionController(500)
    elif controller_type == "Greedy":
        controller = GreedyPositionController(target, dimensions, wind_field)
    elif controller_type == "Search":
        controller = SearchPositionController(target, dimensions, wind_field)
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


def evaluate(controller_type: str, num_simulations: int = 100) -> List[float]:
    """
    Evaluates the given controller with the given number of simulations. Returns the penalties from
    the simulations.
    """
    with multiprocessing.Pool() as pool:
        results = list(
            tqdm(
                pool.imap(
                    partial(evaluate_one, controller_type), range(num_simulations)
                ),
                total=num_simulations,
            )
        )
    return results


if __name__ == "__main__":
    for controller_type in ["Fixed", "Greedy", "Search"]:
        results = evaluate(controller_type)
        print(
            "controller_type={}, mean={}, median={}, standard_deviation={}".format(
                controller_type,
                np.mean(results),
                np.median(results), 
                np.std(results),
            )
        )
