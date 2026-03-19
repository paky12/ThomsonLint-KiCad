import os
from kicad.parsers.netlist_parser import parse_netlist_xml
from kicad.models.schematic import Net

SAMPLE_NETLIST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<export version="E">
  <components>
    <comp ref="U1">
      <value>STM32F407</value>
      <footprint>QFP-64</footprint>
    </comp>
    <comp ref="C1">
      <value>100nF</value>
      <footprint>C_0402</footprint>
    </comp>
  </components>
  <nets>
    <net code="1" name="VCC">
      <node ref="U1" pin="1" pinfunction="VCC" pintype="power_in"/>
      <node ref="C1" pin="1" pinfunction="1" pintype="passive"/>
    </net>
    <net code="2" name="GND">
      <node ref="U1" pin="2" pinfunction="GND" pintype="power_in"/>
      <node ref="C1" pin="2" pinfunction="2" pintype="passive"/>
    </net>
    <net code="3" name="SPI_SCLK">
      <node ref="U1" pin="3" pinfunction="SCLK" pintype="output"/>
    </net>
  </nets>
</export>
"""

def test_parse_netlist_returns_nets(tmp_path):
    xml_file = tmp_path / "netlist.xml"
    xml_file.write_text(SAMPLE_NETLIST_XML)
    nets = parse_netlist_xml(str(xml_file))
    assert len(nets) == 3

def test_net_names(tmp_path):
    xml_file = tmp_path / "netlist.xml"
    xml_file.write_text(SAMPLE_NETLIST_XML)
    nets = parse_netlist_xml(str(xml_file))
    names = [n.name for n in nets]
    assert "VCC" in names
    assert "GND" in names
    assert "SPI_SCLK" in names

def test_net_pins(tmp_path):
    xml_file = tmp_path / "netlist.xml"
    xml_file.write_text(SAMPLE_NETLIST_XML)
    nets = parse_netlist_xml(str(xml_file))
    vcc = next(n for n in nets if n.name == "VCC")
    assert ("U1", "1") in vcc.pins
    assert ("C1", "1") in vcc.pins

def test_net_codes(tmp_path):
    xml_file = tmp_path / "netlist.xml"
    xml_file.write_text(SAMPLE_NETLIST_XML)
    nets = parse_netlist_xml(str(xml_file))
    vcc = next(n for n in nets if n.name == "VCC")
    assert vcc.code == 1

def test_pin_directions_extracted(tmp_path):
    from kicad.parsers.netlist_parser import parse_netlist_xml_with_directions
    xml_file = tmp_path / "netlist.xml"
    xml_file.write_text(SAMPLE_NETLIST_XML)
    nets, pin_dirs = parse_netlist_xml_with_directions(str(xml_file))
    assert pin_dirs[("U1", "1")] == "power_in"
    assert pin_dirs[("C1", "1")] == "passive"
    assert pin_dirs[("U1", "3")] == "output"
