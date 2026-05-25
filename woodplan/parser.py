"""YAML parser for .wood project files."""

from __future__ import annotations
import yaml
from typing import Any, Dict
from .models import Project, Material, Element, Joint, JointPosition


def _parse_material(data: Dict[str, Any]) -> Material:
    return Material(
        id=str(data["id"]),
        type=str(data.get("type", "board")),
        species=str(data.get("species", "unknown")),
        width=float(data.get("width", 0)),
        thickness=float(data.get("thickness", 0)),
        length=float(data.get("length", 0)),
        cost_per_length=float(data.get("cost_per_length", 0)),
        unit=str(data.get("unit", "mm")),
    )


def _parse_element(data: Dict[str, Any]) -> Element:
    dims = data.get("dimensions", {})
    # Support both flat and nested dimensions
    length = float(dims.get("length", data.get("length", 0)))
    width = float(dims.get("width", data.get("width", 0)))
    thickness = float(dims.get("thickness", data.get("thickness", 0)))
    return Element(
        id=str(data["id"]),
        material_id=str(data["material"]),
        length=length,
        width=width,
        thickness=thickness,
        label=str(data.get("label", "")),
        quantity=int(data.get("quantity", 1)),
        notes=str(data.get("notes", "")),
    )


def _parse_joint(data: Dict[str, Any]) -> Joint:
    pos_data = data.get("position")
    position = None
    if pos_data:
        position = JointPosition(
            edge=str(pos_data.get("edge", "bottom")),
            offset=float(pos_data.get("offset", 0)),
        )
    return Joint(
        type=str(data.get("type", "butt")),
        from_element=str(data["from_element"]),
        to_element=str(data["to_element"]),
        description=str(data.get("description", "")),
        depth=float(data.get("depth", 0)),
        width=float(data.get("width", 0)),
        position=position,
        fastener=str(data.get("fastener", "")),
    )


def load(path: str) -> Project:
    """Load a .wood YAML project file and return a Project object."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    meta = raw.get("project", {})
    project = Project(
        name=str(meta.get("name", "Untitled Project")),
        description=str(meta.get("description", "")),
        unit=str(meta.get("unit", "mm")),
    )

    for m in raw.get("materials", []):
        project.materials.append(_parse_material(m))

    for e in raw.get("elements", []):
        project.elements.append(_parse_element(e))

    for j in raw.get("joints", []):
        project.joints.append(_parse_joint(j))

    return project


def loads(text: str) -> Project:
    """Load a project from a YAML string."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        tmp = fh.name
    try:
        return load(tmp)
    finally:
        os.unlink(tmp)
