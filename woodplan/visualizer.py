"""HTML/SVG visualizer for wood-plan projects."""

from __future__ import annotations
from typing import List, Tuple
from .models import Project, Joint
from .cutlist import CutListResult, StockBoard

# Colour palette for pieces
_PIECE_COLOURS = [
    "#8B4513", "#A0522D", "#CD853F", "#D2691E", "#DEB887",
    "#C8A265", "#B8860B", "#DAA520", "#F4A460", "#BC8A5F",
    "#E8C99A", "#C19A6B", "#A67C52", "#7B5B3A", "#5C4033",
]

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background:#f5f0e8; color:#2c1810; margin:0; padding:20px; }}
  h1 {{ color:#5c3317; border-bottom:3px solid #8B4513; padding-bottom:8px; }}
  h2 {{ color:#8B4513; margin-top:2em; }}
  h3 {{ color:#A0522D; }}
  .card {{ background:#fff9f0; border:1px solid #d4b896; border-radius:8px; padding:16px; margin:16px 0; box-shadow:2px 2px 6px rgba(0,0,0,.08); }}
  table {{ border-collapse:collapse; width:100%; font-size:.92em; }}
  th {{ background:#8B4513; color:#fff; padding:8px 12px; text-align:left; }}
  td {{ padding:6px 12px; border-bottom:1px solid #e8d5be; }}
  tr:last-child td {{ border-bottom:none; }}
  tr:hover td {{ background:#fdf3e3; }}
  .board-svg {{ display:block; margin:8px 0; }}
  .waste {{ fill:#e8e0d8; }}
  .piece-label {{ font-size:11px; fill:#2c1810; font-weight:600; pointer-events:none; }}
  .board-label {{ font-size:12px; fill:#5c3317; font-weight:700; }}
  .joint-badge {{ display:inline-block; background:#8B4513; color:#fff; border-radius:4px; padding:2px 8px; margin:2px; font-size:.8em; }}
  .summary-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; }}
  .stat {{ background:#fff; border:1px solid #d4b896; border-radius:6px; padding:12px; text-align:center; }}
  .stat .value {{ font-size:1.8em; font-weight:700; color:#8B4513; }}
  .stat .label {{ font-size:.85em; color:#888; }}
</style>
</head>
<body>
<h1>🪵 {title}</h1>
{description_html}
{summary_html}
{cutlist_html}
{joints_html}
{inventory_html}
</body>
</html>
"""


def _svg_board(board: StockBoard, colour_map: dict, scale: float = 0.25, height: int = 50) -> str:
    """Render a single stock board as a narrow SVG bar with pieces coloured."""
    mat = board.material
    total_px = mat.length * scale
    svg_width = max(int(total_px), 100)

    rects: List[str] = []
    # waste background
    rects.append(
        f'<rect x="0" y="0" width="{svg_width}" height="{height}" class="waste" '
        f'rx="4" ry="4"/>'
    )

    for cut in board.cuts:
        x = int(cut.start * scale)
        w = max(int(cut.element.length * scale), 2)
        colour = colour_map.get(cut.element.material_id, "#CD853F")
        # alternate shade per piece
        piece_idx = board.cuts.index(cut)
        if piece_idx % 2 == 1:
            colour = _darken(colour)

        label = _truncate(cut.element.display_label, max(1, w // 7))
        rects.append(
            f'<rect x="{x}" y="2" width="{w}" height="{height-4}" fill="{colour}" '
            f'rx="3" ry="3" opacity="0.9">'
            f'<title>{cut.element.display_label} ({cut.element.length:.0f}×{cut.element.width:.0f}×{cut.element.thickness:.0f})</title>'
            f'</rect>'
        )
        if w > 30:
            cx = x + w // 2
            cy = height // 2 + 4
            rects.append(
                f'<text x="{cx}" y="{cy}" text-anchor="middle" class="piece-label">{label}</text>'
            )

    # board label
    board_label = f"Board #{board.board_index}  {mat.species} {mat.width:.0f}×{mat.thickness:.0f}mm  len={mat.length:.0f}mm  waste={board.waste_length:.0f}mm ({100-board.utilization:.0f}%)"
    svg = (
        f'<svg class="board-svg" width="{svg_width}" height="{height+20}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<text x="0" y="14" class="board-label">{_esc(board_label)}</text>'
        f'<g transform="translate(0,18)">'
        + "".join(rects)
        + "</g></svg>"
    )
    return svg


def _darken(hex_colour: str) -> str:
    hex_colour = hex_colour.lstrip("#")
    r, g, b = int(hex_colour[0:2], 16), int(hex_colour[2:4], 16), int(hex_colour[4:6], 16)
    r, g, b = max(0, r - 30), max(0, g - 30), max(0, b - 30)
    return f"#{r:02x}{g:02x}{b:02x}"


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _truncate(s: str, max_chars: int) -> str:
    return s if len(s) <= max_chars else s[:max_chars - 1] + "…"


def _build_colour_map(project: Project) -> dict:
    colour_map = {}
    for i, mat in enumerate(project.materials):
        colour_map[mat.id] = _PIECE_COLOURS[i % len(_PIECE_COLOURS)]
    return colour_map


def _summary_html(project: Project, cut_result: CutListResult) -> str:
    total_pieces = sum(len(b.cuts) for b in cut_result.boards)
    total_boards = cut_result.total_boards()
    total_cost = cut_result.total_cost()
    total_joints = len(project.joints)

    stats = [
        (total_pieces, "Total Pieces"),
        (total_boards, "Boards Needed"),
        (total_joints, "Joints"),
        (f"${total_cost:.2f}" if total_cost else "—", "Estimated Cost"),
    ]
    items = "".join(
        f'<div class="stat"><div class="value">{v}</div><div class="label">{l}</div></div>'
        for v, l in stats
    )
    return f'<div class="card"><h2>Summary</h2><div class="summary-grid">{items}</div></div>'


def _cutlist_html(project: Project, cut_result: CutListResult, colour_map: dict) -> str:
    if not cut_result.boards:
        return ""

    parts = ['<div class="card"><h2>Cut List</h2>']

    boards_by_mat = cut_result.boards_by_material()
    for mat_id, boards in boards_by_mat.items():
        material = project.get_material(mat_id)
        mat_label = material.label if material else mat_id
        parts.append(f"<h3>{_esc(mat_label)}</h3>")

        for board in boards:
            parts.append(_svg_board(board, colour_map))

        # Table
        parts.append(
            '<table><tr>'
            '<th>Board</th><th>Piece</th>'
            '<th>Length</th><th>Width</th><th>Thickness</th>'
            '<th>Start</th><th>End</th>'
            '</tr>'
        )
        unit = project.unit
        for board in boards:
            for cut in board.cuts:
                parts.append(
                    f"<tr>"
                    f"<td>#{board.board_index}</td>"
                    f"<td>{_esc(cut.element.display_label)}</td>"
                    f"<td>{cut.element.length:.0f} {unit}</td>"
                    f"<td>{cut.element.width:.0f} {unit}</td>"
                    f"<td>{cut.element.thickness:.0f} {unit}</td>"
                    f"<td>{cut.start:.0f} {unit}</td>"
                    f"<td>{cut.end:.0f} {unit}</td>"
                    f"</tr>"
                )
        parts.append("</table>")

    parts.append("</div>")
    return "".join(parts)


def _joints_html(project: Project) -> str:
    if not project.joints:
        return ""

    joint_type_icons = {
        "dado": "🔲",
        "butt": "📐",
        "mortise_tenon": "🔩",
        "dovetail": "🔷",
        "pocket": "🔩",
        "biscuit": "🟤",
    }

    parts = ['<div class="card"><h2>Joints &amp; Connections</h2>']
    parts.append(
        '<table><tr>'
        '<th>Type</th><th>From</th><th>To</th>'
        '<th>Description</th><th>Depth</th><th>Fastener</th>'
        '</tr>'
    )
    for j in project.joints:
        icon = joint_type_icons.get(j.type, "🔗")
        from_el = project.get_element(j.from_element)
        to_el = project.get_element(j.to_element)
        from_label = from_el.display_label if from_el else j.from_element
        to_label = to_el.display_label if to_el else j.to_element
        depth_str = f"{j.depth:.0f} {project.unit}" if j.depth else "—"
        fastener_str = j.fastener if j.fastener else "—"
        parts.append(
            f"<tr>"
            f"<td>{icon} {_esc(j.type)}</td>"
            f"<td>{_esc(from_label)}</td>"
            f"<td>{_esc(to_label)}</td>"
            f"<td>{_esc(j.description)}</td>"
            f"<td>{depth_str}</td>"
            f"<td>{fastener_str}</td>"
            f"</tr>"
        )
    parts.append("</table></div>")
    return "".join(parts)


def _inventory_html(project: Project, cut_result: CutListResult) -> str:
    boards_by_mat = cut_result.boards_by_material()
    if not boards_by_mat:
        return ""

    parts = ['<div class="card"><h2>Inventory / Bill of Materials</h2>']
    parts.append(
        '<table><tr>'
        '<th>Material</th><th>Species</th><th>Size</th>'
        '<th>Boards Needed</th><th>Total Pieces</th><th>Est. Cost</th>'
        '</tr>'
    )
    grand_total = 0.0
    unit = project.unit
    for mat_id, boards in boards_by_mat.items():
        material = project.get_material(mat_id)
        if material is None:
            continue
        total_pieces = sum(len(b.cuts) for b in boards)
        cost = len(boards) * material.cost_per_length
        grand_total += cost
        size = f"{material.width:.0f}×{material.thickness:.0f}×{material.length:.0f} {unit}"
        parts.append(
            f"<tr>"
            f"<td>{_esc(material.id)}</td>"
            f"<td>{_esc(material.species)}</td>"
            f"<td>{_esc(size)}</td>"
            f"<td>{len(boards)}</td>"
            f"<td>{total_pieces}</td>"
            f"<td>{'$'+format(cost,'.2f') if cost else '—'}</td>"
            f"</tr>"
        )
    cost_str = f"${grand_total:.2f}" if grand_total else "—"
    parts.append(
        f'<tr style="font-weight:700;background:#fdf3e3">'
        f'<td colspan="5">Grand Total</td>'
        f'<td>{cost_str}</td>'
        f"</tr>"
    )
    parts.append("</table></div>")
    return "".join(parts)


def render_html(project: Project, cut_result: CutListResult) -> str:
    """Render the full project report as an HTML string."""
    colour_map = _build_colour_map(project)
    title = _esc(project.name)
    desc_html = (
        f'<p style="font-style:italic;color:#666">{_esc(project.description)}</p>'
        if project.description else ""
    )
    return _HTML_TEMPLATE.format(
        title=title,
        description_html=desc_html,
        summary_html=_summary_html(project, cut_result),
        cutlist_html=_cutlist_html(project, cut_result, colour_map),
        joints_html=_joints_html(project),
        inventory_html=_inventory_html(project, cut_result),
    )


def save_html(project: Project, cut_result: CutListResult, output_path: str) -> None:
    """Write the HTML report to *output_path*."""
    html = render_html(project, cut_result)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)
