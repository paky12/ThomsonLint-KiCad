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


def test_layer_count_excludes_non_copper():
    """Unused copper layer slots (user type) should not be counted."""
    from kicad.parsers.pcb_parser import _parse_layers
    # Simulate a 4-layer board where KiCad defines 20+ layer slots
    nodes = [["layers",
        [0, "F.Cu", "signal"],
        [1, "In1.Cu", "signal"],
        [2, "In2.Cu", "power"],
        [31, "B.Cu", "mixed"],
        [32, "B.Adhes", "user"],
        [33, "F.Adhes", "user"],
        [34, "B.Paste", "user"],
        [36, "B.SilkS", "user"],
        [44, "Edge.Cuts", "user"],
        # Some KiCad files list unused inner copper layers as "user" type
        [3, "In3.Cu", "user"],
        [4, "In4.Cu", "user"],
        [5, "In5.Cu", "user"],
    ]]
    layers, count = _parse_layers(nodes)
    assert count == 4  # Only F.Cu, In1.Cu, In2.Cu, B.Cu are actual copper


def test_nets():
    board = parse_pcb(FIXTURE_PCB)
    assert len(board.nets) > 0
    assert 0 in board.nets


def test_mounting_holes_from_footprints(tmp_path):
    """Mounting holes are footprints with np_thru_hole pads."""
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
    board = parse_pcb(str(pcb_file))
    assert len(board.holes) >= 1
    hole = board.holes[0]
    assert abs(hole.x_mm - 10.0) < 0.01
    assert abs(hole.y_mm - 20.0) < 0.01
    assert abs(hole.drill_mm - 3.2) < 0.01
