from typing import Callable, Tuple

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
        # Make sure there are at two points in each dimension.
        x_num = int(max(2, num_dimension_points.x))
        y_num = int(max(2, num_dimension_points.y))
        z_num = int(max(2, num_dimension_points.z))

        # Generate control points.
        control_points = (
            np.linspace(-dimensions.x / 2, dimensions.x / 2, x_num),
            np.linspace(-dimensions.y / 2, dimensions.y / 2, y_num),
            np.linspace(0, dimensions.z, z_num),
        )

        # Generate random control vectors.
        control_vectors = np.array(
            [
                generator.uniform(-magnitude.x, magnitude.x, (x_num, y_num, z_num)),
                generator.uniform(-magnitude.y, magnitude.y, (x_num, y_num, z_num)),
                generator.uniform(-magnitude.z, magnitude.z, (x_num, y_num, z_num)),
            ],
            dtype=np.float64,
        )
        control_vectors = np.moveaxis(control_vectors, 0, -1)

        # Store the compiled interpolation function.
        self.interpolate = self.make_interpolate_function(
            dimensions, control_points, control_vectors
        )

    @staticmethod
    def make_interpolate_function(
        dimensions: Vector3,
        control_points: Tuple[np.ndarray, np.ndarray, np.ndarray],
        control_vectors: np.ndarray,
    ):
        """
        A helper function to create a compiled interpolation function.
        """
        # Capture constants in closure.
        dim_x, dim_y, dim_z = dimensions
        points_x, points_y, points_z = control_points
        values = control_vectors

        # Define the function to be compiled.
        def interpolate(xi_x: float, xi_y: float, xi_z: float) -> np.ndarray:
            # Ensure the input is within bounds.
            xi_x = min(max(xi_x, -dim_x / 2), dim_x / 2)
            xi_y = min(max(xi_y, -dim_y / 2), dim_y / 2)
            xi_z = min(max(xi_z, 0), dim_z)

            # Compute the deltas between consecutive grid points.
            delta_x = points_x[1] - points_x[0]
            delta_y = points_y[1] - points_y[0]
            delta_z = points_z[1] - points_z[0]

            # Find the indices based on deltas.
            i_x = int((xi_x - points_x[0]) / delta_x)
            i_y = int((xi_y - points_y[0]) / delta_y)
            i_z = int((xi_z - points_z[0]) / delta_z)

            # Ensure the indices are within bounds.
            i_x = max(0, min(i_x, points_x.shape[0] - 2))
            i_y = max(0, min(i_y, points_y.shape[0] - 2))
            i_z = max(0, min(i_z, points_z.shape[0] - 2))

            # Get the values at the 8 surrounding grid points.
            v_000 = values[i_x, i_y, i_z]
            v_001 = values[i_x, i_y, i_z + 1]
            v_010 = values[i_x, i_y + 1, i_z]
            v_011 = values[i_x, i_y + 1, i_z + 1]
            v_100 = values[i_x + 1, i_y, i_z]
            v_101 = values[i_x + 1, i_y, i_z + 1]
            v_110 = values[i_x + 1, i_y + 1, i_z]
            v_111 = values[i_x + 1, i_y + 1, i_z + 1]

            # Compute the trilinear interpolation.
            relative_x = (xi_x - points_x[i_x]) / delta_x
            relative_y = (xi_y - points_y[i_y]) / delta_y
            relative_z = (xi_z - points_z[i_z]) / delta_z
            c_00 = v_000 + (v_100 - v_000) * relative_x
            c_01 = v_001 + (v_101 - v_001) * relative_x
            c_10 = v_010 + (v_110 - v_010) * relative_x
            c_11 = v_011 + (v_111 - v_011) * relative_x
            c_0 = c_00 + (c_10 - c_00) * relative_y
            c_1 = c_01 + (c_11 - c_01) * relative_y
            return c_0 + (c_1 - c_0) * relative_z

        # Return the compiled function.
        return jit(interpolate)

    def __call__(self, position: Vector3) -> Vector3:
        """
        Computes the field at the given position.
        """
        return Vector3(*self.interpolate(*position))
