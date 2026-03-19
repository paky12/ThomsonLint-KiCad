"""Parser for KiCad schematic files (.kicad_sch)."""

import os
from kicad.models.schematic import Component, Pin, Net, Sheet, Schematic
from kicad.parsers.sexpr import parse_sexpr_file


def parse_schematic(file_path: str) -> Schematic:
    """Parse a .kicad_sch file into a Schematic dataclass.
    Recursively parses hierarchical sub-sheets.
    Does NOT resolve net connectivity — that comes from kicad-cli netlist export.
    """
    components = []
    sheets = []
    _parse_sch_recursive(file_path, components, sheets)
    return Schematic(components=components, nets=[], sheets=sheets)


def _parse_sch_recursive(file_path: str, components: list, sheets: list):
    tree = parse_sexpr_file(file_path)
    base_dir = os.path.dirname(os.path.abspath(file_path))

    for node in tree:
        if not isinstance(node, list) or not node:
            continue

        if node[0] == "symbol":
            comp = _parse_symbol(node)
            if comp is not None:
                components.append(comp)

        elif node[0] == "sheet":
            sheet = _parse_sheet(node)
            if sheet is not None:
                sheets.append(sheet)
                sub_path = os.path.join(base_dir, sheet.file_path)
                if os.path.exists(sub_path):
                    _parse_sch_recursive(sub_path, components, sheets)


def _parse_symbol(node: list) -> Component | None:
    props = {}
    pins = []
    lib_id = ""
    is_dnp = False

    for child in node[1:]:
        if not isinstance(child, list) or not child:
            continue

        if child[0] == "lib_id" and len(child) > 1:
            lib_id = str(child[1])

        elif child[0] == "property" and len(child) >= 3:
            prop_name = str(child[1])
            prop_value = str(child[2])
            props[prop_name] = prop_value

        elif child[0] == "pin" and len(child) >= 2:
            pin = Pin(
                name=str(child[1]) if len(child) > 1 else "",
                number=str(child[1]),
                direction="passive",
                electrical_type="",
            )
            pins.append(pin)

        elif child[0] == "dnp":
            # KiCad 9: (dnp yes) = do not populate, (dnp no) = populate
            # KiCad 8: bare (dnp) = do not populate
            is_dnp = len(child) < 2 or str(child[1]).lower() != "no"

    ref = props.get("Reference", "")
    if not ref or ref.startswith("#"):
        return None

    populate = not is_dnp
    if props.get("DNP", "").upper() in ("YES", "TRUE", "1", "DNP"):
        populate = False

    return Component(
        ref=ref,
        value=props.get("Value", ""),
        footprint=props.get("Footprint", ""),
        description=props.get("Description", ""),
        populate=populate,
        properties={k: v for k, v in props.items()
                    if k not in ("Reference", "Value", "Footprint", "Description")},
        pins=pins,
    )


def _parse_sheet(node: list) -> Sheet | None:
    name = ""
    file_path = ""
    instances = []

    for child in node[1:]:
        if not isinstance(child, list) or not child:
            continue
        if child[0] == "property" and len(child) >= 3:
            prop_name = str(child[1])
            if prop_name == "Sheetname":
                name = str(child[2])
            elif prop_name == "Sheetfile":
                file_path = str(child[2])
        elif child[0] == "instances":
            for inst in child[1:]:
                if isinstance(inst, list) and inst and inst[0] == "project":
                    for path_node in inst[1:]:
                        if isinstance(path_node, list) and path_node and path_node[0] == "path":
                            if len(path_node) > 1:
                                instances.append(str(path_node[1]))

    if not file_path:
        return None
    return Sheet(name=name, file_path=file_path, instances=instances)
