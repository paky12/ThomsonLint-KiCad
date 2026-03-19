"""Parser for KiCad PCB files (.kicad_pcb)."""

import math
from kicad.parsers.sexpr import parse_sexpr_file
from kicad.models.board import (
    Board, BoardOutline, Layer, Footprint, Pad, TrackSegment, Via, Zone, Hole,
)


def _find_children(node: list, key: str) -> list[list]:
    """Return all direct child sub-lists whose first element equals key."""
    results = []
    for item in node:
        if isinstance(item, list) and item and item[0] == key:
            results.append(item)
    return results


def _find_child(node: list, key: str) -> list | None:
    """Return the first direct child sub-list whose first element equals key, or None."""
    for item in node:
        if isinstance(item, list) and item and item[0] == key:
            return item
    return None


def _get_value(node: list, key: str, index: int = 1, default=None):
    """Find a child node by key and return the element at index."""
    child = _find_child(node, key)
    if child is None:
        return default
    if index < len(child):
        return child[index]
    return default


def _parse_layers(nodes: list) -> tuple[list[Layer], int]:
    """Parse the (layers ...) node into Layer objects and copper layer count."""
    layers = []
    copper_count = 0
    layers_node = _find_child(nodes, "layers")
    if layers_node is None:
        return layers, 2

    for item in layers_node[1:]:
        if not isinstance(item, list):
            continue
        # Item format: (number "name" type) — already parsed as [num, name, type]
        # but item[0] is the layer number (int), not a keyword
        if len(item) < 3:
            continue
        num = item[0]
        name = item[1] if isinstance(item[1], str) else str(item[1])
        layer_type = item[2] if isinstance(item[2], str) else str(item[2])
        layers.append(Layer(number=int(num), name=name, type=layer_type))
        # Count copper layers by type (signal, power, or mixed)
        if layer_type in ("signal", "power", "mixed"):
            copper_count += 1

    return layers, max(copper_count, 2)


def _parse_nets(nodes: list) -> dict[int, str]:
    """Parse all (net N "name") nodes into a dict."""
    nets: dict[int, str] = {}
    for item in nodes:
        if isinstance(item, list) and item and item[0] == "net" and len(item) >= 3:
            # Guard: nets at top level have form [net, code, name]
            # Nested nets (inside pads) also have this form but we only want top-level ones
            try:
                code = int(item[1])
                name = item[2] if isinstance(item[2], str) else str(item[2])
                nets[code] = name
            except (ValueError, TypeError):
                pass
    return nets


def _rotate_point(x: float, y: float, angle_deg: float) -> tuple[float, float]:
    """Rotate (x, y) around origin by angle_deg degrees (KiCad CCW positive)."""
    if angle_deg == 0.0:
        return x, y
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    return x * cos_a - y * sin_a, x * sin_a + y * cos_a


def _parse_footprint(fp_node: list) -> Footprint:
    """Parse a (footprint ...) node into a Footprint dataclass."""
    lib_id = fp_node[1] if len(fp_node) > 1 and isinstance(fp_node[1], str) else ""

    # Position: (at x y [rotation])
    at_node = _find_child(fp_node, "at")
    fp_x = float(at_node[1]) if at_node and len(at_node) > 1 else 0.0
    fp_y = float(at_node[2]) if at_node and len(at_node) > 2 else 0.0
    fp_rot = float(at_node[3]) if at_node and len(at_node) > 3 else 0.0

    # Side
    layer_node = _find_child(fp_node, "layer")
    layer_name = layer_node[1] if layer_node and len(layer_node) > 1 else "F.Cu"
    side = "bottom" if "B.Cu" in str(layer_name) else "top"

    # Reference: search properties for "Reference"
    ref = ""
    for prop in _find_children(fp_node, "property"):
        if len(prop) > 1 and prop[1] == "Reference" and len(prop) > 2:
            ref = str(prop[2])
            break

    # Pads
    pads = []
    for pad_node in _find_children(fp_node, "pad"):
        pad = _parse_pad(pad_node, fp_x, fp_y, fp_rot)
        pads.append(pad)

    return Footprint(
        ref=ref,
        footprint_lib=lib_id,
        x_mm=fp_x,
        y_mm=fp_y,
        rotation=fp_rot,
        side=side,
        pads=pads,
    )


def _parse_pad(pad_node: list, fp_x: float, fp_y: float, fp_rot: float) -> Pad:
    """Parse a (pad ...) node into a Pad dataclass."""
    # pad format: (pad "number" type shape (at x y) (size ...) (layers ...) (net code name))
    pad_number = str(pad_node[1]) if len(pad_node) > 1 else ""
    pad_type = str(pad_node[2]) if len(pad_node) > 2 else ""

    at_node = _find_child(pad_node, "at")
    local_x = float(at_node[1]) if at_node and len(at_node) > 1 else 0.0
    local_y = float(at_node[2]) if at_node and len(at_node) > 2 else 0.0

    # Convert local pad coords to absolute using footprint rotation
    rot_x, rot_y = _rotate_point(local_x, local_y, fp_rot)
    abs_x = fp_x + rot_x
    abs_y = fp_y + rot_y

    # Net inside pad: (net code name)
    net_code = 0
    net_name = ""
    net_node = _find_child(pad_node, "net")
    if net_node and len(net_node) >= 3:
        try:
            net_code = int(net_node[1])
            net_name = str(net_node[2])
        except (ValueError, TypeError):
            pass

    return Pad(
        number=pad_number,
        type=pad_type,
        x_mm=abs_x,
        y_mm=abs_y,
        net_code=net_code,
        net_name=net_name,
    )


def _parse_segment(seg_node: list) -> TrackSegment:
    """Parse a (segment ...) node into a TrackSegment."""
    start_node = _find_child(seg_node, "start")
    end_node = _find_child(seg_node, "end")
    width_node = _find_child(seg_node, "width")
    layer_node = _find_child(seg_node, "layer")
    net_node = _find_child(seg_node, "net")

    return TrackSegment(
        layer=str(layer_node[1]) if layer_node and len(layer_node) > 1 else "",
        x1_mm=float(start_node[1]) if start_node and len(start_node) > 1 else 0.0,
        y1_mm=float(start_node[2]) if start_node and len(start_node) > 2 else 0.0,
        x2_mm=float(end_node[1]) if end_node and len(end_node) > 1 else 0.0,
        y2_mm=float(end_node[2]) if end_node and len(end_node) > 2 else 0.0,
        width_mm=float(width_node[1]) if width_node and len(width_node) > 1 else 0.0,
        net_code=int(net_node[1]) if net_node and len(net_node) > 1 else 0,
    )


def _parse_via(via_node: list) -> Via:
    """Parse a (via ...) node into a Via."""
    at_node = _find_child(via_node, "at")
    size_node = _find_child(via_node, "size")
    drill_node = _find_child(via_node, "drill")
    layers_node = _find_child(via_node, "layers")
    net_node = _find_child(via_node, "net")

    layer_from = "F.Cu"
    layer_to = "B.Cu"
    if layers_node and len(layers_node) >= 3:
        layer_from = str(layers_node[1])
        layer_to = str(layers_node[2])

    return Via(
        x_mm=float(at_node[1]) if at_node and len(at_node) > 1 else 0.0,
        y_mm=float(at_node[2]) if at_node and len(at_node) > 2 else 0.0,
        drill_mm=float(drill_node[1]) if drill_node and len(drill_node) > 1 else 0.0,
        net_code=int(net_node[1]) if net_node and len(net_node) > 1 else 0,
        layers=(layer_from, layer_to),
    )


def _parse_zone(zone_node: list) -> Zone:
    """Parse a (zone ...) node into a Zone."""
    net_name_node = _find_child(zone_node, "net_name")
    layer_node = _find_child(zone_node, "layer")
    connect_pads_node = _find_child(zone_node, "connect_pads")
    fill_node = _find_child(zone_node, "fill")

    net_name = str(net_name_node[1]) if net_name_node and len(net_name_node) > 1 else ""
    layer = str(layer_node[1]) if layer_node and len(layer_node) > 1 else ""

    clearance_mm = 0.0
    if connect_pads_node:
        clearance_node = _find_child(connect_pads_node, "clearance")
        if clearance_node and len(clearance_node) > 1:
            clearance_mm = float(clearance_node[1])

    thermal_relief = True
    if fill_node:
        # thermal_relief is present when there's a thermal_gap setting
        thermal_gap_node = _find_child(fill_node, "thermal_gap")
        thermal_relief = thermal_gap_node is not None

    return Zone(
        net_name=net_name,
        layer=layer,
        priority=0,
        thermal_relief=thermal_relief,
        clearance_mm=clearance_mm,
    )


def _parse_outline_from_gr_rect(nodes: list) -> BoardOutline | None:
    """Extract board outline from gr_rect on Edge.Cuts layer."""
    for item in nodes:
        if not (isinstance(item, list) and item and item[0] == "gr_rect"):
            continue
        layer_node = _find_child(item, "layer")
        if layer_node is None or (len(layer_node) > 1 and str(layer_node[1]) != "Edge.Cuts"):
            continue
        start_node = _find_child(item, "start")
        end_node = _find_child(item, "end")
        width_node = _find_child(item, "width")
        if start_node is None or end_node is None:
            continue
        x1 = float(start_node[1])
        y1 = float(start_node[2])
        x2 = float(end_node[1])
        y2 = float(end_node[2])
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        line_width = float(width_node[1]) if width_node and len(width_node) > 1 else 0.05
        vertices = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        return BoardOutline(vertices=vertices, width_mm=width, height_mm=height)
    return None


def _parse_outline_from_gr_lines(nodes: list) -> BoardOutline | None:
    """Extract board outline from gr_line elements on Edge.Cuts layer."""
    edge_lines = []
    for item in nodes:
        if not (isinstance(item, list) and item and item[0] == "gr_line"):
            continue
        layer_node = _find_child(item, "layer")
        if layer_node is None or str(layer_node[1]) != "Edge.Cuts":
            continue
        start_node = _find_child(item, "start")
        end_node = _find_child(item, "end")
        if start_node and end_node:
            edge_lines.append((
                float(start_node[1]), float(start_node[2]),
                float(end_node[1]), float(end_node[2]),
            ))

    if not edge_lines:
        return None

    all_x = [p[0] for p in edge_lines] + [p[2] for p in edge_lines]
    all_y = [p[1] for p in edge_lines] + [p[3] for p in edge_lines]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    width = max_x - min_x
    height = max_y - min_y
    vertices = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
    return BoardOutline(vertices=vertices, width_mm=width, height_mm=height)


def parse_pcb(file_path: str) -> Board:
    """Parse a .kicad_pcb file and return a Board model."""
    raw = parse_sexpr_file(file_path)
    # raw is the inner content of the top-level (kicad_pcb ...) list
    # first element is the keyword "kicad_pcb", rest are children
    if not raw or raw[0] != "kicad_pcb":
        raise ValueError(f"Not a valid kicad_pcb file: {file_path}")

    nodes = raw[1:]  # strip the "kicad_pcb" keyword

    # Layers
    layers, layer_count = _parse_layers(nodes)

    # Nets — only top-level net nodes (not pad-nested nets)
    nets: dict[int, str] = {}
    for item in nodes:
        if isinstance(item, list) and item and item[0] == "net" and len(item) >= 3:
            try:
                code = int(item[1])
                name = item[2] if isinstance(item[2], str) else str(item[2])
                nets[code] = name
            except (ValueError, TypeError):
                pass

    # Footprints
    footprints = [_parse_footprint(fp) for fp in _find_children(nodes, "footprint")]

    # Tracks
    tracks = [_parse_segment(seg) for seg in _find_children(nodes, "segment")]

    # Vias
    vias = [_parse_via(v) for v in _find_children(nodes, "via")]

    # Zones
    zones = [_parse_zone(z) for z in _find_children(nodes, "zone")]

    # Standalone holes (np_thru_hole pads at top level, if any)
    holes: list[Hole] = []
    for item in nodes:
        if isinstance(item, list) and item and item[0] == "pad":
            if len(item) > 2 and item[2] == "np_thru_hole":
                at_node = _find_child(item, "at")
                drill_node = _find_child(item, "drill")
                if at_node:
                    holes.append(Hole(
                        x_mm=float(at_node[1]) if len(at_node) > 1 else 0.0,
                        y_mm=float(at_node[2]) if len(at_node) > 2 else 0.0,
                        drill_mm=float(drill_node[1]) if drill_node and len(drill_node) > 1 else 0.0,
                    ))

    # Board outline: prefer gr_rect, fall back to gr_lines
    outline = _parse_outline_from_gr_rect(nodes)
    if outline is None:
        outline = _parse_outline_from_gr_lines(nodes)
    if outline is None:
        outline = BoardOutline()

    return Board(
        outline=outline,
        layers=layers,
        layer_count=layer_count,
        footprints=footprints,
        tracks=tracks,
        vias=vias,
        zones=zones,
        holes=holes,
        nets=nets,
    )
