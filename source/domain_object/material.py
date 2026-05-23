from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class BaseMaterial:
    name: str
    category: str
    unit_price: float
    chemical_content: Dict[str, float]
    moisture: float
    burning_loss: float


@dataclass
class BlendMaterialParam:
    row_index: int
    name: str
    ratio_bounds: Tuple[float, float]
    unit_price: float
    chemical_content: Dict[str, float]
    moisture: float
    burning_loss: float


@dataclass
class BurdenMaterialParam:
    row_index: int
    selected: int
    category: str
    name: str
    ratio_bounds: Tuple[float, float]
    external_unit_price: float = 0.0
    external_chemical_content: Dict[str, float] = field(default_factory=dict)


@dataclass
class FuelParam:
    row_index: int
    name: str
    integrated_ratio: float
    unit_price: float
    chemical_content: Dict[str, float]
    dry_unit_consumption: float = 0.0
    gross_dry_unit_consumption: float = 0.0
    return_fines: float = 0.0
