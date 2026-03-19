import json, jsonschema, os
from kicad.models.board import Board, BoardOutline, Footprint, Pad, TrackSegment, Via, Zone, Layer
from kicad.analyzers.brd_analyzer import analyze_board
from kicad.exporters.brd_exporter import export_board

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "brd_export_schema.json")

def _make_board():
    outline = BoardOutline(vertices=[(0,0),(50,0),(50,40),(0,40)], width_mm=50.0, height_mm=40.0)
    return Board(outline=outline, layers=[Layer(0,"F.Cu","signal"),Layer(31,"B.Cu","signal")], layer_count=2,
        footprints=[
            Footprint(ref="U1", x_mm=25.0, y_mm=20.0, pads=[Pad(number="1", type="smd", x_mm=24.5, y_mm=20.0, net_code=1, net_name="VCC")]),
            Footprint(ref="C1", x_mm=27.0, y_mm=20.0, pads=[Pad(number="1", type="smd", x_mm=26.5, y_mm=20.0, net_code=1, net_name="VCC")]),
        ],
        tracks=[TrackSegment(layer="F.Cu", x1_mm=24.5, y1_mm=20.0, x2_mm=26.5, y2_mm=20.0, width_mm=0.25, net_code=1)],
        vias=[Via(x_mm=30.0, y_mm=20.0, drill_mm=0.3, net_code=1)],
        zones=[Zone(net_name="GND", layer="B.Cu")],
        nets={0: "", 1: "VCC", 2: "GND"})

def test_export_validates_against_schema():
    board = _make_board()
    analysis = analyze_board(board)
    result = export_board(board, analysis)
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    jsonschema.validate(instance=result, schema=schema)

def test_export_structure():
    board = _make_board()
    analysis = analyze_board(board)
    result = export_board(board, analysis)
    assert result["thomsonlint_version"] == "1.0"
    assert result["mode"] == "board"
    assert len(result["components"]) == 2
    assert result["board"]["layer_count"] == 2
    assert result["board"]["area"]["width_mm"] == 50.0

def test_component_has_value():
    board = _make_board()
    # Set value on first footprint
    board.footprints[0].value = "AMS1117-3.3"
    analysis = analyze_board(board)
    export = export_board(board, analysis)
    u1 = next(c for c in export["components"] if c["ref"] == "U1")
    assert u1["value"] == "AMS1117-3.3"

def test_trace_segments_conditional():
    board = _make_board()
    analysis = analyze_board(board)
    result = export_board(board, analysis)
    vcc_signal = next(s for s in result["signals"] if s["name"] == "VCC")
    assert "trace_segments" not in vcc_signal
