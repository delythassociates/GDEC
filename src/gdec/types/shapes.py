"""Tensor shape and frame-aware value metadata (no numerical arrays required)."""
from __future__ import annotations
from dataclasses import dataclass
from .errors import ShapeError

@dataclass(frozen=True, slots=True)
class TensorShape:
    extents: tuple[int, ...]
    def __post_init__(self) -> None:
        if any(not isinstance(n, int) or n <= 0 for n in self.extents):
            raise ShapeError("Tensor extents must be positive integers.")
    @property
    def rank(self) -> int:
        return len(self.extents)
    @property
    def size(self) -> int:
        result = 1
        for n in self.extents: result *= n
        return result

@dataclass(frozen=True, slots=True)
class CoordinateFrame:
    frame_id: str
    dimension: int
    parent_id: str | None = None
    def __post_init__(self) -> None:
        if not self.frame_id.strip(): raise ShapeError("Coordinate frame ID cannot be empty.")
        if self.dimension not in (1, 2, 3): raise ShapeError("Coordinate frame dimension must be 1, 2, or 3.")
        if self.parent_id == self.frame_id: raise ShapeError("A coordinate frame cannot be its own parent.")

@dataclass(frozen=True, slots=True)
class ValueShape:
    shape: TensorShape
    frame: CoordinateFrame | None = None
    def require_compatible(self, other: "ValueShape") -> None:
        if self.shape != other.shape: raise ShapeError(f"Shape mismatch: {self.shape.extents} != {other.shape.extents}.")
        if self.frame != other.frame: raise ShapeError("Coordinate-frame mismatch; an explicit transform is required.")

@dataclass(frozen=True, slots=True)
class FieldType:
    value_shape: ValueShape
    domain_id: str
    function_space: str
    def __post_init__(self) -> None:
        if not self.domain_id.strip() or not self.function_space.strip():
            raise ShapeError("Field types require non-empty domain and function-space identifiers.")
