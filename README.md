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
  - type: dado          # see "Joint types" table below
    from_element: side_panel
    to_element: shelf
    description: "Shelf dado"
    depth: 6            # mm
    position:
      edge: bottom      # bottom | top | left | right | front | back
      offset: 300       # mm from edge
    fastener: glue      # glue | screw | nail | brad_nail | dowel | bolt | pocket_screw | biscuit
```

### Joint types

| Type | Description |
|------|-------------|
| `dado` | Rectangular channel cut across the grain to seat a shelf or panel |
| `rabbet` | Notch along the edge or end of a board (one-sided dado) |
| `butt` | Two square-cut pieces meet face-to-face or end-to-face |
| `miter` | Both pieces cut at a matching angle (typically 45°) |
| `half_lap` | Half the thickness removed from each piece so they sit flush |
| `box_joint` | Interlocking rectangular fingers along the end of a board (finger joint) |
| `mortise_tenon` | A projecting tenon fits into a matching mortise hole |
| `bridle` | Open mortise-and-tenon; the tenon slides into a forked end |
| `tongue_groove` | A tongue (ridge) fits into a matching groove |
| `spline` | A thin strip of wood fits into slots in both faces |
| `dovetail` | Trapezoidal interlocking fingers; very strong and decorative |
| `pocket` | Angled hole driven with a pocket-screw jig |
| `biscuit` | Oval compressed-wood wafer glued into matching slots |
| `dowel` | Cylindrical wooden pins align and reinforce the joint |

See [`examples/bookshelf.wood`](examples/bookshelf.wood) and
[`examples/planter_box.wood`](examples/planter_box.wood) for complete examples.

---

## Editor support / autocompletion

A [JSON Schema](schema/wood-plan.schema.json) is provided for `.wood` files.

### VS Code

Install the [YAML extension](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml).
The included `.vscode/settings.json` automatically associates `*.wood` files
with the schema, so you get autocompletion and validation out of the box.

If you open the project from a different workspace you can add the association
manually in your **settings.json**:

```json
{
  "yaml.schemas": {
    "./schema/wood-plan.schema.json": "*.wood"
  }
}
```

### Other editors

Point your editor's YAML Language Server at the schema file
`schema/wood-plan.schema.json` and associate it with the glob `*.wood`.

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
