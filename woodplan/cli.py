"""Command-line interface for wood-plan."""

from __future__ import annotations
import argparse
import sys
import os
from . import parser as project_parser
from . import cutlist as cutlist_gen
from . import inventory as inventory_gen
from . import visualizer


def _print_cutlist(project, cut_result) -> None:
    unit = project.unit
    print(f"\nCut List — {project.name}")
    print("=" * 70)
    by_mat = cut_result.boards_by_material()
    for mat_id, boards in by_mat.items():
        material = project.get_material(mat_id)
        mat_label = material.label if material else mat_id
        print(f"\n  Material: {mat_label}")
        print(f"  {'Board':<8} {'Piece':<30} {'Length':>8} {'Width':>7} {'Thick':>7} {'Start':>8} {'End':>8}")
        print(f"  {'-'*8} {'-'*30} {'-'*8} {'-'*7} {'-'*7} {'-'*8} {'-'*8}")
        for board in boards:
            for cut in board.cuts:
                print(
                    f"  #{board.board_index:<7} {cut.element.display_label:<30} "
                    f"{cut.element.length:>7.0f}{unit} "
                    f"{cut.element.width:>6.0f}{unit} "
                    f"{cut.element.thickness:>6.0f}{unit} "
                    f"{cut.start:>7.0f}{unit} "
                    f"{cut.end:>7.0f}{unit}"
                )
        print(f"\n  Boards needed for '{mat_id}': {len(boards)}")
        for board in boards:
            bar_len = 50
            used = int(board.utilization / 100 * bar_len)
            bar = "█" * used + "░" * (bar_len - used)
            print(f"  Board #{board.board_index}: [{bar}] {board.utilization:.0f}% used  waste={board.waste_length:.0f}{unit}")


def _print_inventory(report) -> None:
    print(f"\n{report.as_text()}")


def _print_joints(project) -> None:
    if not project.joints:
        return
    unit = project.unit
    print(f"\nJoints — {project.name}")
    print("=" * 70)
    for j in project.joints:
        from_el = project.get_element(j.from_element)
        to_el = project.get_element(j.to_element)
        from_label = from_el.display_label if from_el else j.from_element
        to_label = to_el.display_label if to_el else j.to_element
        print(f"  [{j.type:16}] {from_label}  →  {to_label}", end="")
        if j.description:
            print(f"  ({j.description})", end="")
        if j.depth:
            print(f"  depth={j.depth:.0f}{unit}", end="")
        if j.fastener:
            print(f"  fastener={j.fastener}", end="")
        print()


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="woodplan",
        description="Wood-plan: plan and visualize woodworking projects",
    )
    ap.add_argument("project_file", help="Path to the .wood YAML project file")
    ap.add_argument(
        "--output", "-o",
        help="Output file path for the HTML visualization (default: <project_name>.html)",
        default=None,
    )
    ap.add_argument(
        "--csv", "-c",
        help="Write inventory CSV to this path",
        default=None,
    )
    ap.add_argument(
        "--kerf",
        help="Saw kerf width (in project units, default: 3)",
        type=float,
        default=3.0,
    )
    ap.add_argument(
        "--no-html",
        action="store_true",
        help="Skip generating the HTML visualization",
    )

    args = ap.parse_args(argv)

    if not os.path.isfile(args.project_file):
        print(f"Error: project file not found: {args.project_file}", file=sys.stderr)
        sys.exit(1)

    try:
        project = project_parser.load(args.project_file)
    except Exception as exc:
        print(f"Error parsing project file: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        cut_result = cutlist_gen.generate(project, kerf=args.kerf)
    except ValueError as exc:
        print(f"Cut list error: {exc}", file=sys.stderr)
        sys.exit(1)

    report = inventory_gen.generate(project, cut_result)

    # ---- console output ----
    _print_cutlist(project, cut_result)
    _print_inventory(report)
    _print_joints(project)

    # ---- HTML output ----
    if not args.no_html:
        html_path = args.output
        if html_path is None:
            base = os.path.splitext(os.path.basename(args.project_file))[0]
            html_path = f"{base}.html"
        visualizer.save_html(project, cut_result, html_path)
        print(f"\nHTML report saved to: {html_path}")

    # ---- CSV output ----
    if args.csv:
        with open(args.csv, "w", encoding="utf-8") as fh:
            fh.write(report.as_csv())
        print(f"Inventory CSV saved to: {args.csv}")


if __name__ == "__main__":
    main()
