"""Cut list optimizer: pack pieces onto available stock boards (1-D bin packing)."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from .models import Element, Material, Project

# Kerf (saw blade width) default in project units
DEFAULT_KERF_MM = 3.0


@dataclass
class Cut:
    """A single cut taken from a stock board."""
    element: Element
    start: float        # distance from the start of the board
    end: float          # start + piece_length


@dataclass
class StockBoard:
    """A physical stock board with cuts assigned to it."""
    material: Material
    board_index: int
    cuts: List[Cut] = field(default_factory=list)

    @property
    def used_length(self) -> float:
        if not self.cuts:
            return 0.0
        return self.cuts[-1].end

    @property
    def waste_length(self) -> float:
        return self.material.length - self.used_length

    @property
    def utilization(self) -> float:
        if self.material.length == 0:
            return 0.0
        return self.used_length / self.material.length * 100

    def fits(self, piece_length: float, kerf: float) -> bool:
        gap = self.waste_length
        if self.cuts:
            gap -= kerf       # account for kerf before new cut
        return gap >= piece_length

    def add_cut(self, element: Element, kerf: float) -> Cut:
        if self.cuts:
            start = self.cuts[-1].end + kerf
        else:
            start = 0.0
        cut = Cut(element=element, start=start, end=start + element.length)
        self.cuts.append(cut)
        return cut


@dataclass
class CutListResult:
    """The result of a cut list optimization run."""
    boards: List[StockBoard] = field(default_factory=list)
    kerf: float = DEFAULT_KERF_MM

    # ---- summary helpers -----------------------------------------------
    def boards_by_material(self) -> Dict[str, List[StockBoard]]:
        result: Dict[str, List[StockBoard]] = {}
        for b in self.boards:
            result.setdefault(b.material.id, []).append(b)
        return result

    def total_boards(self) -> int:
        return len(self.boards)

    def total_cost(self) -> float:
        return sum(b.material.cost_per_length for b in self.boards)

    def summary_rows(self) -> List[Tuple]:
        """Returns rows suitable for tabular display."""
        rows = []
        for b in self.boards:
            for c in b.cuts:
                rows.append((
                    b.material.id,
                    b.board_index,
                    c.element.display_label,
                    c.element.length,
                    c.element.width,
                    c.element.thickness,
                    round(c.start, 1),
                    round(c.end, 1),
                ))
        return rows


def generate(project: Project, kerf: float = DEFAULT_KERF_MM) -> CutListResult:
    """
    Generate a cut list for *project* using a First-Fit-Decreasing bin-packing
    strategy along the length dimension.
    """
    result = CutListResult(kerf=kerf)

    # Group pieces by material
    by_material: Dict[str, List[Element]] = {}
    for piece in project.all_pieces():
        by_material.setdefault(piece.material_id, []).append(piece)

    for mat_id, pieces in by_material.items():
        material = project.get_material(mat_id)
        if material is None:
            raise ValueError(f"Unknown material id '{mat_id}' referenced in elements.")

        # Sort pieces largest-first for better bin packing
        sorted_pieces = sorted(pieces, key=lambda p: p.length, reverse=True)

        open_boards: List[StockBoard] = []
        board_counter = 1

        for piece in sorted_pieces:
            if piece.length > material.length:
                raise ValueError(
                    f"Piece '{piece.display_label}' (length={piece.length}) is longer "
                    f"than stock board length {material.length} for material '{mat_id}'."
                )

            # Find the first board that fits
            placed = False
            for board in open_boards:
                if board.fits(piece.length, kerf):
                    board.add_cut(piece, kerf)
                    placed = True
                    break

            if not placed:
                new_board = StockBoard(material=material, board_index=board_counter)
                board_counter += 1
                new_board.add_cut(piece, kerf)
                open_boards.append(new_board)
                result.boards.append(new_board)

    return result
