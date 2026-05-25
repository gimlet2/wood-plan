"""Isometric 3D preview generator for wood-plan projects.

Uses a heuristic layout engine (no explicit 3-D coordinates in .wood files) to
place pieces in world space, then renders an SVG image using a standard
isometric projection.  Works well for common shelf / cabinet / box structures.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

from .models import Element, Project

# ── Colour palette (warm wood tones) ─────────────────────────────────────────
_COLOURS = [
    "#C8A265", "#A67C52", "#D2691E", "#DEB887", "#F4A460",
    "#CD853F", "#B8860B", "#DAA520", "#8B4513", "#A0522D",
]

# ── Trig constants ────────────────────────────────────────────────────────────
_COS30 = math.cos(math.radians(30))   # ≈ 0.866
_SIN30 = 0.5


# ── Colour helpers ────────────────────────────────────────────────────────────

def _darken(hex_col: str, factor: float = 0.70) -> str:
    h = hex_col.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#{:02x}{:02x}{:02x}".format(int(r * factor), int(g * factor), int(b * factor))


def _lighten(hex_col: str, factor: float = 1.12) -> str:
    h = hex_col.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#{:02x}{:02x}{:02x}".format(
        min(255, int(r * factor)),
        min(255, int(g * factor)),
        min(255, int(b * factor)),
    )


# ── Utility helpers ───────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "\u2026"


# ── Isometric projection ──────────────────────────────────────────────────────

def _iso(
    x: float, y: float, z: float, scale: float, ox: float, oy: float
) -> Tuple[float, float]:
    """Map world (x right, y up, z depth) → screen (sx, sy).

    Camera looks from upper-front-right.
    """
    sx = (x - z) * _COS30 * scale + ox
    sy = (-y + (x + z) * _SIN30) * scale + oy
    return sx, sy


# ── Box SVG renderer ──────────────────────────────────────────────────────────

def _box_svg(
    px: float, py: float, pz: float,
    dx: float, dy: float, dz: float,
    base_col: str,
    scale: float, ox: float, oy: float,
    label: str = "",
) -> str:
    """Return SVG markup for one isometric box.

    Visible faces: top (lightest), front (base colour), right side (darkest).
    """
    def p(x: float, y: float, z: float) -> Tuple[float, float]:
        return _iso(x, y, z, scale, ox, oy)

    # 7 corners actually needed (back-bottom-left is never visible)
    FBL = p(px,      py,      pz)
    FBR = p(px + dx, py,      pz)
    FTR = p(px + dx, py + dy, pz)
    FTL = p(px,      py + dy, pz)
    BBR = p(px + dx, py,      pz + dz)
    BTR = p(px + dx, py + dy, pz + dz)
    BTL = p(px,      py + dy, pz + dz)

    def pts(*corners: Tuple[float, float]) -> str:
        return " ".join(f"{c[0]:.1f},{c[1]:.1f}" for c in corners)

    top_col   = _lighten(base_col)
    front_col = base_col
    right_col = _darken(base_col)
    sw = max(0.4, scale * 1.2)

    parts: List[str] = []
    # Top face:   FTL → FTR → BTR → BTL
    parts.append(
        f'<polygon points="{pts(FTL, FTR, BTR, BTL)}" fill="{top_col}" '
        f'stroke="#2c1810" stroke-width="{sw:.2f}"/>'
    )
    # Front face: FBL → FBR → FTR → FTL
    parts.append(
        f'<polygon points="{pts(FBL, FBR, FTR, FTL)}" fill="{front_col}" '
        f'stroke="#2c1810" stroke-width="{sw:.2f}"/>'
    )
    # Right face: FBR → BBR → BTR → FTR
    parts.append(
        f'<polygon points="{pts(FBR, BBR, BTR, FTR)}" fill="{right_col}" '
        f'stroke="#2c1810" stroke-width="{sw:.2f}"/>'
    )

    # Text label on the front face (skip if the face is too thin to show text)
    if label and dy * scale > 14:
        cx = (FBL[0] + FBR[0] + FTR[0] + FTL[0]) / 4
        cy = (FBL[1] + FBR[1] + FTR[1] + FTL[1]) / 4
        fs = max(7, min(11, int(dy * scale * 0.35)))
        parts.append(
            f'<text x="{cx:.1f}" y="{cy:.1f}" '
            f'text-anchor="middle" dominant-baseline="middle" '
            f'font-size="{fs}" fill="#fff" font-weight="600">'
            f"{_esc(label)}</text>"
        )

    return "".join(parts)


# ── Element expansion helper ──────────────────────────────────────────────────

def _expand(template: Element) -> List[Element]:
    """Expand a template element by its quantity into individual pieces."""
    result: List[Element] = []
    for i in range(template.quantity):
        sfx     = f"_{i + 1}" if template.quantity > 1 else ""
        lbl_sfx = f" #{i + 1}" if template.quantity > 1 else ""
        result.append(Element(
            id=f"{template.id}{sfx}",
            material_id=template.material_id,
            length=template.length,
            width=template.width,
            thickness=template.thickness,
            label=f"{template.display_label}{lbl_sfx}",
            quantity=1,
            notes=template.notes,
        ))
    return result


# ── Layout engine ─────────────────────────────────────────────────────────────

def _colour_map(project: Project) -> Dict[str, str]:
    return {mat.id: _COLOURS[i % len(_COLOURS)] for i, mat in enumerate(project.materials)}


def _infer_layout(project: Project) -> List[Dict]:
    """Infer 3-D placement of every piece from joint topology.

    Returns a list of dicts with keys:
        piece, x, y, z, dx, dy, dz, colour
    """
    elem_tpls: Dict[str, Element] = {e.id: e for e in project.elements}
    col_map = _colour_map(project)

    dado_joints = [j for j in project.joints if j.type == "dado"]
    butt_joints = [j for j in project.joints if j.type == "butt"]

    # Frame pieces: appear as from_element in dado joints (they contain the dado)
    frame_ids = set(j.from_element for j in dado_joints)
    # Shelf pieces: appear as to_element in dado joints (they slot into the dado)
    shelf_ids = set(j.to_element for j in dado_joints)

    # Among non-frame/shelf: elements that connect to both frame pieces via butt joints
    butt_to_frame: Dict[str, set] = {}
    for j in butt_joints:
        if j.from_element in frame_ids:
            butt_to_frame.setdefault(j.to_element, set()).add(j.from_element)
        if j.to_element in frame_ids:
            butt_to_frame.setdefault(j.from_element, set()).add(j.to_element)

    n_frame = max(1, len(frame_ids))
    spans_both = {
        eid for eid, frs in butt_to_frame.items() if len(frs) >= n_frame
    }

    frame_elems = [elem_tpls[fid] for fid in frame_ids if fid in elem_tpls]
    side_height = frame_elems[0].length    if frame_elems else 900.0
    side_depth  = frame_elems[0].width     if frame_elems else 184.0
    side_thick  = frame_elems[0].thickness if frame_elems else 19.0

    # Categorise spanning pieces: full-depth → panel, partial-depth → brace
    panel_ids: set = set()
    brace_ids: set = set()
    for eid in spans_both:
        if eid in elem_tpls:
            e = elem_tpls[eid]
            if e.width >= side_depth * 0.8:
                panel_ids.add(eid)
            else:
                brace_ids.add(eid)

    placed: List[Dict] = []

    # ── Case A: Shelf / cabinet structure (dado joints present) ──────────────
    if frame_ids:
        shelf_tpls = [elem_tpls[sid] for sid in shelf_ids if sid in elem_tpls]
        inner_width = float(shelf_tpls[0].length) if shelf_tpls else 600.0

        # Side panels — sorted by id for consistent left/right ordering
        frame_sorted = sorted(frame_elems, key=lambda e: e.id)
        frame_x = [0.0, inner_width + side_thick]

        for i, fe in enumerate(frame_sorted[:2]):
            col = col_map.get(fe.material_id, _COLOURS[0])
            for piece in _expand(fe):
                placed.append(dict(
                    piece=piece, colour=col,
                    x=frame_x[min(i, 1)], y=0.0, z=0.0,
                    dx=float(side_thick), dy=float(side_height), dz=float(side_depth),
                ))

        # Shelves — use dado offsets for known positions, fill remaining evenly
        dado_offsets = sorted({
            j.position.offset
            for j in dado_joints
            if j.position and j.position.offset > 0
        })

        for sid in shelf_ids:
            if sid not in elem_tpls:
                continue
            se = elem_tpls[sid]
            col = col_map.get(se.material_id, _COLOURS[1])
            y_positions = list(dado_offsets)
            while len(y_positions) < se.quantity:
                if y_positions:
                    last = y_positions[-1]
                    avail  = side_height - 50.0 - last - se.thickness
                    remain = se.quantity - len(y_positions)
                    step   = avail / max(1, remain + 1)
                    y_positions.append(last + se.thickness + step)
                else:
                    step = side_height / (se.quantity + 1)
                    y_positions = [step * (k + 1) for k in range(se.quantity)]

            for idx, sp in enumerate(_expand(se)):
                yp = float(y_positions[idx]) if idx < len(y_positions) else side_height / 2
                placed.append(dict(
                    piece=sp, colour=col,
                    x=float(side_thick), y=yp, z=0.0,
                    dx=float(inner_width), dy=float(se.thickness), dz=float(se.width),
                ))

        # Top / bottom panels
        tb_tpls = sorted(
            [elem_tpls[pid] for pid in panel_ids if pid in elem_tpls],
            key=lambda e: e.id,
        )
        if tb_tpls:
            panel_thick = float(tb_tpls[0].thickness)
            tb_y = [0.0, side_height - panel_thick]
            all_tb: List[Tuple[Element, Element]] = []
            for te in tb_tpls:
                for p in _expand(te):
                    all_tb.append((te, p))
            for k, (te, tp) in enumerate(all_tb[:2]):
                col = col_map.get(te.material_id, _COLOURS[0])
                placed.append(dict(
                    piece=tp, colour=col,
                    x=float(side_thick), y=tb_y[min(k, 1)], z=0.0,
                    dx=float(inner_width), dy=float(te.thickness), dz=float(te.width),
                ))

        # Back braces — distributed evenly in height, at the back of the unit
        all_brace: List[Tuple[str, Element, Element]] = []
        for bid in brace_ids:
            if bid in elem_tpls:
                be = elem_tpls[bid]
                col = col_map.get(be.material_id, _COLOURS[2])
                for bp in _expand(be):
                    all_brace.append((col, bp, be))
        bc = len(all_brace)
        for k, (col, bp, be) in enumerate(all_brace):
            yp = side_height * (k + 1) / (bc + 1) - be.width / 2
            zp = side_depth - be.thickness
            placed.append(dict(
                piece=bp, colour=col,
                x=float(side_thick), y=float(yp), z=float(zp),
                dx=float(inner_width), dy=float(be.width), dz=float(be.thickness),
            ))

    # ── Case B: Box / planter structure (no dado joints) ─────────────────────
    else:
        _box_layout(project, col_map, placed)

    # ── Fallback: place any still-unpositioned pieces in a grid ──────────────
    placed_ids = {item["piece"].id for item in placed}
    remaining = [p for p in project.all_pieces() if p.id not in placed_ids]
    if remaining:
        _fallback_grid(remaining, col_map, placed)

    return placed


def _box_layout(project: Project, col_map: Dict[str, str], placed: List[Dict]) -> None:
    """Heuristic layout for box / planter structures (no dado joints)."""
    sorted_tpls = sorted(project.elements, key=lambda e: e.length, reverse=True)
    if not sorted_tpls:
        return

    max_len     = float(sorted_tpls[0].length)
    box_height  = float(sorted_tpls[0].width)
    box_thick   = float(sorted_tpls[0].thickness)

    long_sides  = [e for e in sorted_tpls if abs(e.length - max_len) < 5]
    rest        = [e for e in sorted_tpls if e not in long_sides]
    end_panels  = [e for e in rest if e.width >= box_height * 0.8]
    bottom_pcs  = [e for e in rest if e not in end_panels]

    inner_depth = float(end_panels[0].length) if end_panels else 150.0

    # Front and back long-side panels
    for ls in long_sides:
        col = col_map.get(ls.material_id, _COLOURS[0])
        for j, p in enumerate(_expand(ls)):
            zp = (inner_depth + box_thick) if j > 0 else 0.0
            placed.append(dict(
                piece=p, colour=col,
                x=0.0, y=0.0, z=zp,
                dx=max_len, dy=box_height, dz=box_thick,
            ))

    # Left and right end panels
    for ep in end_panels:
        col = col_map.get(ep.material_id, _COLOURS[1])
        for j, p in enumerate(_expand(ep)):
            xp = (max_len - box_thick) if j > 0 else 0.0
            placed.append(dict(
                piece=p, colour=col,
                x=xp, y=0.0, z=box_thick,
                dx=box_thick, dy=box_height, dz=inner_depth,
            ))

    # Bottom slats — evenly distributed across the inner depth
    all_bottom: List[Tuple[str, Element]] = [
        (col_map.get(be.material_id, _COLOURS[2]), bp)
        for be in bottom_pcs
        for bp in _expand(be)
    ]
    n = len(all_bottom)
    if n:
        step = inner_depth / (n + 1)
        for k, (col, bp) in enumerate(all_bottom):
            zp = box_thick + step * (k + 1) - bp.width / 2
            placed.append(dict(
                piece=bp, colour=col,
                x=box_thick, y=0.0, z=float(zp),
                dx=float(bp.length), dy=float(bp.thickness), dz=float(bp.width),
            ))


def _fallback_grid(
    pieces: List[Element], col_map: Dict[str, str], placed: List[Dict]
) -> None:
    """Place any remaining pieces in a row below the main assembly."""
    x = 0.0
    for p in pieces:
        col = col_map.get(p.material_id, _COLOURS[0])
        placed.append(dict(
            piece=p, colour=col,
            x=x, y=-float(p.thickness) - 30.0, z=0.0,
            dx=float(p.length), dy=float(p.thickness), dz=float(p.width),
        ))
        x += float(p.length) + 20.0


# ── Main public function ──────────────────────────────────────────────────────

def render_3d_html(project: Project) -> str:
    """Render an isometric 3D preview of the project as an HTML ``<div>`` section."""
    placed = _infer_layout(project)
    if not placed:
        return ""

    # Determine scene bounding box (to centre and scale)
    xs = [item["x"] for item in placed] + [item["x"] + item["dx"] for item in placed]
    ys = [item["y"] for item in placed] + [item["y"] + item["dy"] for item in placed]
    zs = [item["z"] for item in placed] + [item["z"] + item["dz"] for item in placed]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)

    scene_w = max_x - min_x
    scene_h = max_y - min_y
    scene_d = max_z - min_z

    # Scale so the tallest dimension fits in ~350 px
    target_px = 350.0
    scale = target_px / max(scene_w, scene_h, scene_d, 1.0)

    # SVG viewport
    svg_w = int((scene_w + scene_d) * _COS30 * scale) + 80
    svg_h = int(scene_h * scale + (scene_w + scene_d) * _SIN30 * scale) + 60

    # Offset so the scene sits nicely in the viewport
    ox = int(scene_d * _COS30 * scale) + 30
    oy = svg_h - 20

    # Painter's algorithm: draw pieces furthest from camera first
    # (highest centroid x + z = furthest from the viewer in isometric space)
    placed_sorted = sorted(
        placed,
        key=lambda item: -(
            (item["x"] - min_x + item["dx"] / 2)
            + (item["z"] - min_z + item["dz"] / 2)
        ),
    )

    parts: List[str] = []
    for item in placed_sorted:
        lbl = _truncate(item["piece"].display_label, 12)
        parts.append(_box_svg(
            item["x"] - min_x,
            item["y"] - min_y,
            item["z"] - min_z,
            item["dx"], item["dy"], item["dz"],
            item["colour"],
            scale=scale, ox=ox, oy=oy,
            label=lbl,
        ))

    svg_inner = "\n".join(parts)

    return (
        '<div class="card"><h2>&#x1F50D; 3D Preview</h2>\n'
        '<p style="color:#888;font-size:.85em">Isometric view &mdash; '
        'heuristic assembly layout</p>\n'
        '<div style="overflow:auto;background:linear-gradient(135deg,#ede8e0,#ddd5c8);'
        'border-radius:8px;padding:20px;display:inline-block">'
        f'<svg width="{svg_w}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="0 0 {svg_w} {svg_h}">'
        f'\n{svg_inner}\n'
        '</svg></div></div>'
    )
