"""Tensor shape and frame-aware value metadata (no numerical arrays required)."""
from __future__ import annotations

from dataclasses import dataclass

from .errors import ShapeError


@dataclass(frozen=True, slots=True)
class TensorShape:
    """Tensor extents; an empty tuple represents a scalar."""

    extents: tuple[int, ...]

    def __post_init__(self) -> None:
        if any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in self.extents):
            raise ShapeError("Tensor extents must be positive integers.")

    @property
    def rank(self) -> int:
        return len(self.extents)

    @property
    def size(self) -> int:
        result = 1
        for extent in self.extents:
            result *= extent
        return result


@dataclass(frozen=True, slots=True)
class CoordinateFrame:
    frame_id: str
    dimension: int
    parent_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.frame_id, str) or not self.frame_id.strip():
            raise ShapeError("Coordinate frame ID cannot be empty.")
        if isinstance(self.dimension, bool) or self.dimension not in (1, 2, 3):
            raise ShapeError("Coordinate frame dimension must be 1, 2, or 3.")
        if self.parent_id is not None:
            if not isinstance(self.parent_id, str) or not self.parent_id.strip():
                raise ShapeError("Parent frame ID must be a non-empty string when supplied.")
            if self.parent_id == self.frame_id:
                raise ShapeError("A coordinate frame cannot be its own parent.")


@dataclass(frozen=True, slots=True)
class ValueShape:
    shape: TensorShape
    frame: CoordinateFrame | None = None

    def require_compatible(self, other: "ValueShape") -> None:
        if self.shape != other.shape:
            raise ShapeError(
                f"Shape mismatch: {self.shape.extents} != {other.shape.extents}."
            )
        if self.frame != other.frame:
            raise ShapeError("Coordinate-frame mismatch; an explicit transform is required.")


@dataclass(frozen=True, slots=True)
class FieldType:
    value_shape: ValueShape
    domain_id: str
    function_space: str

    def __post_init__(self) -> None:
        if not isinstance(self.domain_id, str) or not self.domain_id.strip():
            raise ShapeError("Field types require a non-empty domain identifier.")
        if not isinstance(self.function_space, str) or not self.function_space.strip():
            raise ShapeError("Field types require a non-empty function-space identifier.")
