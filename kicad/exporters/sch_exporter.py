"""Schematic export: converts Schematic + analysis dict to a JSON-serialisable dict."""
from datetime import datetime, timezone

from kicad.models.schematic import Schematic
from kicad.analyzers.net_classifier import classify_net, classify_component

_DIRECTION_MAP: dict[str, str] = {
    "input": "IN",
    "output": "OUT",
    "bidirectional": "IO",
    "passive": "PAS",
    "power_in": "PWR",
    "power_out": "SUP",
    "open_collector": "OC",
    "tri_state": "HIZ",
    "no_connect": "NC",
}

_VERSION = "1.0"


def export_schematic(sch: Schematic, analysis: dict, project_name: str, variant: str = "") -> dict:
    """Return a dict that validates against sch_export_schema.json."""

    # Build a pin-direction lookup: (comp_ref, pin_number) -> direction
    pin_dir: dict[tuple[str, str], str] = {}
    for comp in sch.components:
        for pin in comp.pins:
            pin_dir[(comp.ref, pin.number)] = pin.direction

    # ── components ──────────────────────────────────────────────────────────
    components_out = []
    for comp in sch.components:
        comp_type = classify_component(comp.ref, comp.description)
        entry: dict = {
            "ref": comp.ref,
            "value": comp.value,
            "package": comp.footprint,
            "populate": comp.populate,
            "type": comp_type,
        }
        if comp.description:
            entry["description"] = comp.description
        if comp.properties:
            entry["attributes"] = comp.properties
        components_out.append(entry)

    # ── nets ─────────────────────────────────────────────────────────────────
    nets_out = []
    for net in sch.nets:
        cl = classify_net(net.name)
        pins_out = []
        for comp_ref, pin_num in net.pins:
            raw_dir = pin_dir.get((comp_ref, pin_num), "passive")
            mapped = _DIRECTION_MAP.get(raw_dir, raw_dir.upper())
            pins_out.append({"part": comp_ref, "pin": pin_num, "direction": mapped})

        net_entry: dict = {
            "name": net.name,
            "is_power": cl.is_power,
            "is_ground": cl.is_ground,
            "is_clock": cl.is_clock,
            "is_differential": cl.is_differential,
            "diff_pair_partner": cl.diff_pair_partner,
            "voltage_guess": cl.voltage_guess,
            "pins": pins_out,
        }
        nets_out.append(net_entry)

    # ── project block ────────────────────────────────────────────────────────
    project_block: dict = {
        "name": project_name,
        "sheets": len(sch.sheets),
    }
    if variant:
        project_block["variant"] = variant

    return {
        "thomsonlint_version": _VERSION,
        "export_date": datetime.now(timezone.utc).isoformat(),
        "mode": "schematic",
        "project": project_block,
        "components": components_out,
        "nets": nets_out,
        "analysis": analysis,
    }
