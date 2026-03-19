import math
from kicad.models.board import Board, BoardOutline, Footprint, Pad, TrackSegment, Via, Zone, Layer
from kicad.analyzers.brd_analyzer import analyze_board

def _make_board():
    outline = BoardOutline(vertices=[(0, 0), (50, 0), (50, 40), (0, 40)], width_mm=50.0, height_mm=40.0)
    footprints = [
        Footprint(ref="U1", x_mm=25.0, y_mm=20.0, pads=[
            Pad(number="1", type="smd", x_mm=24.5, y_mm=20.0, net_code=1, net_name="VCC"),
            Pad(number="2", type="smd", x_mm=25.5, y_mm=20.0, net_code=2, net_name="GND"),
        ]),
        Footprint(ref="C1", x_mm=27.0, y_mm=20.0, pads=[
            Pad(number="1", type="smd", x_mm=26.5, y_mm=20.0, net_code=1, net_name="VCC"),
            Pad(number="2", type="smd", x_mm=27.5, y_mm=20.0, net_code=2, net_name="GND"),
        ]),
        Footprint(ref="J1", x_mm=1.0, y_mm=20.0, pads=[
            Pad(number="1", type="thru_hole", x_mm=1.0, y_mm=20.0, net_code=3, net_name="DATA"),
        ]),
    ]
    tracks = [
        TrackSegment(layer="F.Cu", x1_mm=24.5, y1_mm=20.0, x2_mm=26.5, y2_mm=20.0, width_mm=0.25, net_code=1),
        TrackSegment(layer="F.Cu", x1_mm=26.5, y1_mm=20.0, x2_mm=30.0, y2_mm=20.0, width_mm=0.20, net_code=1),
    ]
    vias = [Via(x_mm=30.0, y_mm=20.0, drill_mm=0.3, net_code=1), Via(x_mm=25.0, y_mm=25.0, drill_mm=0.3, net_code=2)]
    zones = [Zone(net_name="GND", layer="B.Cu", priority=0, thermal_relief=True, clearance_mm=0.3)]
    return Board(outline=outline, layers=[Layer(0, "F.Cu", "signal"), Layer(31, "B.Cu", "signal")],
                 layer_count=2, footprints=footprints, tracks=tracks, vias=vias, zones=zones,
                 nets={0: "", 1: "VCC", 2: "GND", 3: "DATA"})

def test_trace_length():
    result = analyze_board(_make_board())
    net1 = next(s for s in result["signals"] if s["name"] == "VCC")
    assert abs(net1["trace_length_mm"] - 5.5) < 0.01

def test_via_count():
    result = analyze_board(_make_board())
    net1 = next(s for s in result["signals"] if s["name"] == "VCC")
    assert net1["via_count"] == 1

def test_min_max_width():
    result = analyze_board(_make_board())
    net1 = next(s for s in result["signals"] if s["name"] == "VCC")
    assert net1["min_width_mm"] == 0.20
    assert net1["max_width_mm"] == 0.25

def test_edge_distance():
    result = analyze_board(_make_board())
    edge_comps = result["component_edge_distances"]
    j1 = next((c for c in edge_comps if c["ref"] == "J1"), None)
    assert j1 is not None
    assert j1["min_distance_mm"] < 3.0

def test_decoupling_proximity():
    result = analyze_board(_make_board())
    decoup = result["decoupling_proximity"]
    assert len(decoup) > 0
    entry = decoup[0]
    assert entry["ic_ref"] == "U1"
    assert entry["cap_ref"] == "C1"
    assert entry["distance_mm"] > 0

def test_ground_plane_layers():
    result = analyze_board(_make_board())
    assert "B.Cu" in result["ground_plane_layers"]
