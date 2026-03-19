# Real-Design Bugfixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 7 bugs discovered during first real-design test (smartLock 4-layer STM32+ESP32 board, 66 components, 113 nets).

**Architecture:** All fixes are in the `kicad/` package — parsers, analyzers, net classifier, and exporters. Each bug is independent, so tasks can be executed in any order. Every fix follows TDD: write failing test first, then implement.

**Tech Stack:** Python 3.10+, pytest, dataclasses, no new dependencies.

---

### Task 1: Fix DNP/populate parsing for KiCad 9

KiCad 9 changed `(dnp)` to `(dnp yes)` / `(dnp no)`. The parser treats ANY `dnp` node as DNP=true, causing all 66 components to show `populate: false`.

**Files:**
- Modify: `kicad/parsers/sch_parser.py:68-69`
- Test: `tests/test_sch_parser.py`

**Step 1: Write the failing test**

In `tests/test_sch_parser.py`, add a test that verifies `(dnp no)` means populate=True. This requires adding a component with `(dnp no)` to the test fixture.

```python
def test_dnp_no_means_populate_true(tmp_path):
    """KiCad 9 uses (dnp no) for normal components, (dnp yes) for DNP."""
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
      (symbol (lib_id "Device:R") (at 0 0 0) (unit 1)
        (dnp yes)
        (property "Reference" "R2")
        (property "Value" "10k")
        (property "Footprint" "Resistor_SMD:R_0603_1608Metric")
        (pin "1" (uuid "a2"))
        (instances (project "test" (path "/" (reference "R2") (unit 1))))
      )
    )"""
    sch_file = tmp_path / "test.kicad_sch"
    sch_file.write_text(sch_content)
    from kicad.parsers.sch_parser import parse_schematic
    sch = parse_schematic(str(sch_file))
    comps = {c.ref: c for c in sch.components}
    assert comps["R1"].populate is True   # dnp no → populate
    assert comps["R2"].populate is False  # dnp yes → do not populate
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sch_parser.py::test_dnp_no_means_populate_true -v`
Expected: FAIL — R1.populate will be False (bug: any dnp node → True)

**Step 3: Write minimal implementation**

In `kicad/parsers/sch_parser.py`, change lines 68-69 from:
```python
        elif child[0] == "dnp":
            is_dnp = True
```
to:
```python
        elif child[0] == "dnp":
            # KiCad 9: (dnp yes) = do not populate, (dnp no) = populate
            # KiCad 8: bare (dnp) = do not populate
            is_dnp = len(child) < 2 or str(child[1]).lower() != "no"
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_sch_parser.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add kicad/parsers/sch_parser.py tests/test_sch_parser.py
git commit -m "fix: handle KiCad 9 (dnp no)/(dnp yes) populate flag"
```

---

### Task 2: Fix +3.3V and VREF not detected as power nets

`classify_net("+3.3V")` returns `is_power=False`. The pattern list has `+3V` (matches `+3V3`) but not `3.3V`. Also `VREF` nets are not recognized as power.

**Files:**
- Modify: `kicad/analyzers/net_classifier.py:22-25`
- Test: `tests/test_net_classifier.py`

**Step 1: Write the failing tests**

In `tests/test_net_classifier.py`, inside `TestPowerNets`:

```python
def test_plus_3_3v(self):
    cl = classify_net("+3.3V")
    assert cl.is_power

def test_vref_plus(self):
    cl = classify_net("VREF+")
    assert cl.is_power

def test_vdda(self):
    cl = classify_net("VDDA")
    assert cl.is_power
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_net_classifier.py::TestPowerNets::test_plus_3_3v tests/test_net_classifier.py::TestPowerNets::test_vref_plus -v`
Expected: FAIL — these patterns aren't in the list

**Step 3: Write minimal implementation**

In `kicad/analyzers/net_classifier.py`, update the `power_patterns` list (line 22-25):

```python
    power_patterns = [
        "VCC", "VDD", "VBUS", "VIN", "VOUT", "VBAT", "VSYS", "VREF",
        "+3V", "+5V", "+12V", "+24V", "3V3", "3.3V", "5V0", "1V8", "1V2", "2V5", "PWR",
    ]
```

Changes: added `"VREF"`, `"3.3V"`. Note: `VDDA` already matches via `VDD`.

Also update `_guess_voltage` to handle `+3.3V` (it already has `"3.3" in upper` on line 86, so voltage guess works).

**Step 4: Run tests**

Run: `uv run pytest tests/test_net_classifier.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add kicad/analyzers/net_classifier.py tests/test_net_classifier.py
git commit -m "fix: detect +3.3V and VREF as power nets"
```

---

### Task 3: Fix "IC" prefix component classification

Components with ref `IC1`, `IC3`, `IC4`, `IC7` are classified as "other" because `I` is not in `_SINGLE_CHAR_PREFIXES` and `IC` is not in `_MULTI_CHAR_PREFIXES`. This causes the decoupling proximity analyzer to miss all ICs with `IC` prefix, which is why only U1 (the one with `U` prefix) was found.

Also: `FP_conn1` → "fuse" (F prefix), `Keypad_conn1` → "relay" (K prefix). Refs containing "conn" should be classified as connectors.

**Files:**
- Modify: `kicad/analyzers/net_classifier.py:129-134, 143-163`
- Test: `tests/test_net_classifier.py`

**Step 1: Write the failing tests**

In `tests/test_net_classifier.py`, inside `TestClassifyComponent`:

```python
def test_ic_prefix(self):
    assert classify_component("IC1") == "IC"

def test_ic7_prefix(self):
    assert classify_component("IC7") == "IC"

def test_conn_in_ref(self):
    assert classify_component("FP_conn1") == "connector"

def test_keypad_conn(self):
    assert classify_component("Keypad_conn1") == "connector"

def test_sc50_conn(self):
    assert classify_component("SC50_conn1") == "connector"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_net_classifier.py::TestClassifyComponent::test_ic_prefix tests/test_net_classifier.py::TestClassifyComponent::test_conn_in_ref -v`
Expected: FAIL — IC1→"other", FP_conn1→"fuse"

**Step 3: Write minimal implementation**

In `kicad/analyzers/net_classifier.py`, add `IC` to multi-char prefixes (line 129-134):

```python
_MULTI_CHAR_PREFIXES = [
    ("IC", "IC"),
    ("FB", "ferrite_bead"),
    ("TP", "test_point"),
    ("SW", "switch"),
    ("BT", "battery"),
]
```

And add a `conn` check in `classify_component` before the single-char fallback (after line 149):

```python
def classify_component(ref: str, description: str = "") -> str:
    if not ref:
        return "unknown"

    upper_ref = ref.upper()

    for prefix, comp_type in _MULTI_CHAR_PREFIXES:
        if upper_ref.startswith(prefix):
            return comp_type

    # Refs containing "conn" are connectors (e.g., FP_conn1, Keypad_conn1)
    if "CONN" in upper_ref:
        return "connector"

    first = ref[0].upper()

    if first == "D":
        upper_desc = description.upper()
        if "LED" in upper_desc:
            return "LED"
        if "TVS" in upper_desc or "ESD" in upper_desc:
            return "TVS"
        if "ZENER" in upper_desc:
            return "zener"
        return "diode"

    return _SINGLE_CHAR_PREFIXES.get(first, "other")
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_net_classifier.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add kicad/analyzers/net_classifier.py tests/test_net_classifier.py
git commit -m "fix: classify IC-prefix components and conn-containing refs"
```

---

### Task 4: Fix layer_count to report copper layers only

`layer_count` is 20 because the parser counts all layers with number 0-31 (the copper range), but KiCad defines unused copper layer slots in the file. The board export should show 4 (the actual copper layers: F.Cu, In1.Cu, In2.Cu, B.Cu).

**Files:**
- Modify: `kicad/parsers/pcb_parser.py:37-60`
- Test: `tests/test_pcb_parser.py`

**Step 1: Write the failing test**

In `tests/test_pcb_parser.py`, add:

```python
def test_layer_count_is_copper_only(sch_board):
    """layer_count should count only copper layers with signal/power/mixed type."""
    # The test fixture has F.Cu and B.Cu → 2 copper layers
    assert sch_board.layer_count == 2
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pcb_parser.py::test_layer_count_is_copper_only -v`
Expected: FAIL — test fixture might report higher count depending on fixture content

**Step 3: Write minimal implementation**

In `kicad/parsers/pcb_parser.py`, change `_parse_layers` (lines 56-58) from:

```python
        # Count copper layers (layer numbers 0–31 are copper in KiCad)
        if 0 <= int(num) <= 31:
            copper_count += 1
```

to:

```python
        # Count copper layers by type (signal, power, or mixed)
        if layer_type in ("signal", "power", "mixed"):
            copper_count += 1
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_pcb_parser.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add kicad/parsers/pcb_parser.py tests/test_pcb_parser.py
git commit -m "fix: count only signal/power/mixed layers as copper in layer_count"
```

---

### Task 5: Add mounting hole extraction from footprints

The `holes` array is empty because the parser only looks for standalone `np_thru_hole` pads at the top level. In KiCad, mounting holes are footprints (e.g., `MountingHole:MountingHole_3.2mm`). We need to extract them from footprints that have np_thru_hole pads and no electrical pads.

**Files:**
- Modify: `kicad/parsers/pcb_parser.py:328-340`
- Test: `tests/test_pcb_parser.py`

**Step 1: Write the failing test**

In `tests/test_pcb_parser.py`, add:

```python
def test_mounting_holes_from_footprints(tmp_path):
    """Mounting holes are footprints with np_thru_hole pads, no electrical nets."""
    pcb_content = """(kicad_pcb (version 20240108) (generator "test")
      (layers (0 "F.Cu" signal) (31 "B.Cu" mixed))
      (net 0 "")
      (footprint "MountingHole:MountingHole_3.2mm" (at 10 20) (layer "F.Cu")
        (fp_text reference "H1" (at 0 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
        (pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (layers "*.Cu" "*.Mask"))
      )
      (gr_rect (start 0 0) (end 50 50) (layer "Edge.Cuts") (width 0.05))
    )"""
    pcb_file = tmp_path / "test.kicad_pcb"
    pcb_file.write_text(pcb_content)
    from kicad.parsers.pcb_parser import parse_pcb
    board = parse_pcb(str(pcb_file))
    assert len(board.holes) >= 1
    assert board.holes[0].drill_mm == 3.2
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pcb_parser.py::test_mounting_holes_from_footprints -v`
Expected: FAIL — holes array will be empty

**Step 3: Write minimal implementation**

In `kicad/parsers/pcb_parser.py`, after the existing standalone hole parsing (after line 340), add footprint-based mounting hole extraction:

```python
    # Also extract mounting holes from footprints with np_thru_hole pads
    for fp in footprints:
        for pad in fp.pads:
            if pad.type == "np_thru_hole":
                # Find drill size from the raw footprint node
                drill_mm = 0.0
                for fp_node in _find_children(nodes, "footprint"):
                    ref_text = ""
                    for child in fp_node[1:]:
                        if isinstance(child, list) and child and child[0] == "fp_text":
                            if len(child) > 1 and child[1] == "reference":
                                ref_text = str(child[2]) if len(child) > 2 else ""
                    if ref_text == fp.ref:
                        for child in fp_node[1:]:
                            if isinstance(child, list) and child and child[0] == "pad":
                                drill_node = _find_child(child, "drill")
                                if drill_node and len(drill_node) > 1:
                                    drill_mm = float(drill_node[1])
                        break
                holes.append(Hole(
                    x_mm=pad.x_mm,
                    y_mm=pad.y_mm,
                    drill_mm=drill_mm,
                ))
```

**Note:** This is complex because pad drill sizes aren't stored on the Pad dataclass. A cleaner approach: add `drill_mm` to the Pad model and extract it during pad parsing.

**Alternative cleaner implementation** — add `drill_mm` to Pad:

In `kicad/models/board.py`, update Pad:
```python
@dataclass
class Pad:
    number: str
    type: str        # smd, thru_hole, np_thru_hole
    x_mm: float
    y_mm: float
    net_code: int = 0
    net_name: str = ""
    drill_mm: float = 0.0
```

In `kicad/parsers/pcb_parser.py` `_parse_pad()`, extract drill:
```python
    drill_node = _find_child(pad_node, "drill")
    drill_mm = float(drill_node[1]) if drill_node and len(drill_node) > 1 else 0.0
```
Add `drill_mm=drill_mm` to Pad constructor.

Then the hole extraction from footprints becomes:
```python
    # Extract mounting holes from footprints with np_thru_hole pads
    for fp in footprints:
        for pad in fp.pads:
            if pad.type == "np_thru_hole":
                holes.append(Hole(x_mm=pad.x_mm, y_mm=pad.y_mm, drill_mm=pad.drill_mm))
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_pcb_parser.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add kicad/models/board.py kicad/parsers/pcb_parser.py tests/test_pcb_parser.py
git commit -m "fix: extract mounting holes from footprints with np_thru_hole pads"
```

---

### Task 6: Add value field to board component export

The board export components only have `ref`, `x_mm`, `y_mm`, `rotation`, `side`, `type`, `footprint`. Missing `value` makes it harder for reviewers to understand what each component is (e.g., is C1 a 100nF or 10uF?).

**Files:**
- Modify: `kicad/models/board.py` (add `value` to Footprint)
- Modify: `kicad/parsers/pcb_parser.py` (extract value property)
- Modify: `kicad/exporters/brd_exporter.py` (include value in export)
- Modify: `tests/brd_export_schema.json` (add value to schema)
- Test: `tests/test_brd_exporter.py`

**Step 1: Write the failing test**

In `tests/test_brd_exporter.py`, add:

```python
def test_component_has_value():
    board = _make_board()
    board.footprints[0] = Footprint(
        ref="U1", footprint_lib="Package_SO:SOIC-8",
        x_mm=10, y_mm=10, rotation=0, side="top",
        pads=[], value="AMS1117-3.3"
    )
    analysis = analyze_board(board)
    export = export_board(board, analysis)
    u1 = next(c for c in export["components"] if c["ref"] == "U1")
    assert u1["value"] == "AMS1117-3.3"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_brd_exporter.py::test_component_has_value -v`
Expected: FAIL — Footprint doesn't accept `value` kwarg

**Step 3: Write minimal implementation**

In `kicad/models/board.py`, add `value` to Footprint:
```python
@dataclass
class Footprint:
    ref: str
    footprint_lib: str
    x_mm: float
    y_mm: float
    rotation: float
    side: str
    pads: list[Pad]
    value: str = ""
```

In `kicad/parsers/pcb_parser.py` `_parse_footprint()`, extract value from `fp_text`:
```python
    # After existing reference extraction
    if child[1] == "value" and len(child) > 2:
        value = str(child[2])
```
Add `value=value` to Footprint constructor.

In `kicad/exporters/brd_exporter.py`, add value to component export (after line 59):
```python
        if fp.value:
            entry["value"] = fp.value
```

In `tests/brd_export_schema.json`, add `"value": { "type": "string" }` to component properties.

**Step 4: Run tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add kicad/models/board.py kicad/parsers/pcb_parser.py kicad/exporters/brd_exporter.py tests/brd_export_schema.json tests/test_brd_exporter.py
git commit -m "feat: include component value in board export"
```

---

### Task 7: Document Flatpak /tmp limitation for kicad-cli methods

The MCP server and manual kicad-cli calls that write to `/tmp` fail under Flatpak because the sandbox can't access the host `/tmp`. This was already fixed for netlist export in `cli.py`, but `run_drc` and other methods also have this issue when callers pass `/tmp` paths.

**Files:**
- Modify: `kicad/kicad_cli.py` (add docstring warning)
- Modify: `kicad/mcp_server/server.py` (use project dir for temp files)

**Step 1: Review current MCP server temp file usage**

Read `kicad/mcp_server/server.py` and check if any tool writes to `/tmp`.

**Step 2: Update kicad_cli.py docstring**

Add class-level docstring:

```python
class KiCadCLI:
    """Wrapper around kicad-cli subprocess calls.

    NOTE: If KiCad is installed via Flatpak, output paths must be within
    the user's home directory. Flatpak sandboxes cannot write to /tmp.
    Callers should use project-relative paths or tempfile with a dir= argument.
    """
```

**Step 3: Fix MCP server temp file usage**

In `kicad/mcp_server/server.py`, ensure `export_kicad_project` uses project dir for temp files (same pattern as cli.py fix). Check if it currently uses `/tmp`.

**Step 4: Run tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS (no behavior change, just safer defaults)

**Step 5: Commit**

```bash
git add kicad/kicad_cli.py kicad/mcp_server/server.py
git commit -m "docs: warn about Flatpak /tmp limitation in kicad-cli wrapper"
```

---

## Verification

After all tasks, run the full export on the real design to confirm fixes:

```bash
uv run pytest tests/ -v
rm -rf benchmark/
uv run thomsonlint export /home/patrik/Desktop/smartLock/proto-dev-pcb/ --output ./benchmark/
uv run python -c "
import json
with open('benchmark/STM_PCB_schematic.json') as f:
    d = json.load(f)
print(f'Components: {len(d[\"components\"])}')
print(f'populate=true: {sum(1 for c in d[\"components\"] if c[\"populate\"])}')
print(f'populate=false: {sum(1 for c in d[\"components\"] if not c[\"populate\"])}')
print(f'Power nets: {d[\"analysis\"][\"power_nets\"]}')
print(f'+3.3V is power: {\"+3.3V\" in d[\"analysis\"][\"power_nets\"]}')
"
uv run python -c "
import json
with open('benchmark/STM_PCB_board.json') as f:
    d = json.load(f)
print(f'Layer count: {d[\"board\"][\"layer_count\"]}')  # Should be 4
print(f'Holes: {len(d[\"board\"][\"holes\"])}')
print(f'Decoupling entries: {len(d[\"analysis\"][\"decoupling_proximity\"])}')
# Check IC components are found
ic_refs = [c['ref'] for c in d['components'] if c['type'] == 'IC']
print(f'IC components: {ic_refs}')
conn_refs = [c['ref'] for c in d['components'] if c['type'] == 'connector']
print(f'Connector components: {conn_refs}')
"
```

**Expected results:**
- populate=true: 66 (all components, none are DNP)
- +3.3V in power_nets: True
- layer_count: 4
- IC components includes IC1, IC3, IC4, IC7, U1
- Connector components includes FP_conn1, Keypad_conn1, SC50_conn1, J2-J12
- Decoupling entries: significantly more than 2 (IC1, IC4, IC7, U1 all paired with caps)
