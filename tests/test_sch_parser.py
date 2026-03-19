import os
from kicad.parsers.sch_parser import parse_schematic
from kicad.models.schematic import Schematic

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
FIXTURE_SCH = os.path.join(FIXTURE_DIR, "test_project.kicad_sch")


def test_returns_schematic():
    sch = parse_schematic(FIXTURE_SCH)
    assert isinstance(sch, Schematic)


def test_finds_components():
    sch = parse_schematic(FIXTURE_SCH)
    refs = [c.ref for c in sch.components]
    assert "U1" in refs
    assert "C1" in refs
    assert "R1" in refs
    assert "J1" in refs


def test_component_fields():
    sch = parse_schematic(FIXTURE_SCH)
    u1 = next(c for c in sch.components if c.ref == "U1")
    assert u1.value != ""
    assert u1.footprint != ""


def test_component_pins():
    sch = parse_schematic(FIXTURE_SCH)
    u1 = next(c for c in sch.components if c.ref == "U1")
    assert len(u1.pins) > 0


def test_dnp_component():
    sch = parse_schematic(FIXTURE_SCH)
    dnp = [c for c in sch.components if not c.populate]
    for c in dnp:
        assert c.populate is False


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
    sch = parse_schematic(str(sch_file))
    comps = {c.ref: c for c in sch.components}
    assert comps["R1"].populate is True   # dnp no → populate
    assert comps["R2"].populate is False  # dnp yes → do not populate
