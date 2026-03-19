import json, jsonschema, os
from kicad.models.schematic import Component, Net, Pin, Schematic
from kicad.analyzers.sch_analyzer import analyze_schematic
from kicad.exporters.sch_exporter import export_schematic

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "sch_export_schema.json")

def _make_schematic():
    components = [
        Component(ref="U1", value="STM32", footprint="QFP-64", pins=[
            Pin(name="VCC", number="1", direction="power_in"),
            Pin(name="DATA", number="2", direction="input"),
        ]),
        Component(ref="C1", value="100nF", footprint="C_0402", pins=[
            Pin(name="1", number="1", direction="passive"),
            Pin(name="2", number="2", direction="passive"),
        ]),
    ]
    nets = [
        Net(name="VCC", code=1, pins=[("U1", "1"), ("C1", "1")]),
        Net(name="GND", code=2, pins=[("U1", "2"), ("C1", "2")]),
    ]
    return Schematic(components=components, nets=nets, sheets=[])

def test_export_validates_against_schema():
    sch = _make_schematic()
    analysis = analyze_schematic(sch)
    result = export_schematic(sch, analysis, project_name="test_project")
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    jsonschema.validate(instance=result, schema=schema)

def test_export_structure():
    sch = _make_schematic()
    analysis = analyze_schematic(sch)
    result = export_schematic(sch, analysis, project_name="test_project")
    assert result["thomsonlint_version"] == "1.0"
    assert result["mode"] == "schematic"
    assert result["project"]["name"] == "test_project"
    assert len(result["components"]) == 2
    assert len(result["nets"]) == 2

def test_pin_direction_mapping():
    sch = _make_schematic()
    analysis = analyze_schematic(sch)
    result = export_schematic(sch, analysis, project_name="test")
    vcc_net = next(n for n in result["nets"] if n["name"] == "VCC")
    u1_pin = next(p for p in vcc_net["pins"] if p["part"] == "U1")
    assert u1_pin["direction"] == "PWR"
    c1_pin = next(p for p in vcc_net["pins"] if p["part"] == "C1")
    assert c1_pin["direction"] == "PAS"

def test_component_type_classification():
    sch = _make_schematic()
    analysis = analyze_schematic(sch)
    result = export_schematic(sch, analysis, project_name="test")
    u1 = next(c for c in result["components"] if c["ref"] == "U1")
    assert u1["type"] == "IC"
    c1 = next(c for c in result["components"] if c["ref"] == "C1")
    assert c1["type"] == "capacitor"
