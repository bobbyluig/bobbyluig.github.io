from balloon import Balloon
from controller import (
    Controller,
    apply_controller_output,
    get_controller_input,
    make_pid_controller,
)
from monitor import Monitor


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


if __name__ == "__main__":
    monitor = run(
        Balloon(),
        make_pid_controller(2000.0),
        1,
        10000.0,
    )
    monitor.plot()
