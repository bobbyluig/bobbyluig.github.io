from balloon import Balloon
from controller import (
    Controller,
    ControllerOutput,
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
    num_steps = int(round((total_time - start_time) / time_step) + 1)

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
        )
    )

    controller = SequenceController(
        [
            (1000.0 * time_step, ControllerOutput(fuel=20.0, vent=0.0)),
            (3000.0 * time_step, ControllerOutput(fuel=25.0, vent=0.0)),
            (5000.0 * time_step, ControllerOutput(fuel=30.0, vent=0.0)),
            (7000.0 * time_step, ControllerOutput(fuel=30.0, vent=5.0)),
            (9000.0 * time_step, ControllerOutput(fuel=30.0, vent=0.0)),
            (11000.0 * time_step, ControllerOutput(fuel=22.0, vent=0.0)),
            (13000.0 * time_step, ControllerOutput(fuel=21.0, vent=0.0)),
            (15000.0 * time_step, ControllerOutput(fuel=20.0, vent=0.0)),
            (17000.0 * time_step, ControllerOutput(fuel=0.0, vent=5.0)),
        ]
    )

    return run(
        balloon=balloon,
        controller=controller,
        time_step=time_step,
        total_time=tf * tr,
    )


def run_test_simulation() -> Monitor:
    """
    Runs a test simulation.
    """
    return run(
        balloon=Balloon(),
        controller=SequenceController(
            [
                (0.0, ControllerOutput(fuel=100.0, vent=0.0)),
                (100.0, ControllerOutput(fuel=25.0, vent=0.0)),
            ]
        ),
        time_step=1.0,
        total_time=5000.0,
    )


if __name__ == "__main__":
    monitor = run_reference_simulation()
    monitor.animate_trajectory()
