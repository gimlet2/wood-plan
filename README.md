# 🪵 wood-plan

A text-based woodworking project planner.  Define your project in a simple YAML
markup file — materials, elements, joints — then let **wood-plan** generate:

* a **cut list** (optimised bin-packing of pieces onto stock boards)
* an **inventory / Bill-of-Materials** (how many boards to buy + cost estimate)
* an **HTML visualisation** with SVG cut diagrams and a joints table

---

## Quick start

```bash
pip install pyyaml          # only external dependency
python -m woodplan.cli examples/bookshelf.wood
```

This prints the cut list, inventory, and joints to the terminal and writes
`bookshelf.html`.

### CLI options

```
woodplan <project.wood> [options]

  -o / --output PATH    Write HTML report to PATH  (default: <project>.html)
  --csv PATH            Write inventory CSV to PATH
  --kerf FLOAT          Saw-blade kerf width in project units (default: 3)
  --no-html             Skip HTML generation
```

---

## Project file format (`.wood`)

Files use YAML with three top-level keys: `project`, `materials`, `elements`,
and `joints`.

```yaml
project:
  name: "My Bookshelf"
  description: "Optional description"
  unit: mm          # mm (default) or inch

materials:
  - id: pine_1x8
    species: pine
    width: 184        # mm
    thickness: 19     # mm
    length: 2440      # available stock length
    cost_per_length: 15.00

elements:
  - id: side_panel
    material: pine_1x8
    dimensions:
      length: 900
      width: 184
      thickness: 19
    label: "Side Panel"
    quantity: 2       # generates two identical pieces

joints:
  - type: dado          # dado | butt | mortise_tenon | dovetail | pocket | biscuit
    from_element: side_panel
    to_element: shelf
    description: "Shelf dado"
    depth: 6            # mm
    position:
      edge: bottom
      offset: 300       # mm from edge
    fastener: glue      # glue | screw | nail | dowel
```

See [`examples/bookshelf.wood`](examples/bookshelf.wood) and
[`examples/planter_box.wood`](examples/planter_box.wood) for complete examples.

---

## Python API

```python
import woodplan

project   = woodplan.load("examples/bookshelf.wood")
cut_result = woodplan.cutlist.generate(project, kerf=3)
report    = woodplan.inventory.generate(project, cut_result)

print(report.as_text())
woodplan.visualizer.save_html(project, cut_result, "output.html")
```

---

## Running tests

```bash
pip install pytest pyyaml
pytest
```

---

## Project structure

```
woodplan/
  models.py      – data classes (Project, Material, Element, Joint …)
  parser.py      – YAML → Project loader
  cutlist.py     – 1-D bin-packing cut-list optimiser
  inventory.py   – Bill-of-Materials / inventory report
  visualizer.py  – HTML + SVG report renderer
  cli.py         – `woodplan` command-line entry point
examples/
  bookshelf.wood
  planter_box.wood
tests/
  test_woodplan.py
```
