from dataclasses import dataclass
from typing import Tuple


@dataclass
class BoundItem:
    row_index: int
    name: str
    selected: int
    bounds: Tuple[float, float]


@dataclass
class ProcessCost:
    sinter: float
    pellet: float
    blast_furnace: float
