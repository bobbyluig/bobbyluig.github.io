import numpy as np
from field import RandomField
from vector import Vector3


def wind_field():
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


if __name__ == "__main__":
    wind_field()
