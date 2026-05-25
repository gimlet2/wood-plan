"""Inventory / Bill-of-Materials generator."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List
from .models import Project
from .cutlist import CutListResult


@dataclass
class InventoryLine:
    material_id: str
    material_label: str
    boards_needed: int
    stock_length: float
    total_length_needed: float
    total_pieces: int
    estimated_cost: float
    unit: str


@dataclass
class InventoryReport:
    project_name: str
    unit: str
    lines: List[InventoryLine] = field(default_factory=list)

    @property
    def grand_total_cost(self) -> float:
        return sum(l.estimated_cost for l in self.lines)

    def as_text(self) -> str:
        lines = [
            f"Inventory Report — {self.project_name}",
            "=" * 60,
            f"{'Material':<28} {'Boards':>6} {'Stock Length':>14} {'Pieces':>7} {'Est. Cost':>10}",
            "-" * 60,
        ]
        for l in self.lines:
            lines.append(
                f"{l.material_label:<28} {l.boards_needed:>6} "
                f"{l.stock_length:>12.0f}{l.unit} {l.total_pieces:>7} "
                f"{l.estimated_cost:>9.2f}"
            )
        lines.append("-" * 60)
        lines.append(f"{'Grand Total':<50} {self.grand_total_cost:>9.2f}")
        return "\n".join(lines)

    def as_csv(self) -> str:
        rows = ["Material ID,Material Label,Boards Needed,Stock Length,Total Pieces,Estimated Cost,Unit"]
        for l in self.lines:
            rows.append(
                f"{l.material_id},{l.material_label},{l.boards_needed},"
                f"{l.stock_length},{l.total_pieces},{l.estimated_cost:.2f},{l.unit}"
            )
        return "\n".join(rows)


def generate(project: Project, cut_result: CutListResult) -> InventoryReport:
    """Generate an inventory report from a project and its cut list result."""
    report = InventoryReport(project_name=project.name, unit=project.unit)

    boards_by_mat = cut_result.boards_by_material()

    for mat_id, boards in boards_by_mat.items():
        material = project.get_material(mat_id)
        if material is None:
            continue

        total_pieces = sum(len(b.cuts) for b in boards)
        total_length = sum(c.element.length for b in boards for c in b.cuts)
        cost = len(boards) * material.cost_per_length

        report.lines.append(InventoryLine(
            material_id=mat_id,
            material_label=material.label,
            boards_needed=len(boards),
            stock_length=material.length,
            total_length_needed=total_length,
            total_pieces=total_pieces,
            estimated_cost=cost,
            unit=material.unit or project.unit,
        ))

    return report
