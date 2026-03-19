"""Parse kicad-cli netlist XML export into Net objects and pin direction maps."""

import xml.etree.ElementTree as ET
from kicad.models.schematic import Net


def parse_netlist_xml(file_path: str) -> list[Net]:
    nets, _ = parse_netlist_xml_with_directions(file_path)
    return nets


def parse_netlist_xml_with_directions(file_path: str) -> tuple[list[Net], dict[tuple[str, str], str]]:
    tree = ET.parse(file_path)
    root = tree.getroot()

    nets = []
    pin_dirs: dict[tuple[str, str], str] = {}

    nets_elem = root.find("nets")
    if nets_elem is None:
        return nets, pin_dirs

    for net_elem in nets_elem.findall("net"):
        code = int(net_elem.get("code", "0"))
        name = net_elem.get("name", "")

        pins = []
        for node in net_elem.findall("node"):
            ref = node.get("ref", "")
            pin = node.get("pin", "")
            pintype = node.get("pintype", "passive")
            pins.append((ref, pin))
            pin_dirs[(ref, pin)] = pintype

        nets.append(Net(name=name, code=code, pins=pins))

    return nets, pin_dirs
