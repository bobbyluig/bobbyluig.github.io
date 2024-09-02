from balloon import Balloon
from controller import (
    Controller,
    ControllerOutput,
    apply_controller_output,
    get_controller_input,
    SequenceController,
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
        balloon=Balloon(),
        controller=SequenceController([
            (0.0, ControllerOutput(fuel=100.0, vent=0.0)),
            (100.0, ControllerOutput(fuel=25.0, vent=0.0)),
        ]),
        time_step=1.0,
        total_time=5000.0,
    )

    monitor.plot_state()
