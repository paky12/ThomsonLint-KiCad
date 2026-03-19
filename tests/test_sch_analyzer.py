from kicad.models.schematic import Component, Net, Pin, Schematic
from kicad.analyzers.sch_analyzer import analyze_schematic

def _make_schematic():
    components = [
        Component(ref="U1", value="MCU", footprint="QFP-64", pins=[
            Pin(name="VCC", number="1", direction="power_in"),
            Pin(name="GND", number="2", direction="power_in"),
            Pin(name="DATA_IN", number="3", direction="input"),
            Pin(name="DATA_OUT", number="4", direction="output"),
        ]),
        Component(ref="C1", value="100nF", footprint="C_0402", pins=[
            Pin(name="1", number="1", direction="passive"),
            Pin(name="2", number="2", direction="passive"),
        ]),
        Component(ref="J1", value="USB-C", footprint="USB_C", pins=[
            Pin(name="D+", number="1", direction="bidirectional"),
            Pin(name="D-", number="2", direction="bidirectional"),
        ]),
    ]
    nets = [
        Net(name="VCC", code=1, pins=[("U1", "1"), ("C1", "1")]),
        Net(name="GND", code=2, pins=[("U1", "2"), ("C1", "2")]),
        Net(name="USB_D_P", code=3, pins=[("U1", "4"), ("J1", "1")]),
        Net(name="USB_D_N", code=4, pins=[("J1", "2")]),
        Net(name="FLOATING_IN", code=5, pins=[("U1", "3")]),
        Net(name="SPI_SCLK", code=6, pins=[("U1", "4")]),
    ]
    return Schematic(components=components, nets=nets, sheets=[])

def test_power_nets():
    result = analyze_schematic(_make_schematic())
    assert "VCC" in result["power_nets"]

def test_ground_nets():
    result = analyze_schematic(_make_schematic())
    assert "GND" in result["ground_nets"]

def test_clock_nets():
    result = analyze_schematic(_make_schematic())
    assert "SPI_SCLK" in result["clock_nets"]

def test_differential_pairs():
    result = analyze_schematic(_make_schematic())
    pairs = result["differential_pairs"]
    assert len(pairs) >= 1
    pair = pairs[0]
    assert pair["positive"] == "USB_D_P"
    assert pair["negative"] == "USB_D_N"
    assert pair["interface"] == "USB"

def test_floating_inputs():
    result = analyze_schematic(_make_schematic())
    floating = result["floating_inputs"]
    parts = [f["part"] for f in floating]
    assert "U1" in parts

def test_single_pin_nets():
    result = analyze_schematic(_make_schematic())
    assert "USB_D_N" in result["single_pin_nets"]
