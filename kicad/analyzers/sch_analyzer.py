"""Schematic-level analysis: floating inputs, diff pairs, net classification."""
from kicad.models.schematic import Schematic
from kicad.analyzers.net_classifier import classify_net

_DRIVER_DIRECTIONS = {"output", "bidirectional", "power_out", "tri_state"}
_POWER_DIRECTIONS = {"power_in", "power_out"}

def analyze_schematic(sch: Schematic) -> dict:
    pin_dir = {}
    pin_names = {}
    for comp in sch.components:
        for pin in comp.pins:
            pin_dir[(comp.ref, pin.number)] = pin.direction
            pin_names[(comp.ref, pin.number)] = pin.name

    power_nets, ground_nets, clock_nets = [], [], []
    diff_pairs_found = {}
    floating_inputs, single_pin_nets = [], []

    for net in sch.nets:
        cl = classify_net(net.name)
        if cl.is_power: power_nets.append(net.name)
        if cl.is_ground: ground_nets.append(net.name)
        if cl.is_clock: clock_nets.append(net.name)

        if cl.is_differential and cl.diff_pair_partner and cl.diff_polarity == 1:
            base = net.name[:-2] if len(net.name) >= 2 else net.name
            diff_pairs_found[base] = {"positive": net.name, "negative": cl.diff_pair_partner, "interface": cl.interface_guess}

        if len(net.pins) == 1:
            single_pin_nets.append(net.name)

        if cl.is_power or cl.is_ground:
            continue

        has_driver = False
        input_pins = []
        for comp_ref, pin_num in net.pins:
            direction = pin_dir.get((comp_ref, pin_num), "passive")
            if direction in _DRIVER_DIRECTIONS or direction in _POWER_DIRECTIONS:
                has_driver = True
            if direction == "input":
                pin_name = pin_names.get((comp_ref, pin_num), pin_num)
                input_pins.append({"part": comp_ref, "pin": pin_name})

        if not has_driver and input_pins:
            floating_inputs.extend(input_pins)

    return {"power_nets": power_nets, "ground_nets": ground_nets, "clock_nets": clock_nets,
            "differential_pairs": list(diff_pairs_found.values()), "floating_inputs": floating_inputs, "single_pin_nets": single_pin_nets}
