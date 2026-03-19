"""CLI entry point for ThomsonLint KiCad tools."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _find_project_files(project_path: str) -> tuple[str | None, str | None]:
    """Return (sch_path, pcb_path) from a project directory or .kicad_pro file."""
    p = Path(project_path)
    if p.is_file():
        # Accept .kicad_pro, .kicad_sch, or .kicad_pcb directly
        if p.suffix == ".kicad_sch":
            return str(p), None
        if p.suffix == ".kicad_pcb":
            return None, str(p)
        # Treat as project root (.kicad_pro or similar)
        base = p.parent / p.stem
        sch = base.with_suffix(".kicad_sch")
        pcb = base.with_suffix(".kicad_pcb")
        return (str(sch) if sch.exists() else None,
                str(pcb) if pcb.exists() else None)
    elif p.is_dir():
        # Prefer .kicad_pro to derive the root schematic/PCB names
        pro_files = list(p.glob("*.kicad_pro"))
        if pro_files:
            base = pro_files[0].parent / pro_files[0].stem
            sch = base.with_suffix(".kicad_sch")
            pcb = base.with_suffix(".kicad_pcb")
            return (str(sch) if sch.exists() else None,
                    str(pcb) if pcb.exists() else None)
        # Fallback: find first .kicad_sch and .kicad_pcb in directory
        sch_files = list(p.glob("*.kicad_sch"))
        pcb_files = list(p.glob("*.kicad_pcb"))
        return (str(sch_files[0]) if sch_files else None,
                str(pcb_files[0]) if pcb_files else None)
    return None, None


def cmd_export(args):
    """Parse project, analyze, export, and save JSONs."""
    from kicad.parsers.sch_parser import parse_schematic
    from kicad.parsers.pcb_parser import parse_pcb
    from kicad.analyzers.sch_analyzer import analyze_schematic
    from kicad.analyzers.brd_analyzer import analyze_board
    from kicad.exporters.sch_exporter import export_schematic
    from kicad.exporters.brd_exporter import export_board
    from kicad.kicad_cli import KiCadCLI, KiCadCLIError
    from kicad.parsers.netlist_parser import parse_netlist_xml_with_directions

    sch_path, pcb_path = _find_project_files(args.project)

    if not sch_path and not pcb_path:
        print(f"Error: no .kicad_sch or .kicad_pcb files found at '{args.project}'",
              file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)

    project_name = Path(sch_path or pcb_path).stem

    if sch_path and os.path.exists(sch_path):
        print(f"Parsing schematic: {sch_path}")
        sch = parse_schematic(sch_path)

        # Try to enrich nets via kicad-cli netlist export
        cli = KiCadCLI()
        if cli.is_available():
            try:
                # Use project dir for temp file — Flatpak can't write to /tmp
                sch_dir = Path(sch_path).parent
                netlist_tmp = str(sch_dir / f".thomsonlint_netlist_{os.getpid()}.xml")
                cli.export_netlist(sch_path, netlist_tmp)
                nets_from_netlist, pin_dirs = parse_netlist_xml_with_directions(netlist_tmp)
                # Update component pin directions from netlist
                for comp in sch.components:
                    for pin in comp.pins:
                        key = (comp.ref, pin.number)
                        if key in pin_dirs:
                            pin.direction = pin_dirs[key]
                sch = sch.__class__(
                    components=sch.components,
                    nets=nets_from_netlist,
                    sheets=sch.sheets,
                )
                os.unlink(netlist_tmp)
                print(f"  Enriched with {len(nets_from_netlist)} nets from kicad-cli netlist.")
            except (KiCadCLIError, Exception) as e:
                print(f"  Warning: kicad-cli netlist failed, nets may be incomplete: {e}",
                      file=sys.stderr)
        else:
            print("  Warning: kicad-cli not available; net connectivity not resolved.\n"
                  "  If KiCad is installed via Flatpak, see README for wrapper setup.",
                  file=sys.stderr)

        analysis = analyze_schematic(sch)
        export = export_schematic(sch, analysis, project_name)
        sch_out = os.path.join(args.output, f"{project_name}_schematic.json")
        with open(sch_out, "w") as f:
            json.dump(export, f, indent=2)
        print(f"Schematic export saved: {sch_out}")

    if pcb_path and os.path.exists(pcb_path):
        print(f"Parsing PCB: {pcb_path}")
        board = parse_pcb(pcb_path)
        analysis = analyze_board(board)
        export = export_board(board, analysis)
        pcb_out = os.path.join(args.output, f"{project_name}_board.json")
        with open(pcb_out, "w") as f:
            json.dump(export, f, indent=2)
        print(f"Board export saved: {pcb_out}")

        # Run DRC if kicad-cli is available
        drc_cli = KiCadCLI()
        if drc_cli.is_available():
            try:
                pcb_dir = str(Path(pcb_path).parent)
                drc_tmp = os.path.join(pcb_dir, f".thomsonlint_drc_{os.getpid()}.json")
                drc_cli.run_drc(pcb_path, drc_tmp)
                import shutil
                drc_out = os.path.join(args.output, f"{project_name}_drc.json")
                shutil.move(drc_tmp, drc_out)
                print(f"DRC report saved: {drc_out}")
            except Exception as e:
                print(f"  Warning: DRC failed: {e}", file=sys.stderr)


def cmd_serve(args):
    """Start the MCP server."""
    from kicad.mcp_server.server import run_server
    run_server()


def cmd_report(args):
    """Generate an HTML report from a findings JSON file."""
    gen_report = Path(__file__).parent.parent / "tools" / "gen_report.py"
    cmd = [sys.executable, str(gen_report), args.findings_json]
    if args.output:
        cmd += ["--output", args.output]
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="ThomsonLint KiCad tools — export, serve, report."
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # export
    p_export = subparsers.add_parser(
        "export",
        help="Parse a KiCad project and export JSON summaries.",
    )
    p_export.add_argument(
        "project",
        help="Path to .kicad_pro, .kicad_sch, .kicad_pcb, or project directory.",
    )
    p_export.add_argument(
        "--output", "-o",
        default="exports/",
        help="Output directory for JSON files (default: exports/).",
    )
    p_export.set_defaults(func=cmd_export)

    # serve
    p_serve = subparsers.add_parser(
        "serve",
        help="Start the MCP server.",
    )
    p_serve.set_defaults(func=cmd_serve)

    # report
    p_report = subparsers.add_parser(
        "report",
        help="Generate an HTML review report from a findings JSON.",
    )
    p_report.add_argument(
        "findings_json",
        help="Path to the findings JSON file.",
    )
    p_report.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory (default: exports/).",
    )
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
