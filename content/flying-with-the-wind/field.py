from typing import Callable

import numpy as np
from numba import jit
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
        self.control_points = control_points

        # Generate random control vectors.
        control_vectors = (
            generator.uniform(-magnitude.x, magnitude.x, size=(x_num, y_num, z_num)),
            generator.uniform(-magnitude.y, magnitude.y, size=(x_num, y_num, z_num)),
            generator.uniform(-magnitude.z, magnitude.z, size=(x_num, y_num, z_num)),
        )
        self.control_vectors = np.array(control_vectors, dtype=np.float64)
        self.control_vectors = np.moveaxis(self.control_vectors, 0, -1)

    def __call__(self, position: Vector3) -> Vector3:
        """
        Computes the field at the given position.
        """
        # Ensure the position is within bounds.
        clamped_position = (
            min(max(position.x, -self.dimensions.y / 2), self.dimensions.y / 2),
            min(max(position.y, -self.dimensions.z / 2), self.dimensions.z / 2),
            min(max(position.z, 0), self.dimensions.z),
        )

        # Interpolate all components of the wind vector.
        return Vector3(
            *self.interpolate(
                self.control_points, self.control_vectors, clamped_position
            )
        )

    @staticmethod
    @nit(nopython=True, cache=True)
    def interpolate(points, values, xi):
        x_points, y_points, z_points = points
        xi_x, xi_y, xi_z = xi

        # Compute the deltas between consecutive grid points (assumed to be even spacing)
        dx = x_points[1] - x_points[0]
        dy = y_points[1] - y_points[0]
        dz = z_points[1] - z_points[0]

        # Find the indices based on deltas
        i_x = int((xi_x - x_points[0]) / dx)
        i_y = int((xi_y - y_points[0]) / dy)
        i_z = int((xi_z - z_points[0]) / dz)

        # Ensure the indices are within bounds (clamping to grid limits)
        i_x = max(0, min(i_x, len(x_points) - 2))
        i_y = max(0, min(i_y, len(y_points) - 2))
        i_z = max(0, min(i_z, len(z_points) - 2))

        # Get the surrounding grid points
        x0 = x_points[i_x]
        y0 = y_points[i_y]
        z0 = z_points[i_z]

        # Get the values at the 8 surrounding grid points
        v000 = values[i_x, i_y, i_z]
        v001 = values[i_x, i_y, i_z + 1]
        v010 = values[i_x, i_y + 1, i_z]
        v011 = values[i_x, i_y + 1, i_z + 1]
        v100 = values[i_x + 1, i_y, i_z]
        v101 = values[i_x + 1, i_y, i_z + 1]
        v110 = values[i_x + 1, i_y + 1, i_z]
        v111 = values[i_x + 1, i_y + 1, i_z + 1]

        # Compute the trilinear interpolation
        dx_rel = (xi_x - x0) / dx
        dy_rel = (xi_y - y0) / dy
        dz_rel = (xi_z - z0) / dz

        c00 = v000 + (v100 - v000) * dx_rel
        c01 = v001 + (v101 - v001) * dx_rel
        c10 = v010 + (v110 - v010) * dx_rel
        c11 = v011 + (v111 - v011) * dx_rel

        c0 = c00 + (c10 - c00) * dy_rel
        c1 = c01 + (c11 - c01) * dy_rel

        return c0 + (c1 - c0) * dz_rel
