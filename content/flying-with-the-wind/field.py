from typing import Callable

import numpy as np
from interp3d.interp_3d import Interp3D
from vector import Vector3

type Field3 = Callable[[Vector3], Vector3]
"""
Represents an arbitrary field in 3D space.
"""


class UniformField:
    """
    A field function that always returns the given vector.
    """

    def __init__(self, vector: Vector3):
        """
        Initializes the field with the given vector.
        """
        self.vector = vector

    def __call__(self, _: Vector3) -> Vector3:
        """
        Computes the field at the given position.
        """
        return self.vector


class RandomField:
    """
    A random field function. The returned vector never exceeds the given magnitude in each
    dimension. The underlying field is interpolated between generated control points.
    """

    def __init__(
        self,
        magnitude: Vector3,
        dimensions: Vector3,
        num_dimension_points: Vector3,
        generator: np.random.Generator = np.random.default_rng(),
    ):
        """
        Initializes the field with the given parameters.
        """
        # Store parameters needed on every call.
        self.dimensions = dimensions

        # Make sure there is at least one point in each dimension.
        x_num = int(max(1, num_dimension_points.x))
        y_num = int(max(1, num_dimension_points.y))
        z_num = int(max(1, num_dimension_points.z))

        # Generate control points.
        control_points = (
            np.linspace(-dimensions.x / 2, dimensions.x / 2, x_num),
            np.linspace(-dimensions.y / 2, dimensions.y / 2, y_num),
            np.linspace(0, dimensions.z, z_num),
        )

        # Generate random control vectors.
        control_vectors = (
            generator.uniform(-magnitude.x, magnitude.x, size=(x_num, y_num, z_num)),
            generator.uniform(-magnitude.y, magnitude.y, size=(x_num, y_num, z_num)),
            generator.uniform(-magnitude.z, magnitude.z, size=(x_num, y_num, z_num)),
        )

        # Create linear interpolators for a regular grid.
        self.interpolators = (
            Interp3D(control_vectors[0], *control_points),
            Interp3D(control_vectors[1], *control_points),
            Interp3D(control_vectors[2], *control_points),
        )

    def __call__(self, position: Vector3) -> Vector3:
        """
        Computes the field at the given position.
        """
        # Ensure the position is within bounds.
        position = Vector3(
            min(max(position.x, -self.dimensions.y / 2), self.dimensions.y / 2),
            min(max(position.y, -self.dimensions.z / 2), self.dimensions.z / 2),
            min(max(position.z, 0), self.dimensions.z),
        )

        # Interpolate all components of the wind vector.
        return Vector3(*(self.interpolators[i](position) for i in range(3)))
