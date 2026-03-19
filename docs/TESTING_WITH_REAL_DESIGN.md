# Testing ThomsonLint-KiCad with a Real Design

Step-by-step guide to set up, test, and benchmark the tool on a real KiCad project.

## 1. Setup on your PC

```bash
# Clone the fork
git clone git@github.com:paky12/ThomsonLint-KiCad.git
cd ThomsonLint-KiCad
git checkout development

# Install
uv sync

# Verify tests pass
uv run pytest tests/ -v
```

Confirm `kicad-cli` is available:
```bash
kicad-cli --version
```

## 2. CLI export test

Pick a KiCad project you have locally. Run:

```bash
uv run thomsonlint export /path/to/your-project.kicad_pro --output ./benchmark/
```

### What to check

**Did it produce two files?**
```bash
ls benchmark/
# Expected: your-project_schematic.json  your-project_board.json
```

**Do the files validate against schemas?**
```bash
uv run python -c "
import json, jsonschema
for suffix, schema in [('schematic', 'sch_export_schema'), ('board', 'brd_export_schema')]:
    with open(f'benchmark/YOUR_PROJECT_NAME_{suffix}.json') as f:
        data = json.load(f)
    with open(f'tests/{schema}.json') as f:
        s = json.load(f)
    jsonschema.validate(data, s)
    print(f'{suffix}: VALID')
"
```

**Spot-check the schematic export:**
```bash
uv run python -c "
import json
with open('benchmark/YOUR_PROJECT_NAME_schematic.json') as f:
    d = json.load(f)
print(f'Components: {len(d[\"components\"])}')
print(f'Nets: {len(d[\"nets\"])}')
print(f'Power nets: {d[\"analysis\"][\"power_nets\"]}')
print(f'Ground nets: {d[\"analysis\"][\"ground_nets\"]}')
print(f'Clock nets: {d[\"analysis\"][\"clock_nets\"]}')
print(f'Diff pairs: {d[\"analysis\"][\"differential_pairs\"]}')
print(f'Floating inputs: {len(d[\"analysis\"][\"floating_inputs\"])}')
print(f'Single-pin nets: {len(d[\"analysis\"][\"single_pin_nets\"])}')
"
```

Compare against what you know about the design:
- [ ] Component count matches what's in the schematic?
- [ ] All ICs found (U1, U2, ...)?
- [ ] Capacitors, resistors, connectors present?
- [ ] Power nets correctly identified (VCC, 3V3, 5V, etc.)?
- [ ] Ground nets correctly identified?
- [ ] Clock nets found if any?
- [ ] Differential pairs detected if any (USB, Ethernet, etc.)?
- [ ] Floating inputs make sense (known unconnected pins)?
- [ ] No false positives in single-pin nets?

**Spot-check the board export:**
```bash
uv run python -c "
import json
with open('benchmark/YOUR_PROJECT_NAME_board.json') as f:
    d = json.load(f)
print(f'Footprints: {len(d[\"components\"])}')
print(f'Layer count: {d[\"board\"][\"layer_count\"]}')
print(f'Board size: {d[\"board\"][\"area\"][\"width_mm\"]}mm x {d[\"board\"][\"area\"][\"height_mm\"]}mm')
print(f'Signals: {len(d[\"signals\"])}')
print(f'Components near edge: {len(d[\"analysis\"][\"component_edge_distances\"])}')
print(f'Decoupling entries: {len(d[\"analysis\"][\"decoupling_proximity\"])}')
print(f'Ground plane layers: {d[\"analysis\"][\"ground_plane_layers\"]}')
"
```

Compare against what you know:
- [ ] Footprint count matches component count?
- [ ] Board dimensions correct?
- [ ] Layer count correct (2, 4, 6)?
- [ ] Ground plane on expected layers?
- [ ] Decoupling proximity entries exist for ICs with nearby caps?
- [ ] Components near board edge flagged correctly?

## 3. kicad-cli netlist enrichment test

The export should also try kicad-cli netlist export for net connectivity. Check the output:

```bash
# Look for the "Enriched with N nets" message in the CLI output
# If you see "Warning: kicad-cli not available" — kicad-cli isn't on PATH
```

If nets were enriched, check:
- [ ] Net count is non-zero in the schematic export?
- [ ] Pin directions are set (not all "PAS")?
- [ ] Power pins show "PWR", output pins show "OUT", etc.?

## 4. MCP server test

```bash
# Start the server in background
uv run thomsonlint serve &
MCP_PID=$!

# Test with Claude Code
claude

# In Claude Code, ask:
# "Review my KiCad design at /path/to/your-project.kicad_pro"

# When done:
kill $MCP_PID
```

Or configure it properly in `~/.claude/settings.json`:
```json
{
  "mcpServers": {
    "thomsonlint": {
      "command": "uv",
      "args": ["--directory", "/path/to/ThomsonLint-KiCad", "run", "thomsonlint", "serve"]
    }
  }
}
```

Then just open Claude Code anywhere and ask it to review your design.

### What to check in the Claude Code review:
- [ ] Claude calls `export_kicad_project` tool successfully?
- [ ] Claude calls `get_review_context` to load the knowledge base?
- [ ] Claude identifies real issues (missing decoupling, ESD protection, etc.)?
- [ ] Findings reference specific rule IDs (PWR_DECPL_001, EMC_ESD_001, etc.)?
- [ ] Claude calls `generate_report` and produces an HTML file?
- [ ] The HTML report opens correctly in a browser?

## 5. Known issues to watch for

These are things we expect might break on real designs:

| Issue | Symptom | Where to fix |
|-------|---------|-------------|
| Board outline with arcs | `board.outline.width_mm = 0` | `kicad/parsers/pcb_parser.py` — `_parse_edge_item` doesn't handle `gr_arc` |
| Pin names vs numbers | All floating inputs show pin numbers not names | Need netlist XML enrichment (kicad-cli) |
| Hierarchical schematics | Missing components from sub-sheets | `kicad/parsers/sch_parser.py` — `_parse_sch_recursive` |
| Large designs (1000+ components) | Slow parsing | S-expression parser may need optimization |
| Net classes | All nets show empty class `{"name":"","width_mm":0}` | Not yet implemented |
| KiCad 9 new syntax | Parser crash on unknown nodes | S-expression parser should skip unknown nodes gracefully |

## 6. Reporting results

After testing, note:
1. **KiCad version** you tested with
2. **Project complexity** (component count, layer count, board size)
3. **What worked** — which checks passed above
4. **What broke** — parser errors, wrong data, missing components
5. **Parser errors** — copy the full traceback

This will help prioritize fixes for v0.2.
