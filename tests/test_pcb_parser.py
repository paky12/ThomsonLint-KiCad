import os
from kicad.parsers.pcb_parser import parse_pcb
from kicad.models.board import Board

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
FIXTURE_PCB = os.path.join(FIXTURE_DIR, "test_project.kicad_pcb")


def test_returns_board():
    board = parse_pcb(FIXTURE_PCB)
    assert isinstance(board, Board)


def test_finds_footprints():
    board = parse_pcb(FIXTURE_PCB)
    refs = [fp.ref for fp in board.footprints]
    assert "C1" in refs
    assert "U1" in refs


def test_footprint_position():
    board = parse_pcb(FIXTURE_PCB)
    c1 = next(fp for fp in board.footprints if fp.ref == "C1")
    assert c1.x_mm != 0.0 or c1.y_mm != 0.0


def test_footprint_pads():
    board = parse_pcb(FIXTURE_PCB)
    c1 = next(fp for fp in board.footprints if fp.ref == "C1")
    assert len(c1.pads) > 0
    assert c1.pads[0].net_name != ""


def test_finds_tracks():
    board = parse_pcb(FIXTURE_PCB)
    assert len(board.tracks) > 0
    assert board.tracks[0].width_mm > 0


def test_finds_vias():
    board = parse_pcb(FIXTURE_PCB)
    assert len(board.vias) > 0
    assert board.vias[0].drill_mm > 0


def test_finds_zones():
    board = parse_pcb(FIXTURE_PCB)
    assert len(board.zones) > 0


def test_board_outline():
    board = parse_pcb(FIXTURE_PCB)
    assert board.outline.width_mm > 0
    assert board.outline.height_mm > 0


def test_layers():
    board = parse_pcb(FIXTURE_PCB)
    assert board.layer_count >= 2
    layer_names = [l.name for l in board.layers]
    assert "F.Cu" in layer_names
    assert "B.Cu" in layer_names


def test_nets():
    board = parse_pcb(FIXTURE_PCB)
    assert len(board.nets) > 0
    assert 0 in board.nets
