"""Three.js interactive 3D preview generator for wood-plan projects.

The layout engine (_infer_layout) infers 3-D piece positions from the joint
topology in the .wood file.  render_3d_html() serialises those positions to
JSON and embeds them in a self-contained Three.js scene with OrbitControls so
the user can rotate, zoom, and inspect the assembled project in a browser.
"""

from __future__ import annotations

import json
from typing import Dict, List

from .models import Element, Project

# ── Colour palette (warm wood tones) ─────────────────────────────────────────
_COLOURS = [
    "#C8A265", "#A67C52", "#D2691E", "#DEB887", "#F4A460",
    "#CD853F", "#B8860B", "#DAA520", "#8B4513", "#A0522D",
]

# ── Three.js viewer HTML template ─────────────────────────────────────────────
# __PIECES__ is replaced at runtime with a compact JSON array.
_THREE_TEMPLATE = """\
<div class="card">
<h2>&#x1F50D; 3D Preview</h2>
<p style="color:#888;font-size:.85em">
  Drag to rotate &bull; Scroll to zoom &bull; Right-drag to pan &bull;
  Hover a piece for details
</p>
<div id="wood3d-view" style="width:100%;height:520px;border-radius:8px;overflow:hidden;"></div>
<div id="wood3d-tip" style="position:fixed;pointer-events:none;background:rgba(44,24,16,.88);
  color:#fff;padding:5px 10px;border-radius:4px;font-size:.82em;
  display:none;z-index:999;line-height:1.4;"></div>
<script type="module">
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.162.0/build/three.module.js';
import { OrbitControls } from 'https://cdn.jsdelivr.net/npm/three@0.162.0/examples/jsm/controls/OrbitControls.js';

(function () {
  const PIECES = __PIECES__;

  const container = document.getElementById('wood3d-view');
  const tooltip   = document.getElementById('wood3d-tip');
  if (!container) return;

  const H = 520;
  let W = container.clientWidth || 900;

  // ── Renderer ────────────────────────────────────────────────────────────────
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(W, H);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);

  // ── Scene & camera ──────────────────────────────────────────────────────────
  const scene  = new THREE.Scene();
  scene.background = new THREE.Color(0xf0ebe2);

  const camera = new THREE.PerspectiveCamera(45, W / H, 1, 500000);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping  = true;
  controls.dampingFactor  = 0.06;

  // ── Lighting ────────────────────────────────────────────────────────────────
  scene.add(new THREE.AmbientLight(0xfff5e6, 0.70));

  const sun = new THREE.DirectionalLight(0xffffff, 1.0);
  sun.position.set(1000, 2000, 800);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  scene.add(sun);

  const fill = new THREE.DirectionalLight(0xe8d5b0, 0.40);
  fill.position.set(-800, 400, -600);
  scene.add(fill);

  // ── Shadow-receiving floor ──────────────────────────────────────────────────
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(500000, 500000),
    new THREE.ShadowMaterial({ opacity: 0.15 })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -1;
  floor.receiveShadow = true;
  scene.add(floor);

  // ── Build piece meshes ──────────────────────────────────────────────────────
  const group  = new THREE.Group();
  const meshes = [];

  for (const p of PIECES) {
    const geom  = new THREE.BoxGeometry(p.dx, p.dy, p.dz);
    const color = parseInt(p.colour.replace('#', ''), 16);
    const mat   = new THREE.MeshLambertMaterial({ color });
    const mesh  = new THREE.Mesh(geom, mat);
    mesh.position.set(p.x + p.dx / 2, p.y + p.dy / 2, p.z + p.dz / 2);
    mesh.castShadow    = true;
    mesh.receiveShadow = true;
    mesh.userData.label = p.label;
    mesh.userData.dims  = (
      Math.round(p.dx) + '\u00d7' +
      Math.round(p.dy) + '\u00d7' +
      Math.round(p.dz) + ' mm'
    );
    group.add(mesh);
    meshes.push(mesh);

    // Crisp outline edges
    mesh.add(new THREE.LineSegments(
      new THREE.EdgesGeometry(geom, 5),
      new THREE.LineBasicMaterial({ color: 0x2c1810, transparent: true, opacity: 0.55 })
    ));
  }
  scene.add(group);

  // ── Fit camera to the assembled group ───────────────────────────────────────
  const bbox   = new THREE.Box3().setFromObject(group);
  const center = bbox.getCenter(new THREE.Vector3());
  const size   = bbox.getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z);
  const fovRad = camera.fov * Math.PI / 180;
  const dist   = (maxDim / 2) / Math.tan(fovRad / 2) * 1.9;
  camera.position.set(
    center.x + dist * 0.55,
    center.y + dist * 0.50,
    center.z + dist * 0.85
  );
  camera.lookAt(center);
  controls.target.copy(center);
  controls.minDistance = maxDim * 0.15;
  controls.maxDistance = maxDim * 10;
  controls.update();

  // Fit shadow camera to scene bounding box
  sun.shadow.camera.left   = -maxDim * 1.2;
  sun.shadow.camera.right  =  maxDim * 1.2;
  sun.shadow.camera.top    =  maxDim * 1.2;
  sun.shadow.camera.bottom = -maxDim * 1.2;
  sun.shadow.camera.near   = 10;
  sun.shadow.camera.far    = maxDim * 8;
  sun.shadow.camera.updateProjectionMatrix();

  // ── Hover tooltip via raycasting ─────────────────────────────────────────────
  const raycaster = new THREE.Raycaster();
  const mouse     = new THREE.Vector2();
  let hoveredMesh = null;

  renderer.domElement.addEventListener('mousemove', (e) => {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width)  * 2 - 1;
    mouse.y = -((e.clientY - rect.top)  / rect.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    const hits = raycaster.intersectObjects(meshes);
    if (hits.length > 0) {
      const m = hits[0].object;
      if (m !== hoveredMesh) {
        if (hoveredMesh) hoveredMesh.material.emissive.setHex(0x000000);
        hoveredMesh = m;
        hoveredMesh.material.emissive.setHex(0x331100);
      }
      if (tooltip) {
        tooltip.style.display = 'block';
        tooltip.style.left    = (e.clientX + 14) + 'px';
        tooltip.style.top     = (e.clientY - 36) + 'px';
        tooltip.innerHTML = '<strong>' + m.userData.label + '</strong><br>' + m.userData.dims;
      }
    } else {
      if (hoveredMesh) { hoveredMesh.material.emissive.setHex(0x000000); hoveredMesh = null; }
      if (tooltip) tooltip.style.display = 'none';
    }
  });

  renderer.domElement.addEventListener('mouseleave', () => {
    if (hoveredMesh) { hoveredMesh.material.emissive.setHex(0x000000); hoveredMesh = null; }
    if (tooltip) tooltip.style.display = 'none';
  });

  // ── Responsive resize ────────────────────────────────────────────────────────
  if (typeof ResizeObserver !== 'undefined') {
    new ResizeObserver(() => {
      W = container.clientWidth;
      renderer.setSize(W, H);
      camera.aspect = W / H;
      camera.updateProjectionMatrix();
    }).observe(container);
  }

  // ── Render loop ──────────────────────────────────────────────────────────────
  (function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  })();
})();
</script>
</div>"""


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
                    last   = y_positions[-1]
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
            all_tb = []
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
        all_brace = []
        for bid in brace_ids:
            if bid in elem_tpls:
                be  = elem_tpls[bid]
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

    # ── Fallback: place any still-unpositioned pieces in a row ────────────────
    placed_ids = {item["piece"].id for item in placed}
    remaining  = [p for p in project.all_pieces() if p.id not in placed_ids]
    if remaining:
        _fallback_grid(remaining, col_map, placed)

    return placed


def _box_layout(project: Project, col_map: Dict[str, str], placed: List[Dict]) -> None:
    """Heuristic layout for box / planter structures (no dado joints)."""
    sorted_tpls = sorted(project.elements, key=lambda e: e.length, reverse=True)
    if not sorted_tpls:
        return

    max_len    = float(sorted_tpls[0].length)
    box_height = float(sorted_tpls[0].width)
    box_thick  = float(sorted_tpls[0].thickness)

    long_sides = [e for e in sorted_tpls if abs(e.length - max_len) < 5]
    rest       = [e for e in sorted_tpls if e not in long_sides]
    end_panels = [e for e in rest if e.width >= box_height * 0.8]
    bottom_pcs = [e for e in rest if e not in end_panels]

    inner_depth = float(end_panels[0].length) if end_panels else 150.0

    for ls in long_sides:
        col = col_map.get(ls.material_id, _COLOURS[0])
        for j, p in enumerate(_expand(ls)):
            zp = (inner_depth + box_thick) if j > 0 else 0.0
            placed.append(dict(
                piece=p, colour=col,
                x=0.0, y=0.0, z=zp,
                dx=max_len, dy=box_height, dz=box_thick,
            ))

    for ep in end_panels:
        col = col_map.get(ep.material_id, _COLOURS[1])
        for j, p in enumerate(_expand(ep)):
            xp = (max_len - box_thick) if j > 0 else 0.0
            placed.append(dict(
                piece=p, colour=col,
                x=xp, y=0.0, z=box_thick,
                dx=box_thick, dy=box_height, dz=inner_depth,
            ))

    all_bottom = [
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
    """Render an interactive Three.js 3D preview of the project as an HTML card."""
    placed = _infer_layout(project)
    if not placed:
        return ""

    pieces_data = [
        {
            "label":  item["piece"].display_label,
            "x":      round(item["x"],  2),
            "y":      round(item["y"],  2),
            "z":      round(item["z"],  2),
            "dx":     round(item["dx"], 2),
            "dy":     round(item["dy"], 2),
            "dz":     round(item["dz"], 2),
            "colour": item["colour"],
        }
        for item in placed
    ]
    pieces_json = json.dumps(pieces_data, separators=(",", ":"))
    return _THREE_TEMPLATE.replace("__PIECES__", pieces_json)
