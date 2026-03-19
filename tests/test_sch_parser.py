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
