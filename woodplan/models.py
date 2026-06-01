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
    """A connection/join between two elements.

    Supported joint types
    ----------------------
    dado          – rectangular channel cut across the grain to seat a shelf/panel
    rabbet        – notch along the edge or end of a board (one-sided dado)
    butt          – two square-cut pieces meet face-to-face or end-to-face
    miter         – both pieces cut at a matching angle (typically 45°)
    half_lap      – half the thickness removed from each piece so they sit flush
    box_joint      – interlocking rectangular fingers along the end of a board
    mortise_tenon – a projecting tenon fits into a matching mortise hole
    bridle        – open mortise-and-tenon; the tenon slides into a forked end
    tongue_groove – a tongue (ridge) fits into a matching groove
    spline        – a thin strip of wood (or biscuit) fits into slots in both faces
    dovetail      – trapezoidal interlocking fingers; very strong and decorative
    pocket        – angled hole driven with a pocket-screw jig
    biscuit       – oval compressed-wood wafer glued into matching slots
    dowel         – cylindrical wooden pins align and reinforce the joint
    """
    type: str                       # see docstring for supported types
    from_element: str
    to_element: str
    description: str = ""
    depth: float = 0.0
    width: float = 0.0
    position: Optional[JointPosition] = None
    fastener: str = ""              # screw | nail | dowel | glue | brad_nail


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
