# ThomsonLint-KiCad

AI-powered hardware design review for KiCad projects. Fork of [ThomsonLint](https://github.com/holla2040/ThomsonLint) with native KiCad support.

Analyzes your schematics and PCB layouts against 158 engineering rules covering power integrity, high-speed routing, EMC, analog design, DFM, and more — then produces actionable findings with severity ratings.

## Quick Start

### 1. Install

```bash
git clone git@github.com:paky12/ThomsonLint-KiCad.git
cd ThomsonLint-KiCad
pip install -e .
```

Requires **Python 3.10+** and **KiCad 8+** (with `kicad-cli` on PATH).

### 2. Use with Claude Code (recommended)

Add the MCP server to your Claude Code config (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "thomsonlint": {
      "command": "thomsonlint",
      "args": ["serve"]
    }
  }
}
```

Then open Claude Code and ask:

> **"Review my KiCad design at ~/projects/my-board/my-board.kicad_pro"**

Claude will:
1. Export your schematic and PCB data (components, nets, traces, placement)
2. Load the 158-rule engineering knowledge base
3. Walk through each rule and report findings with severity ratings
4. Generate an interactive HTML report

That's it. No manual exporting, no prompt engineering.

### 3. Use from the command line

```bash
# Export KiCad project to ThomsonLint JSON
thomsonlint export ~/projects/my-board/my-board.kicad_pro --output ./exports/

# Generate HTML report from review findings
thomsonlint report findings.json --output ./exports/
```

The exported JSONs can be fed to any LLM along with `review_instructions.txt` for a manual review.

## What It Checks

| Domain | Examples | Rules |
|--------|---------|-------|
| **Power** | Missing decoupling, regulator placement, SMPS hot loops | 18 |
| **High-Speed** | Impedance control, diff pair routing, DDR length matching | 26 |
| **Analog** | Op-amp stability, ADC drivers, sensor front-ends | 11 |
| **EMC/ESD** | Missing TVS diodes, ground stitching, loop area | 12 |
| **DFM** | Acid traps, fiducials, BOM completeness | 24 |
| **DFT** | Test points, debug access, silkscreen labeling | 17 |
| **Thermal** | Power density, thermal vias, heat dissipation | 12 |
| **Component** | Voltage ratings, capacitor types, inductor saturation | 14 |
| **Schematic** | Floating inputs, single-pin nets, value errors | 14 |
| **Mechanical** | Connector stress, mounting holes, edge clearance | 6 |

## How It Works

```
KiCad Project (.kicad_pro)
    |
    |-- kicad-cli --> netlist, BOM, positions, drill data
    |-- .kicad_sch --> component pins, hierarchical sheets
    |-- .kicad_pcb --> traces, vias, zones, board outline
    |
    v
 Analyzers (signal classification, floating inputs,
            decoupling proximity, edge distances, ...)
    |
    v
 ThomsonLint JSON (same format as upstream)
    |
    v
 Claude Code + 158-rule knowledge base --> findings.json
    |
    v
 Interactive HTML report
```

**Dual-source data extraction:** `kicad-cli` provides structured exports (netlist XML, BOM, positions). Direct `.kicad_sch`/`.kicad_pcb` parsing provides data CLI can't export (trace lengths, via counts per net, zone pours, pad coordinates, board outline, layer stackup).

## MCP Tools

When running as an MCP server (`thomsonlint serve`), three tools are available:

| Tool | What it does |
|------|-------------|
| `export_kicad_project` | Parse KiCad project, run analysis, return schematic + board JSONs |
| `get_review_context` | Return the engineering knowledge base (ontology + rules + examples) |
| `generate_report` | Generate interactive HTML report from review findings |

## Requirements

- **Python 3.10+**
- **KiCad 8+** with `kicad-cli` on PATH
- **Claude Code** (for the MCP integration)

Python dependencies (installed automatically):
- `mcp` — Anthropic MCP SDK
- `jsonschema` — JSON validation

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run tests with coverage
pytest --cov=kicad --cov-report=html tests/
```

## Credits

Based on [ThomsonLint](https://github.com/holla2040/ThomsonLint) by holla2040. The ontology, knowledge base, examples, and report generator are from the upstream project. This fork adds KiCad export capability and MCP server integration.
