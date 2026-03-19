"""Board export: converts Board + analysis dict to a JSON-serialisable dict."""
from datetime import datetime, timezone

from kicad.models.board import Board, TrackSegment
from kicad.analyzers.net_classifier import classify_component

_VERSION = "1.0"


def _layer_name_to_number(name: str, layers: list) -> int | str:
    """Convert a layer name to its number for ULP compatibility.

    Falls back to the original name string if no match is found.
    """
    for layer in layers:
        if layer.name == name:
            return layer.number
    return name


def _serialise_signal(sig: dict) -> dict:
    """Return a JSON-safe copy of a signal dict from the analyzer.

    TrackSegment objects inside 'trace_segments' are converted to plain dicts.
    """
    out = {k: v for k, v in sig.items() if k != "trace_segments"}
    if "trace_segments" in sig:
        segments = []
        for seg in sig["trace_segments"]:
            if isinstance(seg, TrackSegment):
                segments.append({
                    "layer": seg.layer,
                    "x1_mm": seg.x1_mm,
                    "y1_mm": seg.y1_mm,
                    "x2_mm": seg.x2_mm,
                    "y2_mm": seg.y2_mm,
                    "width_mm": seg.width_mm,
                    "net_code": seg.net_code,
                })
            else:
                segments.append(seg)
        out["trace_segments"] = segments
    return out


def export_board(board: Board, analysis: dict) -> dict:
    """Return a dict that validates against brd_export_schema.json."""

    # ── components ──────────────────────────────────────────────────────────
    components_out = []
    for fp in board.footprints:
        comp_type = classify_component(fp.ref)
        entry: dict = {
            "ref": fp.ref,
            "x_mm": fp.x_mm,
            "y_mm": fp.y_mm,
            "rotation": fp.rotation,
            "side": fp.side,
            "type": comp_type,
        }
        if fp.footprint_lib:
            entry["footprint"] = fp.footprint_lib
        components_out.append(entry)

    # ── board block ──────────────────────────────────────────────────────────
    layers_used = [layer.name for layer in board.layers]

    holes_out = [
        {"x_mm": h.x_mm, "y_mm": h.y_mm, "drill_mm": h.drill_mm}
        for h in board.holes
    ]

    polygons_out = []
    for zone in board.zones:
        layer_val = _layer_name_to_number(zone.layer, board.layers)
        polygons_out.append({
            "net_name": zone.net_name,
            "layer": layer_val,
        })

    board_block: dict = {
        "area": {
            "width_mm": board.outline.width_mm,
            "height_mm": board.outline.height_mm,
        },
        "layers_used": layers_used,
        "layer_count": board.layer_count,
        "holes": holes_out,
        "polygons": polygons_out,
    }

    # ── signals ──────────────────────────────────────────────────────────────
    signals_out = [_serialise_signal(sig) for sig in analysis.get("signals", [])]

    # ── analysis block ───────────────────────────────────────────────────────
    analysis_block: dict = {
        "component_edge_distances": analysis.get("component_edge_distances", []),
        "decoupling_proximity": analysis.get("decoupling_proximity", []),
        "ground_plane_layers": analysis.get("ground_plane_layers", []),
    }

    return {
        "thomsonlint_version": _VERSION,
        "export_date": datetime.now(timezone.utc).isoformat(),
        "mode": "board",
        "components": components_out,
        "board": board_block,
        "signals": signals_out,
        "analysis": analysis_block,
    }
