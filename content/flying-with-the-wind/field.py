from typing import Callable, Tuple, cast

import numpy as np
from scipy.spatial import KDTree
from vector import Vector3

type Field3 = Callable[[Vector3], Vector3]
"""
Represents an arbitrary field in 3D space.
"""


def make_uniform_field(vector: Vector3) -> Field3:
    """
    Returns a uniform field function that always returns the same vector.   
    """
    return lambda _: vector


def make_random_field(
    min_magnitude: Vector3,
    max_magnitude: Vector3,
    dimensions: Vector3,
    points_per_dimension: int = 10,
    num_interpolation_points: int = 9,
) -> Field3:
    """
    Returns a random field function. The returned vector never exceeds the given bounds in each
    dimension. The underlying field is interpolated between generated control points.
    """

    # Generate control points.
    control_points = np.array(
        np.meshgrid(*[np.linspace(0, dim, points_per_dimension) for dim in dimensions])
    ).T.reshape(-1, 3)

    # Generate random control vectors.
    control_vectors = np.random.uniform(
        min_magnitude, max_magnitude, size=(len(control_points), 3)
    )

    # Create a KDTree.
    tree = KDTree(control_points)

    # Create a function that linearly interpolates between the control points.
    def interpolate(position: Vector3) -> Vector3:
        # Ensure the position is within bounds.
        position = cast(
            Vector3,
            tuple(min(max(position[i], 0), dimensions[i]) for i in range(3)),
        )

        # Find the nearest control points.
        distances, indices = tree.query(position, k=num_interpolation_points)

        # If the distance to the nearest point is zero, just return that point.
        if np.isclose(distances[0], 0):
            return tuple(control_vectors[indices[0]])

        # Calculate the weights of the interpolation.
        weights = distances
        weights = 1 / weights
        weights_sum = np.sum(weights)
        weights /= weights_sum

        # Interpolate.
        return tuple(np.dot(weights, control_vectors[indices, i]) for i in range(3))

    return interpolate

