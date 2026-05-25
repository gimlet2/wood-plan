"""Tests for woodplan package."""
import os
import textwrap
import pytest

# Make sure the package is importable from the project root
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from woodplan import loads, load
from woodplan.models import Project, Element, Material, Joint
import woodplan.cutlist as cutlist
import woodplan.inventory as inventory
import woodplan.visualizer as visualizer


# ────────────────────────────────────────────────────────────
#  Fixtures
# ────────────────────────────────────────────────────────────

SIMPLE_YAML = textwrap.dedent("""\
    project:
      name: "Test Shelf"
      description: "Unit test project"
      unit: mm

    materials:
      - id: pine_1x8
        species: pine
        width: 184
        thickness: 19
        length: 2440
        cost_per_length: 10.00

    elements:
      - id: side
        material: pine_1x8
        dimensions:
          length: 900
          width: 184
          thickness: 19
        label: "Side Panel"
        quantity: 2

      - id: shelf
        material: pine_1x8
        dimensions:
          length: 600
          width: 184
          thickness: 19
        label: "Shelf"
        quantity: 3

    joints:
      - type: dado
        from_element: side
        to_element: shelf
        description: "Dado joint"
        depth: 6
        fastener: glue
""")


@pytest.fixture
def simple_project():
    return loads(SIMPLE_YAML)


# ────────────────────────────────────────────────────────────
#  Parser tests
# ────────────────────────────────────────────────────────────

class TestParser:
    def test_project_meta(self, simple_project):
        assert simple_project.name == "Test Shelf"
        assert simple_project.unit == "mm"

    def test_materials_loaded(self, simple_project):
        assert len(simple_project.materials) == 1
        mat = simple_project.materials[0]
        assert mat.id == "pine_1x8"
        assert mat.species == "pine"
        assert mat.width == 184
        assert mat.thickness == 19
        assert mat.length == 2440
        assert mat.cost_per_length == 10.00

    def test_elements_loaded(self, simple_project):
        assert len(simple_project.elements) == 2
        side = simple_project.get_element("side")
        assert side is not None
        assert side.length == 900
        assert side.quantity == 2

    def test_joints_loaded(self, simple_project):
        assert len(simple_project.joints) == 1
        j = simple_project.joints[0]
        assert j.type == "dado"
        assert j.from_element == "side"
        assert j.to_element == "shelf"
        assert j.depth == 6
        assert j.fastener == "glue"

    def test_all_pieces_expanded(self, simple_project):
        pieces = simple_project.all_pieces()
        # 2 sides + 3 shelves = 5
        assert len(pieces) == 5

    def test_load_from_file(self, tmp_path):
        f = tmp_path / "test.wood"
        f.write_text(SIMPLE_YAML, encoding="utf-8")
        project = load(str(f))
        assert project.name == "Test Shelf"


# ────────────────────────────────────────────────────────────
#  Cut list tests
# ────────────────────────────────────────────────────────────

class TestCutList:
    def test_all_pieces_placed(self, simple_project):
        result = cutlist.generate(simple_project)
        total_cuts = sum(len(b.cuts) for b in result.boards)
        assert total_cuts == len(simple_project.all_pieces())

    def test_no_piece_exceeds_board(self, simple_project):
        result = cutlist.generate(simple_project)
        for board in result.boards:
            for cut in board.cuts:
                assert cut.end <= board.material.length + 0.001

    def test_board_count_reasonable(self, simple_project):
        result = cutlist.generate(simple_project)
        # 5 pieces each ≤900mm, board is 2440mm → should fit in ≤3 boards
        assert result.total_boards() <= 3

    def test_board_utilization_positive(self, simple_project):
        result = cutlist.generate(simple_project)
        for board in result.boards:
            assert board.used_length > 0
            assert 0 < board.utilization <= 100

    def test_piece_too_long_raises(self):
        yaml = textwrap.dedent("""\
            project:
              name: Fail
              unit: mm
            materials:
              - id: short_board
                species: pine
                width: 100
                thickness: 19
                length: 500
            elements:
              - id: big_piece
                material: short_board
                dimensions:
                  length: 600
                  width: 100
                  thickness: 19
        """)
        project = loads(yaml)
        with pytest.raises(ValueError, match="longer than stock"):
            cutlist.generate(project)

    def test_kerf_respected(self):
        """With kerf=100 each piece should be offset by 100 from the previous end."""
        yaml = textwrap.dedent("""\
            project:
              name: Kerf
              unit: mm
            materials:
              - id: m
                species: pine
                width: 100
                thickness: 19
                length: 3000
            elements:
              - id: p
                material: m
                dimensions:
                  length: 300
                  width: 100
                  thickness: 19
                quantity: 3
        """)
        project = loads(yaml)
        result = cutlist.generate(project, kerf=100)
        board = result.boards[0]
        assert len(board.cuts) == 3
        # second cut starts at 300 + 100 = 400
        assert board.cuts[1].start == pytest.approx(400)
        assert board.cuts[2].start == pytest.approx(800)

    def test_unknown_material_raises(self):
        yaml = textwrap.dedent("""\
            project:
              name: Bad
              unit: mm
            materials: []
            elements:
              - id: p
                material: nonexistent
                dimensions:
                  length: 100
                  width: 50
                  thickness: 19
        """)
        project = loads(yaml)
        with pytest.raises(ValueError, match="Unknown material"):
            cutlist.generate(project)


# ────────────────────────────────────────────────────────────
#  Inventory tests
# ────────────────────────────────────────────────────────────

class TestInventory:
    def test_inventory_line_per_material(self, simple_project):
        cut_result = cutlist.generate(simple_project)
        report = inventory.generate(simple_project, cut_result)
        assert len(report.lines) == 1

    def test_boards_needed_matches_cutlist(self, simple_project):
        cut_result = cutlist.generate(simple_project)
        report = inventory.generate(simple_project, cut_result)
        assert report.lines[0].boards_needed == cut_result.total_boards()

    def test_cost_calculation(self, simple_project):
        cut_result = cutlist.generate(simple_project)
        report = inventory.generate(simple_project, cut_result)
        expected_cost = cut_result.total_boards() * 10.0
        assert report.grand_total_cost == pytest.approx(expected_cost)

    def test_as_csv_has_header(self, simple_project):
        cut_result = cutlist.generate(simple_project)
        report = inventory.generate(simple_project, cut_result)
        csv = report.as_csv()
        assert csv.startswith("Material ID,")

    def test_as_text_contains_project_name(self, simple_project):
        cut_result = cutlist.generate(simple_project)
        report = inventory.generate(simple_project, cut_result)
        text = report.as_text()
        assert "Test Shelf" in text


# ────────────────────────────────────────────────────────────
#  Visualizer tests
# ────────────────────────────────────────────────────────────

class TestVisualizer:
    def test_render_returns_html(self, simple_project):
        cut_result = cutlist.generate(simple_project)
        html = visualizer.render_html(simple_project, cut_result)
        assert html.startswith("<!DOCTYPE html>")
        assert "<title>" in html

    def test_html_contains_project_name(self, simple_project):
        cut_result = cutlist.generate(simple_project)
        html = visualizer.render_html(simple_project, cut_result)
        assert "Test Shelf" in html

    def test_html_contains_svg(self, simple_project):
        cut_result = cutlist.generate(simple_project)
        html = visualizer.render_html(simple_project, cut_result)
        assert "<svg" in html

    def test_html_contains_joint_table(self, simple_project):
        cut_result = cutlist.generate(simple_project)
        html = visualizer.render_html(simple_project, cut_result)
        assert "dato" in html.lower() or "dado" in html.lower()

    def test_save_html(self, simple_project, tmp_path):
        cut_result = cutlist.generate(simple_project)
        out = str(tmp_path / "test.html")
        visualizer.save_html(simple_project, cut_result, out)
        assert os.path.isfile(out)
        with open(out, encoding="utf-8") as fh:
            content = fh.read()
        assert "Test Shelf" in content


# ────────────────────────────────────────────────────────────
#  Example files smoke tests
# ────────────────────────────────────────────────────────────

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "examples")


@pytest.mark.parametrize("example_file", ["bookshelf.wood", "planter_box.wood"])
def test_example_files_parse_and_render(example_file, tmp_path):
    path = os.path.join(EXAMPLES_DIR, example_file)
    project = load(path)
    cut_result = cutlist.generate(project)
    report = inventory.generate(project, cut_result)
    html = visualizer.render_html(project, cut_result)

    assert project.name
    assert len(project.elements) > 0
    assert cut_result.total_boards() > 0
    assert len(report.lines) > 0
    assert "<!DOCTYPE html>" in html

    # save to tmp and verify file exists
    out = str(tmp_path / "out.html")
    visualizer.save_html(project, cut_result, out)
    assert os.path.getsize(out) > 500
