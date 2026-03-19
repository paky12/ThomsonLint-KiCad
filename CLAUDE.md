# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## What This Is

ThomsonLint-KiCad is a fork of [ThomsonLint](https://github.com/holla2040/ThomsonLint) that adds native KiCad export support. It's an AI-powered hardware design review framework: export KiCad schematic + PCB data, run it through 158 engineering rules, get actionable findings.

The fork adds a `kicad/` Python package (parsers, analyzers, exporters) and an MCP server. The upstream knowledge base (ontology, rules, examples, report generator) is kept unchanged.

## Commands

```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_net_classifier.py -v

# Run with coverage
uv run pytest --cov=kicad --cov-report=html tests/

# Export a KiCad project to ThomsonLint JSON
uv run thomsonlint export path/to/project.kicad_pro --output ./exports/

# Start the MCP server
uv run thomsonlint serve

# Generate HTML report from findings
uv run thomsonlint report findings.json --output ./exports/

# Validate upstream JSON files (ontology, examples)
uv run python validate_json.py

# Regenerate review_instructions.txt (after modifying ontology/KB/examples)
./gen_context.sh > review_instructions.txt
```

## Architecture

```
kicad/
  parsers/
    sexpr.py           # S-expression tokenizer → nested Python lists
    sch_parser.py       # .kicad_sch → Schematic dataclass (recursive for hierarchical)
    pcb_parser.py       # .kicad_pcb → Board dataclass
    netlist_parser.py   # kicad-cli netlist XML → Net objects + pin directions
  models/
    schematic.py        # Pin, Component, Net, Sheet, Schematic
    board.py            # Pad, Footprint, TrackSegment, Via, Zone, BoardOutline, Layer, Hole, Board
  analyzers/
    net_classifier.py   # Power/ground/clock/differential detection, component type classification
    sch_analyzer.py     # Floating inputs, single-pin nets, diff pairs, net lists
    brd_analyzer.py     # Trace stats, decoupling proximity, edge distances, ground planes
  exporters/
    sch_exporter.py     # Schematic + analysis → ThomsonLint JSON
    brd_exporter.py     # Board + analysis → ThomsonLint JSON
  kicad_cli.py          # Wrapper around kicad-cli subprocess calls
  cli.py                # CLI entry point (export, serve, report)
  mcp_server/
    server.py           # MCP server with 3 tools (export, review context, report)
```

### Data flow

```
KiCad .kicad_pro
  ├─ kicad-cli → netlist XML, BOM, positions (structured CLI output)
  ├─ .kicad_sch → sexpr parser → sch_parser → Schematic dataclass
  └─ .kicad_pcb → sexpr parser → pcb_parser → Board dataclass
        │
        ├─ sch_analyzer → floating inputs, diff pairs, net classification
        └─ brd_analyzer → trace lengths, decoupling proximity, edge distances
              │
              ├─ sch_exporter → *-thomson-export-sch.json
              └─ brd_exporter → *-thomson-export-brd.json
                    │
                    └─ Claude Code + review_instructions.txt → findings.json → HTML report
```

### Dual-source strategy

- **kicad-cli** provides: netlist (authoritative net connectivity), BOM, component positions, drill data, DRC
- **Direct .kicad_sch/.kicad_pcb parsing** provides: pin directions, trace lengths, via counts per net, zone pours, pad coordinates, board outline, layer stackup — data CLI can't export

### Key design decisions

- **Multi-char prefixes checked before single-char** in component classification (`FB` before `F`, `TP` before `T`) — fixes a bug in the upstream Fusion ULP
- **Pin directions mapped to ULP short strings** in export JSON: `input→IN`, `output→OUT`, `bidirectional→IO`, `passive→PAS`, `power_in→PWR`, `power_out→SUP`
- **`trace_segments` only present** on high-speed/clock/differential nets (conditionally omitted for others)
- **MCP package lives at `kicad/mcp_server/`** not `mcp/` — avoids shadowing the `mcp` PyPI package
- **Schematic nets come from kicad-cli** (`sch export netlist`), not from direct parsing — the `.kicad_sch` parser only extracts component/pin metadata

## Upstream files (do not modify)

These are kept in sync with `holla2040/ThomsonLint` upstream:

- `ontology/ontology.json` — 158 rules across 10 domains
- `docs/AI_Hardware_Design_Review_KnowledgeBase.md` — engineering knowledge base
- `examples/examples.json` — 16 example scenarios
- `tools/gen_report.py` — HTML report generator
- `tools/fusion-electronics-export.ulp` — Fusion Electronics exporter (kept for upstream compat)
- `review_instructions.txt` — pre-generated AI review prompt (~214KB)
- `validate_json.py` — JSON schema validator
- `gen_context.sh` — review instructions generator
- `tests/ontology_schema.json`, `tests/examples_schema.json`, `tests/findings_schema.json`

To pull upstream updates: `git fetch upstream && git merge upstream/main`

## Test layout

```
tests/
  fixtures/              # Minimal KiCad 9 project (schematic + PCB + project file)
  test_sexpr.py          # S-expression parser
  test_net_classifier.py # Signal/component classification
  test_sch_parser.py     # Schematic parser
  test_pcb_parser.py     # PCB parser
  test_netlist_parser.py # Netlist XML parser
  test_sch_analyzer.py   # Schematic analysis
  test_brd_analyzer.py   # Board analysis
  test_sch_exporter.py   # Schematic export + schema validation
  test_brd_exporter.py   # Board export + schema validation
  test_kicad_cli.py      # kicad-cli wrapper (mocked)
  test_mcp_server.py     # MCP server tools
  sch_export_schema.json # JSON schema for schematic export
  brd_export_schema.json # JSON schema for board export
```

## Git remotes

- `origin` → `paky12/ThomsonLint-KiCad` (this fork)
- `upstream` → `holla2040/ThomsonLint` (original)

## System requirements

- Python 3.10+
- KiCad 8+ with `kicad-cli` on PATH (Flatpak users: `kicad-cli` is not exposed on PATH — create a wrapper at `/usr/local/bin/kicad-cli` that runs `flatpak run --command=kicad-cli org.kicad.KiCad "$@"`)
- uv (Python package manager)
