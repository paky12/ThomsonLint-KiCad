"""Board-level analysis: trace stats, decoupling proximity, edge distances, ground planes."""
import math
from kicad.models.board import Board
from kicad.analyzers.net_classifier import classify_net, classify_component


def _point_to_segment_dist(px: float, py: float,
                            ax: float, ay: float,
                            bx: float, by: float) -> float:
    """Minimum distance from point (px,py) to line segment (ax,ay)-(bx,by)."""
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _compute_signal_stats(board: Board) -> list[dict]:
    """Per-net trace length, via count, width range."""
    net_length: dict[int, float] = {}
    net_via_count: dict[int, int] = {}
    net_min_width: dict[int, float] = {}
    net_max_width: dict[int, float] = {}
    net_segments: dict[int, list] = {}

    for track in board.tracks:
        nc = track.net_code
        seg_len = math.hypot(track.x2_mm - track.x1_mm, track.y2_mm - track.y1_mm)
        net_length[nc] = net_length.get(nc, 0.0) + seg_len
        if nc not in net_min_width or track.width_mm < net_min_width[nc]:
            net_min_width[nc] = track.width_mm
        if nc not in net_max_width or track.width_mm > net_max_width[nc]:
            net_max_width[nc] = track.width_mm
        net_segments.setdefault(nc, []).append(track)

    for via in board.vias:
        nc = via.net_code
        net_via_count[nc] = net_via_count.get(nc, 0) + 1

    results = []
    all_net_codes = set(net_length.keys()) | set(net_via_count.keys())
    for nc in all_net_codes:
        net_name = board.nets.get(nc, "")
        if not net_name:
            continue
        entry = {
            "name": net_name,
            "net_code": nc,
            "trace_length_mm": round(net_length.get(nc, 0.0), 6),
            "via_count": net_via_count.get(nc, 0),
            "min_width_mm": net_min_width.get(nc, 0.0),
            "max_width_mm": net_max_width.get(nc, 0.0),
        }
        # Include trace segments for high-speed nets (differential or clock)
        cl = classify_net(net_name)
        if cl.is_differential or cl.is_clock:
            entry["trace_segments"] = net_segments.get(nc, [])
        results.append(entry)
    return results


def _compute_edge_distances(board: Board) -> list[dict]:
    """Components within 3mm of board edge."""
    vertices = board.outline.vertices
    if len(vertices) < 2:
        return []

    # Build edge segments from outline vertices (closed polygon)
    edges = []
    n = len(vertices)
    for i in range(n):
        edges.append((vertices[i], vertices[(i + 1) % n]))

    results = []
    for fp in board.footprints:
        px, py = fp.x_mm, fp.y_mm
        min_dist = min(
            _point_to_segment_dist(px, py, ax, ay, bx, by)
            for (ax, ay), (bx, by) in edges
        )
        results.append({"ref": fp.ref, "min_distance_mm": round(min_dist, 6)})
    return results


def _compute_decoupling_proximity(board: Board) -> list[dict]:
    """IC pad to nearest capacitor pad distance on each power net."""
    # Group pads by net_code
    net_ic_pads: dict[int, list[tuple[str, float, float]]] = {}
    net_cap_pads: dict[int, list[tuple[str, float, float]]] = {}

    for fp in board.footprints:
        comp_type = classify_component(fp.ref)
        for pad in fp.pads:
            nc = pad.net_code
            if nc == 0:
                continue
            net_name = board.nets.get(nc, "")
            cl = classify_net(net_name)
            if not (cl.is_power or cl.is_ground):
                continue
            if comp_type == "IC":
                net_ic_pads.setdefault(nc, []).append((fp.ref, pad.x_mm, pad.y_mm))
            elif comp_type == "capacitor":
                net_cap_pads.setdefault(nc, []).append((fp.ref, pad.x_mm, pad.y_mm))

    results = []
    seen_pairs: set[tuple[str, str, int]] = set()
    for nc, ic_pads in net_ic_pads.items():
        if nc not in net_cap_pads:
            continue
        cap_pads = net_cap_pads[nc]
        for ic_ref, ix, iy in ic_pads:
            best_dist = None
            best_cap_ref = None
            for cap_ref, cx, cy in cap_pads:
                d = math.hypot(cx - ix, cy - iy)
                if best_dist is None or d < best_dist:
                    best_dist = d
                    best_cap_ref = cap_ref
            if best_cap_ref is not None:
                pair_key = (ic_ref, best_cap_ref, nc)
                if pair_key not in seen_pairs:
                    seen_pairs.add(pair_key)
                    results.append({
                        "ic_ref": ic_ref,
                        "cap_ref": best_cap_ref,
                        "net_code": nc,
                        "net_name": board.nets.get(nc, ""),
                        "distance_mm": round(best_dist, 6),
                    })
    return results


def _compute_ground_plane_layers(board: Board) -> list[str]:
    """Zone layers associated with ground nets."""
    layers = []
    for zone in board.zones:
        cl = classify_net(zone.net_name)
        if cl.is_ground and zone.layer not in layers:
            layers.append(zone.layer)
    return layers


def analyze_board(board: Board) -> dict:
    return {
        "signals": _compute_signal_stats(board),
        "component_edge_distances": _compute_edge_distances(board),
        "decoupling_proximity": _compute_decoupling_proximity(board),
        "ground_plane_layers": _compute_ground_plane_layers(board),
    }
