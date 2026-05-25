"""Core data models for wood-plan."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Dimensions:
    """Dimensions of a wood piece in the project unit (mm by default)."""
    length: float
    width: float
    thickness: float

    def volume(self) -> float:
        return self.length * self.width * self.thickness


@dataclass
class Material:
    """A stock material (e.g. a pine board available in a specific size)."""
    id: str
    type: str = "board"
    species: str = "unknown"
    width: float = 0.0
    thickness: float = 0.0
    length: float = 0.0         # available stock length
    cost_per_length: float = 0.0
    unit: str = "mm"

    @property
    def label(self) -> str:
        return f"{self.species} {self.width}x{self.thickness}x{self.length}"


@dataclass
class Element:
    """A named piece that will be cut from stock material."""
    id: str
    material_id: str
    length: float
    width: float
    thickness: float
    label: str = ""
    quantity: int = 1
    notes: str = ""

    @property
    def display_label(self) -> str:
        return self.label or self.id

    def unit_volume(self) -> float:
        return self.length * self.width * self.thickness


@dataclass
class JointPosition:
    """Describes where a joint sits on an element."""
    edge: str = "bottom"     # bottom | top | left | right | front | back
    offset: float = 0.0


@dataclass
class Joint:
    """A connection/join between two elements."""
    type: str                       # dado | butt | mortise_tenon | dovetail | pocket | biscuit
    from_element: str
    to_element: str
    description: str = ""
    depth: float = 0.0
    width: float = 0.0
    position: Optional[JointPosition] = None
    fastener: str = ""              # screw | nail | dowel | glue


@dataclass
class Project:
    """Top-level project container."""
    name: str
    description: str = ""
    unit: str = "mm"
    materials: List[Material] = field(default_factory=list)
    elements: List[Element] = field(default_factory=list)
    joints: List[Joint] = field(default_factory=list)

    def get_material(self, material_id: str) -> Optional[Material]:
        for m in self.materials:
            if m.id == material_id:
                return m
        return None

    def get_element(self, element_id: str) -> Optional[Element]:
        for e in self.elements:
            if e.id == element_id:
                return e
        return None

    def all_pieces(self) -> List[Element]:
        """Expand elements by quantity into individual pieces."""
        pieces: List[Element] = []
        for e in self.elements:
            for i in range(e.quantity):
                piece = Element(
                    id=f"{e.id}_{i+1}" if e.quantity > 1 else e.id,
                    material_id=e.material_id,
                    length=e.length,
                    width=e.width,
                    thickness=e.thickness,
                    label=f"{e.display_label} #{i+1}" if e.quantity > 1 else e.display_label,
                    quantity=1,
                    notes=e.notes,
                )
                pieces.append(piece)
        return pieces
