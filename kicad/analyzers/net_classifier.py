"""Signal and component classification matching ThomsonLint's Fusion ULP logic."""

from dataclasses import dataclass


@dataclass
class NetClassification:
    is_power: bool = False
    is_ground: bool = False
    is_clock: bool = False
    is_differential: bool = False
    diff_polarity: int = 0
    diff_pair_partner: str | None = None
    voltage_guess: str | None = None
    interface_guess: str = "unknown"


def classify_net(name: str) -> NetClassification:
    upper = name.upper()
    result = NetClassification()

    power_patterns = [
        "VCC", "VDD", "VBUS", "VIN", "VOUT", "VBAT", "VSYS", "VREF",
        "+3V", "+5V", "+12V", "+24V", "3V3", "3.3V", "5V0", "1V8", "1V2", "2V5", "PWR",
    ]
    for p in power_patterns:
        if p in upper:
            result.is_power = True
            break

    ground_exact = {"GND", "AGND", "DGND", "PGND", "SGND"}
    if upper in ground_exact or "VSS" in upper or "GND" in upper:
        result.is_ground = True

    clock_patterns = ["CLK", "XTAL", "SCK", "SCLK", "MCLK", "BCLK", "LRCK", "OSC"]
    for p in clock_patterns:
        if p in upper:
            result.is_clock = True
            break

    result.diff_polarity, result.diff_pair_partner = _detect_diff_pair(name)
    result.is_differential = result.diff_polarity != 0

    result.voltage_guess = _guess_voltage(upper)

    if result.is_differential:
        result.interface_guess = _guess_interface(upper)

    return result


def _detect_diff_pair(name: str) -> tuple[int, str | None]:
    length = len(name)
    if length < 2:
        return 0, None

    if length >= 3:
        last3 = name[-3:]
        ul3 = last3.upper()
        base = name[:-3]
        if ul3 == "_DP":
            return 1, base + "_DN"
        if ul3 == "_DN":
            return -1, base + "_DP"

    last2 = name[-2:]
    ul2 = last2.upper()
    base = name[:-2]
    if ul2 == "_P":
        return 1, base + "_N"
    if ul2 == "_N":
        return -1, base + "_P"
    if ul2 == "DP":
        return 1, base + "DN"
    if ul2 == "DN":
        return -1, base + "DP"
    if ul2 == "D+":
        return 1, base + "D-"
    if ul2 == "D-":
        return -1, base + "D+"

    return 0, None


def _guess_voltage(upper: str) -> str | None:
    if "3V3" in upper or "3.3" in upper or "+3V3" in upper:
        return "3.3V"
    if "5V0" in upper or "+5V" in upper or "5V" in upper:
        return "5V"
    if "1V8" in upper or "1.8" in upper:
        return "1.8V"
    if "1V2" in upper or "1.2" in upper:
        return "1.2V"
    if "2V5" in upper or "2.5" in upper:
        return "2.5V"
    if "12V" in upper:
        return "12V"
    if "24V" in upper:
        return "24V"
    if "VBUS" in upper:
        return "5V"
    if "VBAT" in upper:
        return "3.7V"
    return None


def _guess_interface(upper: str) -> str:
    if "USB" in upper:
        return "USB"
    if "ETH" in upper or "MDIO" in upper:
        return "Ethernet"
    if "HDMI" in upper:
        return "HDMI"
    if "LVDS" in upper:
        return "LVDS"
    if "CAN" in upper:
        return "CAN"
    if "RS485" in upper or "RS-485" in upper:
        return "RS-485"
    if "PCIE" in upper or "PCI" in upper:
        return "PCIe"
    if "SATA" in upper:
        return "SATA"
    if "MIPI" in upper:
        return "MIPI"
    return "unknown"


_MULTI_CHAR_PREFIXES = [
    ("FB", "ferrite_bead"),
    ("TP", "test_point"),
    ("SW", "switch"),
    ("BT", "battery"),
]

_SINGLE_CHAR_PREFIXES = {
    "U": "IC", "C": "capacitor", "R": "resistor", "L": "inductor",
    "Q": "transistor", "J": "connector", "X": "crystal", "Y": "crystal",
    "F": "fuse", "T": "transformer", "K": "relay",
}


def classify_component(ref: str, description: str = "") -> str:
    if not ref:
        return "unknown"

    for prefix, comp_type in _MULTI_CHAR_PREFIXES:
        if ref.upper().startswith(prefix):
            return comp_type

    first = ref[0].upper()

    if first == "D":
        upper_desc = description.upper()
        if "LED" in upper_desc:
            return "LED"
        if "TVS" in upper_desc or "ESD" in upper_desc:
            return "TVS"
        if "ZENER" in upper_desc:
            return "zener"
        return "diode"

    return _SINGLE_CHAR_PREFIXES.get(first, "other")
