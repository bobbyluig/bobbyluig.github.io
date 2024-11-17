import numpy as np
from field import RandomField
from vector import Vector3
from simulation import run_reference_simulation
from tune import simulate_position


def field():
    generator = np.random.default_rng(1)
    magnitude = Vector3(5.0, 5.0, 1.0)
    dimensions = Vector3(2000.0, 2000.0, 2000.0)
    num_dimension_points = Vector3(20, 20, 20)
    wind_field = RandomField(
        magnitude, dimensions, num_dimension_points, generator=generator
    )

    points = np.array(
        np.meshgrid(
            np.linspace(0, 500, 50),
            np.linspace(0, 500, 50),
        )
    ).T.reshape(-1, 2)

    out = []
    for point in points:
        wind = wind_field(Vector3(point[0], point[1], 1000.0))
        out.append(
            "[{:.3g}, {:.3g}, {:.3g}, {:.3g}]".format(
                point[0], point[1], wind.x / 5, wind.y / 5
            )
        )
    print("const data = [" + ", ".join(out) + "];")


def reference():
    monitor = run_reference_simulation(generator=np.random.default_rng(1))
    monitor = monitor.interpolate(1000)

    out = []
    for point in monitor.position:
        out.append(
            "[{:.5g}, {:.5g}, {:.5g}]".format(
                round(point.x), round(point.y), round(point.z)
            )
        )
    print("const data = [" + ", ".join(out) + "];")
    print(monitor.get_square_bounds())


def tune():
    monitor, _ = simulate_position(0.009774907674593549, 0.0, 0.0)
    monitor = monitor.interpolate(6000 // 5)

    time = []
    for point in monitor.time:
        time.append("{:.5g}".format(round(point)))
    print("const data_time = [" + ", ".join(time) + "];")

    position = []
    for point in monitor.position:
        position.append("{:.5g}".format(round(point.z, 1)))
    print("const data_position = [" + ", ".join(position) + "];")

    velocity = []
    for point in monitor.velocity:
        velocity.append("{:.5g}".format(round(point.z, 1)))
    print("const data_velocity = [" + ", ".join(velocity) + "];")

    fuel = []
    for point in monitor.fuel:
        fuel.append("{:.5g}".format(round(point)))
    print("const data_fuel = [" + ", ".join(fuel) + "];")

    vent = []
    for point in monitor.vent:
        vent.append("{:.5g}".format(round(point)))
    print("const data_vent = [" + ", ".join(vent) + "];")


if __name__ == "__main__":
    # field()
    # reference()
    tune()
