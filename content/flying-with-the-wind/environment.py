import numpy as np
import numpy.typing as npt


class Environment:
    def __init__(self, dimensions: npt.ArrayLike):
        self._dimensions: npt.NDArray = np.array(dimensions, dtype=np.float64)
        self._control_points: npt.NDArray
        self._create_control_points()

    def _create_control_points(self):
        self._control_points = np.linspace(
           -np.concatenate((self._dimensions[:-1], [0])) / 2,
           np.concatenate((self._dimensions[:-1], [0])) / 2,
        )
        print(self._control_points)


env = Environment([100, 100])
