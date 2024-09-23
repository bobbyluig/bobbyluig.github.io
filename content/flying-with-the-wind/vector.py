from typing import Self


class Vector3(tuple):
    """
    Represents an immutable 3D vector.
    """

    def __new__(cls, x, y, z):
        return super().__new__(cls, (x, y, z))

    def __add__(self, other):
        if isinstance(other, (int, float)):
            return Vector3(self.x + other, self.y + other, self.z + other)
        elif isinstance(other, Vector3):
            return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)
        else:
            raise TypeError(
                f"unsupported operand type(s) for +: 'Vector3' and '{type(other)}'"
            )

    def __sub__(self, other):
        if isinstance(other, (int, float)):
            return Vector3(self.x - other, self.y - other, self.z - other)
        elif isinstance(other, Vector3):
            return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)
        else:
            raise TypeError(
                f"unsupported operand type(s) for -: 'Vector3' and '{type(other)}'"
            )

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return Vector3(self.x * other, self.y * other, self.z * other)
        elif isinstance(other, Vector3):
            return Vector3(self.x * other.x, self.y * other.y, self.z * other.z)
        else:
            raise TypeError(
                f"unsupported operand type(s) for *: 'Vector3' and '{type(other)}'"
            )

    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            return Vector3(self.x / other, self.y / other, self.z / other)
        elif isinstance(other, Vector3):
            return Vector3(self.x / other.x, self.y / other.y, self.z / other.z)
        else:
            raise TypeError(
                f"unsupported operand type(s) for /: 'Vector3' and '{type(other)}'"
            )

    def __neg__(self):
        return Vector3(-self.x, -self.y, -self.z)
    
    def magnitude(self):
        return (self.x ** 2 + self.y ** 2 + self.z ** 2) ** 0.5
    
    def normalize(self):
        return self / self.magnitude()
    
    def dot(self, other):
        return self.x * other.x + self.y * other.y + self.z * other.z

    @property
    def x(self) -> float:
        return self[0]

    @property
    def y(self) -> float:
        return self[1]

    @property
    def z(self) -> float:
        return self[2]

