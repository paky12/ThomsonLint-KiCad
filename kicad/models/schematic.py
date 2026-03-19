from dataclasses import dataclass, field


@dataclass
class Pin:
    name: str
    number: str
    direction: str  # input, output, bidirectional, passive, power_in, power_out, open_collector, tri_state, no_connect
    electrical_type: str = ""


@dataclass
class Component:
    ref: str
    value: str
    footprint: str
    description: str = ""
    populate: bool = True
    properties: dict = field(default_factory=dict)
    pins: list[Pin] = field(default_factory=list)


@dataclass
class Net:
    name: str
    code: int = 0
    pins: list[tuple[str, str]] = field(default_factory=list)  # (component_ref, pin_number)


@dataclass
class Sheet:
    name: str
    file_path: str  # relative path to sub-sheet .kicad_sch
    instances: list[str] = field(default_factory=list)


@dataclass
class Schematic:
    components: list[Component] = field(default_factory=list)
    nets: list[Net] = field(default_factory=list)
    sheets: list[Sheet] = field(default_factory=list)
