import logging
import os
from typing import Dict, List, Tuple, Optional

from . import domain_object as do
from .utils import enums, field
from .utils.xlsx import WorkbookReader


BASE_MATERIAL_SHEETS = [
    field.SHEET_SINTER_ORE,
    field.SHEET_SINTER_RECYCLE,
    field.SHEET_SINTER_ADDITIVE,
    field.SHEET_SINTER_FUEL,
    field.SHEET_SINTER_PRODUCT,
    field.SHEET_PELLET_PRODUCT,
    field.SHEET_LUMP_ORE,
    field.SHEET_COKE,
    field.SHEET_COAL,
]

MIXING_BASE_SHEETS = [
    field.SHEET_SINTER_ORE,
    field.SHEET_SINTER_RECYCLE,
    field.SHEET_SINTER_ADDITIVE,
    field.SHEET_SINTER_FUEL,
]

BURDEN_BASE_SHEETS = [
    field.SHEET_SINTER_PRODUCT,
    field.SHEET_PELLET_PRODUCT,
    field.SHEET_LUMP_ORE,
]


class InputData:
    def __init__(self, exe_folder: str = "./", excel_filename: str = field.EXCEL_FILENAME):
        self.exe_folder = exe_folder
        self.excel_filename = excel_filename
        self.excel_path = os.path.join(exe_folder, field.DATA_DIR, excel_filename)
        self.workbook = WorkbookReader(self.excel_path)

        self.base_material_dict: Dict[str, do.BaseMaterial] = {}
        self.base_material_by_sheet: Dict[str, Dict[str, do.BaseMaterial]] = {}
        self.sinter_ore_names = set()

        self.sinter_rows: List[int] = []
        self.pellet_rows: List[int] = []
        self.burden_rows: List[int] = []
        self.coke_rows: List[int] = []
        self.coal_rows: List[int] = []

        self.sinter_params: Dict[int, do.BlendMaterialParam] = {}
        self.pellet_params: Dict[int, do.BlendMaterialParam] = {}
        self.burden_params: Dict[int, do.BurdenMaterialParam] = {}
        self.coke_params: Dict[int, do.FuelParam] = {}
        self.coal_params: Dict[int, do.FuelParam] = {}

        self.param_dict: Dict[str, float] = {}
        self.drop_rate_sinter: Dict[str, float] = {}
        self.drop_rate_pellet: Dict[str, float] = {}
        self.atomic_ratio: Dict[str, float] = {}
        self.hot_metal_distribution: Dict[str, float] = {}
        self.slag_distribution: Dict[str, float] = {}

        self.sinter_composition_bounds: Dict[str, do.BoundItem] = {}
        self.sinter_indicator_bounds: Dict[str, do.BoundItem] = {}
        self.pellet_composition_bounds: Dict[str, do.BoundItem] = {}
        self.hot_metal_bounds: Dict[str, do.BoundItem] = {}
        self.slag_composition_bounds: Dict[str, do.BoundItem] = {}
        self.slag_alkalinity_bounds: Dict[str, do.BoundItem] = {}
        self.harmful_load_bounds: Dict[str, do.BoundItem] = {}
        self.process_cost = do.ProcessCost(0.0, 0.0, 0.0)

    def read_data(self):
        self.load_direct_parameters()
        self.calculate_indirect_parameters()

    def load_direct_parameters(self):
        self.load_base_materials()
        self.load_decision_rows()
        self.load_param_dict()
        self.load_conversion_parameters()
        self.load_bounds()
        self.load_process_costs()

    def load_base_materials(self):
        for sheet in BASE_MATERIAL_SHEETS:
            sheet_materials = {}
            for row in self.workbook.iter_rows(sheet, min_row=2):
                name = self.workbook.value(sheet, row, 1, default=None)
                if name is None or name == "":
                    continue
                content = {
                    comp: self.workbook.numeric_value(sheet, row, 3 + idx)
                    for idx, comp in enumerate(enums.COMPONENTS)
                }
                material = do.BaseMaterial(
                    name=str(name),
                    category=sheet,
                    unit_price=self.workbook.numeric_value(sheet, row, 2),
                    chemical_content=content,
                    moisture=self.workbook.numeric_value(sheet, row, 21),
                    burning_loss=self.workbook.numeric_value(sheet, row, 22),
                )
                sheet_materials[material.name] = material
                self.base_material_dict[material.name] = material
            self.base_material_by_sheet[sheet] = sheet_materials
        self.sinter_ore_names = set(self.base_material_by_sheet[field.SHEET_SINTER_ORE])
        logging.info("loaded base materials: %s", len(self.base_material_dict))

    def load_decision_rows(self):
        self.sinter_rows = self._nonempty_rows(field.SHEET_INTEGRATED_SINTER, 1)
        self.pellet_rows = self._nonempty_rows(field.SHEET_INTEGRATED_PELLET, 1)
        self.burden_rows = self._nonempty_rows(field.SHEET_BF_BURDEN, 3)
        self.coke_rows = self._nonempty_rows(field.SHEET_BF_COKE, 1)
        self.coal_rows = self._nonempty_rows(field.SHEET_BF_COAL, 1)
        logging.info(
            "decision rows: sinter=%s pellet=%s burden=%s coke=%s coal=%s",
            len(self.sinter_rows), len(self.pellet_rows), len(self.burden_rows),
            len(self.coke_rows), len(self.coal_rows),
        )

    def _nonempty_rows(self, sheet: str, name_col: int) -> List[int]:
        rows = []
        for row in self.workbook.iter_rows(sheet, min_row=2):
            name = self.workbook.value(sheet, row, name_col, default=None)
            if name is not None and name != "":
                rows.append(row)
        return rows

    def load_param_dict(self):
        for row in self.workbook.iter_rows(field.SHEET_PARAM, min_row=2):
            name = self.workbook.value(field.SHEET_PARAM, row, 1, default=None)
            if not name:
                continue
            self.param_dict[str(name)] = self.workbook.numeric_value(field.SHEET_PARAM, row, 2)
        logging.info("loaded parameter settings: %s", len(self.param_dict))

    def load_conversion_parameters(self):
        for row in self.workbook.iter_rows(field.SHEET_DROP_RATE, min_row=2):
            name = self.workbook.value(field.SHEET_DROP_RATE, row, 1, default=None)
            if not name:
                continue
            self.drop_rate_sinter[str(name)] = self.workbook.numeric_value(field.SHEET_DROP_RATE, row, 2)
            self.drop_rate_pellet[str(name)] = self.workbook.numeric_value(field.SHEET_DROP_RATE, row, 3)

        for row in self.workbook.iter_rows(field.SHEET_ATOMIC_RATIO, min_row=2):
            name = self.workbook.value(field.SHEET_ATOMIC_RATIO, row, 1, default=None)
            if name:
                self.atomic_ratio[str(name)] = self.workbook.numeric_value(field.SHEET_ATOMIC_RATIO, row, 2)

        for row in self.workbook.iter_rows(field.SHEET_DISTRIBUTION, min_row=2):
            name = self.workbook.value(field.SHEET_DISTRIBUTION, row, 1, default=None)
            if not name:
                continue
            self.hot_metal_distribution[str(name)] = self.workbook.numeric_value(field.SHEET_DISTRIBUTION, row, 2)
            self.slag_distribution[str(name)] = self.workbook.numeric_value(field.SHEET_DISTRIBUTION, row, 3)
        logging.info("loaded conversion parameters")

    def load_bounds(self):
        self.sinter_composition_bounds = self._load_bound_sheet(field.SHEET_SINTER_COMPOSITION)
        self.sinter_indicator_bounds = self._load_bound_sheet(field.SHEET_SINTER_INDICATOR)
        self.pellet_composition_bounds = self._load_bound_sheet(field.SHEET_PELLET_COMPOSITION)
        self.hot_metal_bounds = self._load_bound_sheet(field.SHEET_HOT_METAL_COMPOSITION)
        self.slag_composition_bounds = self._load_bound_sheet(field.SHEET_SLAG_COMPOSITION)
        self.slag_alkalinity_bounds = self._load_bound_sheet(field.SHEET_SLAG_ALKALINITY)
        self.harmful_load_bounds = self._load_bound_sheet(field.SHEET_HARMFUL_LOAD)
        logging.info("loaded bounds")

    def _load_bound_sheet(self, sheet: str) -> Dict[str, do.BoundItem]:
        result = {}
        for row in self.workbook.iter_rows(sheet, min_row=2):
            name = self.workbook.value(sheet, row, 2, default=None)
            if not name:
                continue
            result[str(name)] = do.BoundItem(
                row_index=row,
                name=str(name),
                selected=int(self.workbook.numeric_value(sheet, row, 1)),
                bounds=(
                    self.workbook.numeric_value(sheet, row, 3),
                    self.workbook.numeric_value(sheet, row, 4),
                ),
            )
        return result

    def load_process_costs(self):
        self.process_cost = do.ProcessCost(
            sinter=self.workbook.numeric_value(field.SHEET_SINTER_PROCESS_COST, 27, 4),
            pellet=self.workbook.numeric_value(field.SHEET_PELLET_PROCESS_COST, 24, 4),
            blast_furnace=self.workbook.numeric_value(field.SHEET_BF_PROCESS_COST, 35, 4),
        )
        logging.info("process cost: %s", self.process_cost)

    def calculate_indirect_parameters(self):
        self.sinter_params = self._calculate_blend_params(field.SHEET_INTEGRATED_SINTER, self.sinter_rows)
        self.pellet_params = self._calculate_blend_params(field.SHEET_INTEGRATED_PELLET, self.pellet_rows)
        self.burden_params = self._calculate_burden_params()
        self.coke_params = self._calculate_fuel_params(
            sheet=field.SHEET_BF_COKE,
            rows=self.coke_rows,
            base_sheet=field.SHEET_COKE,
            total_key="一体化焦比",
            has_return_fines=True,
        )
        self.coal_params = self._calculate_fuel_params(
            sheet=field.SHEET_BF_COAL,
            rows=self.coal_rows,
            base_sheet=field.SHEET_COAL,
            total_key="一体化煤比",
            has_return_fines=False,
        )
        logging.info("calculated indirect parameters")

    def _calculate_blend_params(self, sheet: str, rows: List[int]) -> Dict[int, do.BlendMaterialParam]:
        result = {}
        for row in rows:
            name = str(self.workbook.value(sheet, row, 1))
            material = self.find_material(name, MIXING_BASE_SHEETS)
            if material is None:
                logging.warning("%s row %s material not found: %s", sheet, row, name)
                unit_price = 0.0
                content = {comp: 0.0 for comp in enums.COMPONENTS}
                moisture = 0.0
                burning_loss = 0.0
            else:
                unit_price = material.unit_price
                content = material.chemical_content.copy()
                moisture = material.moisture
                burning_loss = material.burning_loss
            result[row] = do.BlendMaterialParam(
                row_index=row,
                name=name,
                ratio_bounds=(
                    self.workbook.numeric_value(sheet, row, 2),
                    self.workbook.numeric_value(sheet, row, 3),
                ),
                unit_price=unit_price,
                chemical_content=content,
                moisture=moisture,
                burning_loss=burning_loss,
            )
        return result

    def _calculate_burden_params(self) -> Dict[int, do.BurdenMaterialParam]:
        result = {}
        for row in self.burden_rows:
            name = str(self.workbook.value(field.SHEET_BF_BURDEN, row, 3))
            category = str(self.workbook.value(field.SHEET_BF_BURDEN, row, 2, default=""))
            material = self.find_material(name, BURDEN_BASE_SHEETS)
            result[row] = do.BurdenMaterialParam(
                row_index=row,
                selected=int(self.workbook.numeric_value(field.SHEET_BF_BURDEN, row, 1)),
                category=category,
                name=name,
                ratio_bounds=(
                    self.workbook.numeric_value(field.SHEET_BF_BURDEN, row, 4),
                    self.workbook.numeric_value(field.SHEET_BF_BURDEN, row, 5),
                ),
                external_unit_price=material.unit_price if material else 0.0,
                external_chemical_content=material.chemical_content.copy() if material else {comp: 0.0 for comp in enums.COMPONENTS},
            )
        return result

    def _calculate_fuel_params(self, sheet: str, rows: List[int], base_sheet: str, total_key: str, has_return_fines: bool) -> Dict[int, do.FuelParam]:
        result = {}
        total = self.param_dict[total_key]
        return_rate = self.param_dict.get("焦炭返粉率", 0.0)
        for row in rows:
            name = str(self.workbook.value(sheet, row, 1))
            material = self.find_material(name, [base_sheet])
            ratio = self.workbook.numeric_value(sheet, row, 3)
            dry_unit = total / 1000 * ratio / 100
            if has_return_fines:
                gross = dry_unit / (1 - return_rate / 100)
                ret = dry_unit - gross
            else:
                gross = 0.0
                ret = 0.0
            result[row] = do.FuelParam(
                row_index=row,
                name=name,
                integrated_ratio=ratio,
                unit_price=material.unit_price if material else 0.0,
                chemical_content=material.chemical_content.copy() if material else {comp: 0.0 for comp in enums.COMPONENTS},
                dry_unit_consumption=dry_unit,
                gross_dry_unit_consumption=gross,
                return_fines=ret,
            )
        return result

    def find_material(self, name: str, sheets: List[str]) -> Optional[do.BaseMaterial]:
        for sheet in sheets:
            material = self.base_material_by_sheet.get(sheet, {}).get(name)
            if material is not None:
                return material
        return None
