"""MCP server exposing ThomsonLint tools: export, review context, and report generation."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import jsonschema

# REPO_ROOT: server.py is at kicad/mcp_server/server.py → parent.parent.parent = repo root
REPO_ROOT = Path(__file__).parent.parent.parent


def export_kicad_project_impl(project_path: str) -> dict:
    """Parse a KiCad project and return a combined export dict.

    Parses any .kicad_sch and .kicad_pcb files found at project_path,
    runs analysis, and returns the serialisable export dictionaries.
    """
    from kicad.parsers.sch_parser import parse_schematic
    from kicad.parsers.pcb_parser import parse_pcb
    from kicad.analyzers.sch_analyzer import analyze_schematic
    from kicad.analyzers.brd_analyzer import analyze_board
    from kicad.exporters.sch_exporter import export_schematic
    from kicad.exporters.brd_exporter import export_board
    from kicad.kicad_cli import KiCadCLI, KiCadCLIError
    from kicad.parsers.netlist_parser import parse_netlist

    p = Path(project_path)
    result: dict = {}

    # Resolve sch/pcb paths
    if p.is_dir():
        sch_files = list(p.glob("*.kicad_sch"))
        pcb_files = list(p.glob("*.kicad_pcb"))
        sch_path = str(sch_files[0]) if sch_files else None
        pcb_path = str(pcb_files[0]) if pcb_files else None
    elif p.suffix == ".kicad_sch":
        sch_path, pcb_path = str(p), None
    elif p.suffix == ".kicad_pcb":
        sch_path, pcb_path = None, str(p)
    else:
        base = p.parent / p.stem
        sch_candidate = base.with_suffix(".kicad_sch")
        pcb_candidate = base.with_suffix(".kicad_pcb")
        sch_path = str(sch_candidate) if sch_candidate.exists() else None
        pcb_path = str(pcb_candidate) if pcb_candidate.exists() else None

    project_name = Path(sch_path or pcb_path or project_path).stem

    if sch_path and os.path.exists(sch_path):
        sch = parse_schematic(sch_path)

        # Try kicad-cli netlist for net connectivity
        cli = KiCadCLI()
        if cli.is_available():
            try:
                with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tf:
                    netlist_tmp = tf.name
                cli.export_netlist(sch_path, netlist_tmp)
                nets = parse_netlist(netlist_tmp)
                sch = sch.__class__(
                    components=sch.components,
                    nets=nets,
                    sheets=sch.sheets,
                )
                os.unlink(netlist_tmp)
            except (KiCadCLIError, Exception):
                pass  # proceed with incomplete nets

        analysis = analyze_schematic(sch)
        result["schematic"] = export_schematic(sch, analysis, project_name)

    if pcb_path and os.path.exists(pcb_path):
        board = parse_pcb(pcb_path)
        analysis = analyze_board(board)
        result["board"] = export_board(board, analysis)

    if not result:
        raise ValueError(f"No KiCad project files found at: {project_path}")

    return result


def get_review_context_impl(section: str = "all") -> str:
    """Return review instructions and/or ontology content.

    section: "all" | "instructions" | "ontology" | "docs"
    """
    parts: list[str] = []

    if section in ("all", "instructions"):
        instructions_path = REPO_ROOT / "review_instructions.txt"
        if instructions_path.exists():
            parts.append("=== REVIEW INSTRUCTIONS ===\n")
            parts.append(instructions_path.read_text(encoding="utf-8"))

    if section in ("all", "ontology"):
        ontology_path = REPO_ROOT / "ontology" / "ontology.json"
        if ontology_path.exists():
            parts.append("\n=== ONTOLOGY ===\n")
            parts.append(ontology_path.read_text(encoding="utf-8"))

    if section in ("all", "docs"):
        docs_dir = REPO_ROOT / "docs"
        if docs_dir.exists():
            for doc_file in sorted(docs_dir.glob("*.md")):
                parts.append(f"\n=== DOC: {doc_file.name} ===\n")
                parts.append(doc_file.read_text(encoding="utf-8"))

    if not parts:
        raise ValueError(
            f"Unknown section '{section}'. Use 'all', 'instructions', 'ontology', or 'docs'."
        )

    return "".join(parts)


def generate_report_impl(findings_json: str) -> str:
    """Validate findings JSON against schema and generate an HTML report.

    findings_json: JSON string (not a file path) containing ThomsonLint findings.
    Returns the path to the generated HTML report.
    """
    # Parse JSON
    try:
        findings = json.loads(findings_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e

    # Validate against findings_schema.json
    schema_path = REPO_ROOT / "tests" / "findings_schema.json"
    if schema_path.exists():
        with open(schema_path) as f:
            schema = json.load(f)
        jsonschema.validate(instance=findings, schema=schema)

    # Write findings to a temp file and call gen_report.py
    gen_report = REPO_ROOT / "tools" / "gen_report.py"
    exports_dir = REPO_ROOT / "exports"
    exports_dir.mkdir(exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir=str(exports_dir)
    ) as tf:
        json.dump(findings, tf)
        tmp_findings_path = tf.name

    try:
        result = subprocess.run(
            [sys.executable, str(gen_report), tmp_findings_path, "--output", str(exports_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"gen_report.py failed (exit {result.returncode}): {result.stderr}"
            )
    finally:
        os.unlink(tmp_findings_path)

    # Extract the output path from gen_report.py's stdout
    for line in result.stdout.splitlines():
        if line.startswith("Report generated:"):
            return line.split(":", 1)[1].strip()

    return str(exports_dir)


def run_server():
    """Create and run the FastMCP server with ThomsonLint tools."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("ThomsonLint")

    @mcp.tool()
    def export_kicad_project(project_path: str) -> dict:
        """Export a KiCad project (schematic + PCB) to structured JSON for AI review.

        Args:
            project_path: Path to a .kicad_pro, .kicad_sch, .kicad_pcb, or project directory.

        Returns:
            Dict with 'schematic' and/or 'board' export data.
        """
        return export_kicad_project_impl(project_path)

    @mcp.tool()
    def get_review_context(section: str = "all") -> str:
        """Get ThomsonLint review instructions and design rule ontology.

        Args:
            section: Which context to return — 'all', 'instructions', 'ontology', or 'docs'.

        Returns:
            String containing the requested context.
        """
        return get_review_context_impl(section)

    @mcp.tool()
    def generate_report(findings_json: str) -> str:
        """Generate an HTML review report from ThomsonLint findings JSON.

        Args:
            findings_json: JSON string containing findings (project_name + issues array).

        Returns:
            Path to the generated HTML report file.
        """
        return generate_report_impl(findings_json)

    mcp.run()


if __name__ == "__main__":
    run_server()
