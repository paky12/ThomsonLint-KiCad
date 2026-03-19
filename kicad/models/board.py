from dataclasses import dataclass, field


@dataclass
class Pad:
    number: str
    type: str  # smd, thru_hole, np_thru_hole
    x_mm: float = 0.0
    y_mm: float = 0.0
    net_code: int = 0
    net_name: str = ""


@dataclass
class Footprint:
    ref: str
    footprint_lib: str = ""
    x_mm: float = 0.0
    y_mm: float = 0.0
    rotation: float = 0.0
    side: str = "top"  # "top" or "bottom"
    pads: list[Pad] = field(default_factory=list)


@dataclass
class TrackSegment:
    layer: str = ""
    x1_mm: float = 0.0
    y1_mm: float = 0.0
    x2_mm: float = 0.0
    y2_mm: float = 0.0
    width_mm: float = 0.0
    net_code: int = 0


@dataclass
class Via:
    x_mm: float = 0.0
    y_mm: float = 0.0
    drill_mm: float = 0.0
    net_code: int = 0
    layers: tuple[str, str] = ("F.Cu", "B.Cu")


@dataclass
class Zone:
    net_name: str = ""
    layer: str = ""
    priority: int = 0
    thermal_relief: bool = True
    clearance_mm: float = 0.0


@dataclass
class BoardOutline:
    vertices: list[tuple[float, float]] = field(default_factory=list)
    width_mm: float = 0.0
    height_mm: float = 0.0


@dataclass
class Layer:
    number: int = 0
    name: str = ""
    type: str = ""  # signal, power, mixed, user


@dataclass
class Hole:
    """Standalone board hole (mounting, mechanical) — NOT signal vias."""
    x_mm: float = 0.0
    y_mm: float = 0.0
    drill_mm: float = 0.0


@dataclass
class Board:
    outline: BoardOutline = field(default_factory=BoardOutline)
    layers: list[Layer] = field(default_factory=list)
    layer_count: int = 2
    footprints: list[Footprint] = field(default_factory=list)
    tracks: list[TrackSegment] = field(default_factory=list)
    vias: list[Via] = field(default_factory=list)
    zones: list[Zone] = field(default_factory=list)
    holes: list[Hole] = field(default_factory=list)  # standalone mechanical holes
    nets: dict[int, str] = field(default_factory=dict)  # net_code → net_name
