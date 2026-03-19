# MCP Server DRC Integration & Workflow Fix

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate DRC into the export pipeline, improve MCP tool descriptions so Claude Code actually uses them, and add a `run_drc` MCP tool for standalone DRC checks.

**Architecture:** Add DRC results to `export_kicad_project` output (automatic when kicad-cli is available). Add a standalone `run_drc` MCP tool. Improve all tool descriptions to guide Claude through the correct workflow. All DRC temp files use project-relative paths for Flatpak compatibility.

**Tech Stack:** Python 3.10+, mcp FastMCP, kicad-cli, pytest

---

### Task 1: Add DRC to the export pipeline

When `export_kicad_project` is called with a PCB path and kicad-cli is available, automatically run DRC and include results in the export dict under `result["drc"]`.

**Files:**
- Modify: `kicad/mcp_server/server.py:89-92`
- Modify: `kicad/cli.py` (add DRC to CLI export too)
- Test: `tests/test_mcp_server.py`

**Step 1: Write the failing test**

In `tests/test_mcp_server.py`, add:

```python
def test_export_includes_drc_when_available(monkeypatch, tmp_path):
    """export_kicad_project should include DRC results when kicad-cli is available."""
    from kicad.mcp_server.server import export_kicad_project_impl
    from kicad.kicad_cli import KiCadCLI

    # Create a minimal valid KiCad project in tmp_path
    sch_content = """(kicad_sch (version 20231120) (generator "test")
      (lib_symbols)
      (symbol (lib_id "Device:R") (at 0 0 0) (unit 1)
        (dnp no)
        (property "Reference" "R1")
        (property "Value" "10k")
        (property "Footprint" "Resistor_SMD:R_0603_1608Metric")
        (pin "1" (uuid "a1"))
        (instances (project "test" (path "/" (reference "R1") (unit 1))))
      )
    )"""
    pcb_content = """(kicad_pcb (version 20240108) (generator "test")
      (layers (0 "F.Cu" signal) (31 "B.Cu" mixed))
      (net 0 "")
      (gr_rect (start 0 0) (end 50 50) (layer "Edge.Cuts") (width 0.05))
    )"""
    pro_content = """{"board": {}, "schematic": {}}"""

    (tmp_path / "test.kicad_sch").write_text(sch_content)
    (tmp_path / "test.kicad_pcb").write_text(pcb_content)
    (tmp_path / "test.kicad_pro").write_text(pro_content)

    # Mock kicad-cli: make run_drc write a fake DRC JSON
    def mock_run_drc(self, pcb_path, output_path):
        import json
        drc = {"violations": [], "unconnected_items": [], "schematic_parity": []}
        with open(output_path, "w") as f:
            json.dump(drc, f)
        return output_path

    def mock_export_netlist(self, sch_path, output_path):
        # Write minimal valid netlist XML
        with open(output_path, "w") as f:
            f.write('<?xml version="1.0"?><export version="E"><nets></nets></export>')
        return output_path

    monkeypatch.setattr(KiCadCLI, "is_available", lambda self: True)
    monkeypatch.setattr(KiCadCLI, "run_drc", mock_run_drc)
    monkeypatch.setattr(KiCadCLI, "export_netlist", mock_export_netlist)

    result = export_kicad_project_impl(str(tmp_path))
    assert "drc" in result
    assert "violations" in result["drc"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_server.py::test_export_includes_drc_when_available -v`
Expected: FAIL — "drc" key not in result

**Step 3: Write minimal implementation**

In `kicad/mcp_server/server.py`, after the board export block (after line 92), add DRC:

```python
    # Run DRC if kicad-cli is available and we have a PCB
    if pcb_path and os.path.exists(pcb_path):
        cli = KiCadCLI() if "cli" not in dir() else cli
        if not hasattr(cli, '_cli'):
            from kicad.kicad_cli import KiCadCLI as _KiCadCLI
            cli = _KiCadCLI()
        if cli.is_available():
            try:
                pcb_dir = str(Path(pcb_path).parent)
                drc_tmp = os.path.join(pcb_dir, f".thomsonlint_drc_{os.getpid()}.json")
                cli.run_drc(pcb_path, drc_tmp)
                with open(drc_tmp) as f:
                    result["drc"] = json.load(f)
                os.unlink(drc_tmp)
            except Exception:
                pass  # DRC is best-effort
```

Note: the `cli` variable may already be defined from the netlist section. Handle this cleanly — restructure so `cli` is initialized once at the top of the function. Here's the cleaner approach:

At the top of `export_kicad_project_impl`, after resolving paths (after line 58), add:

```python
    cli = KiCadCLI()
    cli_available = cli.is_available()
```

Then replace `cli = KiCadCLI()` / `if cli.is_available():` in the netlist section with `if cli_available:`.

Then add after the board export block:

```python
    # Run DRC if kicad-cli is available and we have a PCB
    if pcb_path and os.path.exists(pcb_path) and cli_available:
        try:
            pcb_dir = str(Path(pcb_path).parent)
            drc_tmp = os.path.join(pcb_dir, f".thomsonlint_drc_{os.getpid()}.json")
            cli.run_drc(pcb_path, drc_tmp)
            with open(drc_tmp) as f:
                result["drc"] = json.load(f)
            os.unlink(drc_tmp)
        except Exception:
            pass  # DRC is best-effort
```

**Step 4: Run ALL tests**

Run: `uv run pytest tests/ -v`

**Step 5: Commit**

```bash
git add kicad/mcp_server/server.py tests/test_mcp_server.py
git commit -m "feat: include DRC results in export_kicad_project output"
```

---

### Task 2: Add standalone run_drc MCP tool

Add a `run_drc` MCP tool for running DRC independently, with Flatpak-safe temp paths.

**Files:**
- Modify: `kicad/mcp_server/server.py` (add tool in run_server)
- Test: `tests/test_mcp_server.py`

**Step 1: Write the failing test**

In `tests/test_mcp_server.py`, add:

```python
def test_run_drc_impl(monkeypatch, tmp_path):
    """run_drc tool should return parsed DRC JSON."""
    from kicad.mcp_server.server import run_drc_impl
    from kicad.kicad_cli import KiCadCLI

    pcb_file = tmp_path / "test.kicad_pcb"
    pcb_file.write_text("(kicad_pcb)")

    def mock_run_drc(self, pcb_path, output_path):
        import json
        with open(output_path, "w") as f:
            json.dump({"violations": [{"type": "test", "severity": "warning"}],
                       "unconnected_items": []}, f)
        return output_path

    monkeypatch.setattr(KiCadCLI, "is_available", lambda self: True)
    monkeypatch.setattr(KiCadCLI, "run_drc", mock_run_drc)

    result = run_drc_impl(str(pcb_file))
    assert "violations" in result
    assert len(result["violations"]) == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_server.py::test_run_drc_impl -v`
Expected: FAIL — `run_drc_impl` doesn't exist

**Step 3: Write minimal implementation**

In `kicad/mcp_server/server.py`, add the impl function (after `generate_report_impl`):

```python
def run_drc_impl(pcb_path: str) -> dict:
    """Run KiCad DRC on a PCB file and return the results.

    Uses project-relative temp paths for Flatpak compatibility.
    """
    from kicad.kicad_cli import KiCadCLI, KiCadCLIError

    cli = KiCadCLI()
    if not cli.is_available():
        raise RuntimeError(
            "kicad-cli not found. Install KiCad or see README for Flatpak setup."
        )

    p = Path(pcb_path)
    if not p.exists():
        raise FileNotFoundError(f"PCB file not found: {pcb_path}")

    # Use PCB directory for temp file (Flatpak can't write to /tmp)
    drc_tmp = str(p.parent / f".thomsonlint_drc_{os.getpid()}.json")
    try:
        cli.run_drc(str(p), drc_tmp)
        with open(drc_tmp) as f:
            return json.load(f)
    finally:
        if os.path.exists(drc_tmp):
            os.unlink(drc_tmp)
```

And register the tool in `run_server()`:

```python
    @mcp.tool()
    def run_drc(pcb_path: str) -> dict:
        """Run KiCad Design Rule Check (DRC) on a PCB file.

        Checks for violations like clearance errors, unconnected nets, and
        manufacturing rule violations. Requires kicad-cli on PATH.

        Args:
            pcb_path: Path to a .kicad_pcb file.

        Returns:
            Dict with 'violations', 'unconnected_items', etc. from KiCad DRC.
        """
        return run_drc_impl(pcb_path)
```

**Step 4: Run ALL tests**

Run: `uv run pytest tests/ -v`

**Step 5: Commit**

```bash
git add kicad/mcp_server/server.py tests/test_mcp_server.py
git commit -m "feat: add run_drc MCP tool for standalone DRC checks"
```

---

### Task 3: Improve MCP tool descriptions for workflow guidance

Claude Code didn't use the MCP tools because the descriptions don't clearly guide the workflow. The tool descriptions should tell Claude WHEN and HOW to use each tool.

**Files:**
- Modify: `kicad/mcp_server/server.py` (tool docstrings)

**Step 1: No test needed — documentation change only**

**Step 2: Update tool descriptions**

In `kicad/mcp_server/server.py`, update the tool docstrings in `run_server()`:

```python
    @mcp.tool()
    def export_kicad_project(project_path: str) -> dict:
        """Export a KiCad project for design review. CALL THIS FIRST.

        Parses schematic (.kicad_sch) and PCB (.kicad_pcb), runs analysis
        (net classification, decoupling proximity, edge distances, trace stats),
        enriches with kicad-cli netlist data, and runs DRC.

        After calling this, call get_review_context() to load the 158 engineering
        rules, then review the design against those rules.

        Args:
            project_path: Path to .kicad_pro file or project directory.

        Returns:
            Dict with 'schematic' (components, nets, analysis), 'board'
            (footprints, signals, analysis), and 'drc' (violations) data.
        """
        return export_kicad_project_impl(project_path)

    @mcp.tool()
    def get_review_context(section: str = "all") -> str:
        """Load the ThomsonLint engineering knowledge base. CALL THIS SECOND.

        Returns 158 design rules across 10 domains (Power, HighSpeed, Analog,
        EMC, DFM, DFT, Thermal, Component, Schematic, Mechanical) plus the
        engineering knowledge base with detailed guidance.

        Use this AFTER export_kicad_project to review the exported data against
        these rules. Each finding should reference a specific rule_id.

        Args:
            section: 'all' (default), 'instructions', 'ontology', or 'docs'.

        Returns:
            String containing rules, knowledge base, and review instructions.
        """
        return get_review_context_impl(section)

    @mcp.tool()
    def generate_report(findings_json: str) -> str:
        """Generate an HTML report from review findings. CALL THIS LAST.

        Takes a JSON string with project_name and issues array. Each issue needs:
        rule_id, severity (Critical/Major/Minor/Advisory), domain, summary.

        Args:
            findings_json: JSON string, e.g.:
                {"project_name": "my_board", "review_date": "2026-03-19",
                 "issues": [{"rule_id": "PWR_DECPL_001", "severity": "Major",
                 "domain": "Power", "summary": "Missing decoupling on U1"}]}

        Returns:
            Path to the generated HTML report file.
        """
        return generate_report_impl(findings_json)

    @mcp.tool()
    def run_drc(pcb_path: str) -> dict:
        """Run KiCad Design Rule Check on a PCB file.

        Returns violations (clearance, width, etc.), unconnected nets, and other
        DRC results. This is also automatically included in export_kicad_project
        output, so you only need this for standalone DRC checks.

        Args:
            pcb_path: Path to a .kicad_pcb file.

        Returns:
            Dict with 'violations', 'unconnected_items', etc.
        """
        return run_drc_impl(pcb_path)
```

**Step 3: Run ALL tests**

Run: `uv run pytest tests/ -v`

**Step 4: Commit**

```bash
git add kicad/mcp_server/server.py
git commit -m "docs: improve MCP tool descriptions for workflow guidance"
```

---

### Task 4: Add DRC to CLI export command

The CLI `export` command should also run DRC when kicad-cli is available, saving the DRC report alongside the schematic and board JSONs.

**Files:**
- Modify: `kicad/cli.py`

**Step 1: No new test — integration verified by re-exporting real design**

**Step 2: Add DRC to cmd_export**

In `kicad/cli.py`, after the board export block (after line ~104), add:

```python
    # Run DRC if kicad-cli is available and we have a PCB
    if pcb_path and os.path.exists(pcb_path):
        cli_for_drc = KiCadCLI()
        if cli_for_drc.is_available():
            try:
                pcb_dir = str(Path(pcb_path).parent)
                drc_tmp = os.path.join(pcb_dir, f".thomsonlint_drc_{os.getpid()}.json")
                cli_for_drc.run_drc(pcb_path, drc_tmp)
                # Copy DRC results to output directory
                import shutil
                drc_out = os.path.join(args.output, f"{project_name}_drc.json")
                shutil.move(drc_tmp, drc_out)
                print(f"DRC report saved: {drc_out}")
            except Exception as e:
                print(f"  Warning: DRC failed: {e}", file=sys.stderr)
```

Note: `KiCadCLI` is already imported at the top of `cmd_export`. The `cli` variable from the netlist section may have gone out of scope, so create a new instance.

**Step 3: Run ALL tests**

Run: `uv run pytest tests/ -v`

**Step 4: Verify on real design**

```bash
rm -rf benchmark/
uv run thomsonlint export /home/patrik/Desktop/smartLock/proto-dev-pcb/ --output ./benchmark/
ls benchmark/
# Expected: STM_PCB_schematic.json  STM_PCB_board.json  STM_PCB_drc.json
```

**Step 5: Commit**

```bash
git add kicad/cli.py
git commit -m "feat: include DRC report in CLI export output"
```

---

## Verification

After all tasks, test the full MCP workflow:

1. Restart Claude Code (to reload MCP server)
2. Ask: "Review my KiCad design at /home/patrik/Desktop/smartLock/proto-dev-pcb/"
3. Verify Claude:
   - Calls `export_kicad_project` (not `uv run thomsonlint export`)
   - Gets DRC results in the export (no separate kicad-cli call needed)
   - Calls `get_review_context` to load the 158 rules
   - References specific rule IDs in findings (PWR_DECPL_001, etc.)
   - Calls `generate_report` and produces an HTML file
