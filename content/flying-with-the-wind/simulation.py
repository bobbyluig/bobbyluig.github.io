import math

import numpy as np
from balloon import Balloon
from controller import (
    Controller,
    ControllerOutput,
    FixedController,
    PositionController,
    SequenceController,
    apply_controller_output,
    get_controller_input,
)
from field import make_random_field
from monitor import Monitor
from vector import Vector3


def run(
    balloon: Balloon,
    controller: Controller,
    time_step: float,
    total_time: float,
) -> Monitor:
    """
    Runs the balloon simulation. Returns a monitor containing the state of the balloon at each step
    of the simulation.
    """
    monitor = Monitor()

    start_time = balloon.get_time()
    num_steps = int(math.ceil((total_time - start_time) / time_step))

    for _ in range(num_steps):
        apply_controller_output(balloon, controller(get_controller_input(balloon)))
        balloon.step(time_step)
        monitor.update(balloon)

    return monitor


def run_reference_simulation() -> Monitor:
    """
    Runs the reference simulation in a random field.
    """
    tr = 10.10
    tf = 5000
    dt = 0.25
    time_step = dt * tr

    balloon = Balloon(
        make_random_field(
            Vector3(5.0, 5.0, 0.0),
            Vector3(10000.0, 10000.0, 10000.0),
            Vector3(10, 10, 10),
        )
    )

    controller = SequenceController(
        (1000.0 * time_step, FixedController(ControllerOutput(fuel=20.0, vent=0.0))),
        (3000.0 * time_step, FixedController(ControllerOutput(fuel=25.0, vent=0.0))),
        (5000.0 * time_step, FixedController(ControllerOutput(fuel=30.0, vent=0.0))),
        (7000.0 * time_step, FixedController(ControllerOutput(fuel=30.0, vent=5.0))),
        (9000.0 * time_step, FixedController(ControllerOutput(fuel=30.0, vent=0.0))),
        (11000.0 * time_step, FixedController(ControllerOutput(fuel=22.0, vent=0.0))),
        (13000.0 * time_step, FixedController(ControllerOutput(fuel=21.0, vent=0.0))),
        (15000.0 * time_step, FixedController(ControllerOutput(fuel=20.0, vent=0.0))),
        (17000.0 * time_step, FixedController(ControllerOutput(fuel=0.0, vent=5.0))),
    )

    return run(
        balloon=balloon,
        controller=controller,
        time_step=time_step,
        total_time=tf * tr,
    )


def run_max_height_simulation() -> Monitor:
    """
    Runs a simulation where the balloon reaches its maximum possible height.
    """
    return run(
        balloon=Balloon(),
        controller=SequenceController(
            (0.0, FixedController(ControllerOutput(fuel=100.0, vent=0.0))),
            (4000.0, FixedController(ControllerOutput(fuel=25.0, vent=0.0))),
        ),
        time_step=1.0,
        total_time=5000.0,
    )


def run_position_simulation() -> Monitor:
    """
    Runs a simulation with a fixed target position.
    """
    np.random.seed(1)

    magnitude = Vector3(5.0, 5.0, 0.0)
    dimensions = Vector3(10000.0, 10000.0, 10000.0)
    num_dimension_points = Vector3(10, 10, 10)
    wind_field = make_random_field(magnitude, dimensions, num_dimension_points)

    target = Vector3(2000.0, 2000.0, 2000.0)
    controller = PositionController(target, dimensions, wind_field)

    return run(
        balloon=Balloon(wind_field),
        controller=controller,
        time_step=1.0,
        total_time=10000.0,
    )


if __name__ == "__main__":
    monitor = run_position_simulation()
    monitor.animate_trajectory()
