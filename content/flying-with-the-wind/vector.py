from typing import Self


class Vector3(tuple):
    """
    Represents an immutable 3D vector.
    """

    def __new__(cls, x, y, z):
        return super().__new__(cls, (x, y, z))
    
    def __add__(self, other):
        if not isinstance(other, Vector3):
            raise TypeError(f"unsupported operand type(s) for +: 'Vector3' and '{type(other)}'")
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)
    
    def __sub__(self, other):
        if not isinstance(other, Vector3):
            raise TypeError(f"unsupported operand type(s) for -: 'Vector3' and '{type(other)}'")
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)
    
    def __mul__(self, other):
        if not isinstance(other, (int, float)):
            raise TypeError(f"unsupported operand type(s) for *: 'Vector3' and '{type(other)}'")
        return Vector3(self.x * other, self.y * other, self.z * other)
    
    def __truediv__(self, other):
        if not isinstance(other, (int, float)):
            raise TypeError(f"unsupported operand type(s) for /: 'Vector3' and '{type(other)}'")
        return Vector3(self.x / other, self.y / other, self.z / other)
    
    def __neg__(self):
        return Vector3(-self.x, -self.y, -self.z)
    
    @property
    def x(self) -> float:
        return self[0]
    
    @property
    def y(self) -> float:
        return self[1]
    
    @property
    def z(self) -> float:
        return self[2]
    
