import logging
from typing import Dict, Tuple

from .input_data import InputData
from .utils import enums, field


class VariableData:
    def __init__(self, input_data: InputData):
        self.input_data = input_data
        self.workbook = input_data.workbook

        self.sinter_ratio: Dict[int, float] = {}
        self.pellet_ratio: Dict[int, float] = {}
        self.burden_ratio: Dict[int, float] = {}

        self.sinter_dry_basis: Dict[int, float] = {}
        self.sinter_burn_save: Dict[int, float] = {}
        self.pellet_dry_basis: Dict[int, float] = {}
        self.pellet_burn_save: Dict[int, float] = {}

        self.sinter_composition: Dict[str, float] = {}
        self.sinter_indicator: Dict[str, float] = {}
        self.pellet_composition: Dict[str, float] = {}
        self.sinter_unit_cost = 0.0
        self.pellet_unit_cost = 0.0

        self.burden_unit_price: Dict[int, float] = {}
        self.burden_content: Dict[Tuple[int, str], float] = {}
        self.hot_metal_grade = 0.0
        self.burden_dry_unit: Dict[int, float] = {}
        self.burden_gross_dry_unit: Dict[int, float] = {}
        self.burden_return_price: Dict[int, float] = {}
        self.burden_return_fines: Dict[int, float] = {}

        self.in_furnace_content: Dict[str, float] = {}
        self.hot_metal_composition: Dict[str, float] = {}
        self.slag_amount: Dict[str, float] = {}
        self.slag_composition: Dict[str, float] = {}
        self.slag_alkalinity: Dict[str, float] = {}
        self.harmful_load: Dict[str, float] = {}
        self.hot_metal_cost = 0.0

        self.compare_total = 0
        self.compare_failed = 0

    def read_variables(self):
        self.sinter_ratio = {
            row: self.workbook.numeric_value(field.SHEET_INTEGRATED_SINTER, row, 5)
            for row in self.input_data.sinter_rows
        }
        self.pellet_ratio = {
            row: self.workbook.numeric_value(field.SHEET_INTEGRATED_PELLET, row, 5)
            for row in self.input_data.pellet_rows
        }
        self.burden_ratio = {
            row: self.workbook.numeric_value(field.SHEET_BF_BURDEN, row, 7)
            for row in self.input_data.burden_rows
        }
        logging.info(
            "read variables: sum_sinter=%.12g sum_pellet=%.12g sum_burden=%.12g",
            sum(self.sinter_ratio.values()),
            sum(self.pellet_ratio.values()),
            sum(self.burden_ratio.values()),
        )

    def calculate_auxiliary_variables(self):
        self._calculate_sinter_auxiliary()
        self._calculate_pellet_auxiliary()
        self._calculate_burden_auxiliary()
        self._calculate_hot_metal_slag_load_auxiliary()
        self._calculate_hot_metal_cost()

    def _calculate_sinter_auxiliary(self):
        for row, ratio in self.sinter_ratio.items():
            param = self.input_data.sinter_params[row]
            dry = ratio * (1 - param.moisture / 100)
            burn = dry * (1 - param.burning_loss / 100)
            self.sinter_dry_basis[row] = dry
            self.sinter_burn_save[row] = burn
        denominator = sum(self.sinter_burn_save.values())
        for comp in enums.PRODUCT_COMPONENTS:
            numerator = sum(
                self.sinter_dry_basis[row] * self.input_data.sinter_params[row].chemical_content[comp]
                for row in self.sinter_ratio
            )
            self.sinter_composition[comp] = self._safe_div(numerator, denominator) * (1 - self.input_data.drop_rate_sinter[comp] / 100)
        self.sinter_indicator = {
            "CaO/SiO2": self._safe_div(self.sinter_composition["CaO"], self.sinter_composition["SiO2"]),
            "Al2O3/SiO2": self._safe_div(self.sinter_composition["Al2O3"], self.sinter_composition["SiO2"]),
            "MgO/Al2O3": self._safe_div(self.sinter_composition["MgO"], self.sinter_composition["Al2O3"]),
        }
        numerator_cost = sum(
            self.input_data.sinter_params[row].unit_price * self.sinter_dry_basis[row]
            for row in self.sinter_ratio
        )
        self.sinter_unit_cost = self._safe_div(numerator_cost, denominator) + self.input_data.process_cost.sinter

    def _calculate_pellet_auxiliary(self):
        for row, ratio in self.pellet_ratio.items():
            param = self.input_data.pellet_params[row]
            dry = ratio * (1 - param.moisture / 100)
            burn = dry * (1 - param.burning_loss / 100)
            self.pellet_dry_basis[row] = dry
            self.pellet_burn_save[row] = burn
        denominator = sum(self.pellet_burn_save.values())
        for comp in enums.PRODUCT_COMPONENTS:
            numerator = sum(
                self.pellet_dry_basis[row] * self.input_data.pellet_params[row].chemical_content[comp]
                for row in self.pellet_ratio
            )
            self.pellet_composition[comp] = self._safe_div(numerator, denominator) * (1 - self.input_data.drop_rate_pellet[comp] / 100)
        numerator_cost = sum(
            self.input_data.pellet_params[row].unit_price * self.pellet_dry_basis[row]
            for row in self.pellet_ratio
        )
        self.pellet_unit_cost = self._safe_div(numerator_cost, denominator) + self.input_data.process_cost.pellet

    def _calculate_burden_auxiliary(self):
        for row in self.input_data.burden_rows:
            param = self.input_data.burden_params[row]
            if param.name == enums.INTEGRATED_SINTER_NAME:
                self.burden_unit_price[row] = self.sinter_unit_cost
                for comp in enums.PRODUCT_COMPONENTS:
                    self.burden_content[row, comp] = self.sinter_composition[comp]
            elif param.name == enums.INTEGRATED_PELLET_NAME:
                self.burden_unit_price[row] = self.pellet_unit_cost
                for comp in enums.PRODUCT_COMPONENTS:
                    self.burden_content[row, comp] = self.pellet_composition[comp]
            else:
                self.burden_unit_price[row] = param.external_unit_price
                for comp in enums.PRODUCT_COMPONENTS:
                    self.burden_content[row, comp] = param.external_chemical_content.get(comp, 0.0)

        self.hot_metal_grade = self._safe_div(
            sum(self.burden_ratio[row] * self.burden_content[row, "TFe"] for row in self.input_data.burden_rows),
            sum(self.burden_ratio.values()),
        )

        for row in self.input_data.burden_rows:
            param = self.input_data.burden_params[row]
            dry_unit = (self.input_data.param_dict["铁元素消耗"] / self.hot_metal_grade * 100) * self.burden_ratio[row] / 100
            self.burden_dry_unit[row] = dry_unit
            if param.category == enums.BURDEN_CATEGORY_SINTER:
                rate = self.input_data.param_dict["烧结返粉率"]
                return_price = self.input_data.param_dict["烧结返粉单价"]
            elif param.category == enums.BURDEN_CATEGORY_PELLET:
                rate = self.input_data.param_dict["球团返粉率"]
                return_price = self.input_data.param_dict["球团返粉单价"]
            elif param.category == enums.BURDEN_CATEGORY_LUMP:
                rate = self.input_data.param_dict["块矿返粉率"]
                return_price = self.input_data.param_dict["块矿返粉单价"]
            else:
                rate = 0.0
                return_price = 0.0
            gross = self._safe_div(dry_unit, 1 - rate / 100)
            self.burden_gross_dry_unit[row] = gross
            self.burden_return_price[row] = return_price
            self.burden_return_fines[row] = dry_unit - gross

    def _calculate_hot_metal_slag_load_auxiliary(self):
        for comp in enums.PRODUCT_COMPONENTS:
            burden_part = sum(
                self.burden_dry_unit[row] * self.burden_content[row, comp]
                for row in self.input_data.burden_rows
            )
            coke_part = sum(
                item.dry_unit_consumption * item.chemical_content.get(comp, 0.0)
                for item in self.input_data.coke_params.values()
            )
            coal_part = sum(
                item.dry_unit_consumption * item.chemical_content.get(comp, 0.0)
                for item in self.input_data.coal_params.values()
            )
            self.in_furnace_content[comp] = burden_part + coke_part + coal_part

        for hm_name, comp in enums.HOT_METAL_TO_COMPONENT.items():
            self.hot_metal_composition[hm_name] = (
                self.in_furnace_content[comp]
                * self.input_data.hot_metal_distribution[comp]
                / 100
                * self.input_data.atomic_ratio[comp]
                / 100
            )

        for comp in enums.PRODUCT_COMPONENTS:
            self.slag_amount[comp] = (
                self.in_furnace_content[comp]
                / 100
                * self.input_data.slag_distribution[comp]
                / 100
            )
        slag_total = sum(self.slag_amount.values())
        for comp in enums.PRODUCT_COMPONENTS:
            self.slag_composition[comp] = self._safe_div(self.slag_amount[comp], slag_total) * 100

        self.slag_alkalinity = {
            "镁铝比": self._safe_div(self.slag_composition["MgO"], self.slag_composition["Al2O3"]),
            "二元碱度": self._safe_div(self.slag_composition["CaO"], self.slag_composition["SiO2"]),
            "三元碱度": self._safe_div(self.slag_composition["CaO"] + self.slag_composition["MgO"], self.slag_composition["SiO2"]),
            "四元碱度": self._safe_div(
                self.slag_composition["CaO"] + self.slag_composition["MgO"],
                self.slag_composition["SiO2"] + self.slag_composition["Al2O3"],
            ),
        }
        self.harmful_load = {
            name: self.in_furnace_content[comp] / 100 * 1000
            for name, comp in enums.HARMFUL_LOAD_COMPONENT.items()
        }

    def _calculate_hot_metal_cost(self):
        burden_cost = sum(
            self.burden_unit_price[row] * self.burden_gross_dry_unit[row]
            for row in self.input_data.burden_rows
        )
        burden_return_cost = sum(
            self.burden_return_price[row] * self.burden_return_fines[row]
            for row in self.input_data.burden_rows
        )
        coke_cost = sum(
            item.unit_price * item.gross_dry_unit_consumption
            for item in self.input_data.coke_params.values()
        )
        coke_return_cost = self.input_data.param_dict["焦炭返粉单价"] * sum(
            item.return_fines for item in self.input_data.coke_params.values()
        )
        coal_cost = sum(
            item.unit_price * item.dry_unit_consumption
            for item in self.input_data.coal_params.values()
        )
        self.hot_metal_cost = (
            burden_cost
            + burden_return_cost
            + coke_cost
            + coke_return_cost
            + coal_cost
            + self.input_data.process_cost.blast_furnace
        )

    def validate_against_excel(self):
        logging.info("start validation against Excel cached values")
        self._compare_indirect_parameters()
        self._compare_auxiliary_variables()
        logging.info(
            "validation summary: total=%s failed=%s passed=%s",
            self.compare_total, self.compare_failed, self.compare_total - self.compare_failed,
        )
        if self.compare_failed:
            logging.warning("validation has %s mismatches", self.compare_failed)

    def _compare_indirect_parameters(self):
        for row, param in self.input_data.sinter_params.items():
            self._compare(f"param sinter row {row} unit_price", param.unit_price, field.SHEET_INTEGRATED_SINTER, row, 6)
            for idx, comp in enumerate(enums.COMPONENTS):
                self._compare(f"param sinter row {row} {comp}", param.chemical_content[comp], field.SHEET_INTEGRATED_SINTER, row, 7 + idx)
            self._compare(f"param sinter row {row} moisture", param.moisture, field.SHEET_INTEGRATED_SINTER, row, 25)
            self._compare(f"param sinter row {row} burning_loss", param.burning_loss, field.SHEET_INTEGRATED_SINTER, row, 26)
        for row, param in self.input_data.pellet_params.items():
            self._compare(f"param pellet row {row} unit_price", param.unit_price, field.SHEET_INTEGRATED_PELLET, row, 6)
            for idx, comp in enumerate(enums.COMPONENTS):
                self._compare(f"param pellet row {row} {comp}", param.chemical_content[comp], field.SHEET_INTEGRATED_PELLET, row, 7 + idx)
            self._compare(f"param pellet row {row} moisture", param.moisture, field.SHEET_INTEGRATED_PELLET, row, 25)
            self._compare(f"param pellet row {row} burning_loss", param.burning_loss, field.SHEET_INTEGRATED_PELLET, row, 26)
        for row, item in self.input_data.coke_params.items():
            self._compare(f"param coke row {row} dry_unit", item.dry_unit_consumption, field.SHEET_BF_COKE, row, 26)
            self._compare(f"param coke row {row} gross_dry_unit", item.gross_dry_unit_consumption, field.SHEET_BF_COKE, row, 28)
            self._compare(f"param coke row {row} return_fines", item.return_fines, field.SHEET_BF_COKE, row, 30)
        for row, item in self.input_data.coal_params.items():
            self._compare(f"param coal row {row} dry_unit", item.dry_unit_consumption, field.SHEET_BF_COAL, row, 26)

    def _compare_auxiliary_variables(self):
        for row in self.input_data.sinter_rows:
            self._compare(f"var sinter row {row} integrated_dry_basis", self.sinter_dry_basis[row], field.SHEET_INTEGRATED_SINTER, row, 28)
            self._compare(f"var sinter row {row} integrated_burn_save", self.sinter_burn_save[row], field.SHEET_INTEGRATED_SINTER, row, 30)
        for row in self.input_data.pellet_rows:
            self._compare(f"var pellet row {row} integrated_dry_basis", self.pellet_dry_basis[row], field.SHEET_INTEGRATED_PELLET, row, 28)
            self._compare(f"var pellet row {row} integrated_burn_save", self.pellet_burn_save[row], field.SHEET_INTEGRATED_PELLET, row, 30)

        for idx, comp in enumerate(enums.PRODUCT_COMPONENTS, start=2):
            self._compare(f"var sinter composition {comp}", self.sinter_composition[comp], field.SHEET_SINTER_COMPOSITION, idx, 6)
            self._compare(f"var pellet composition {comp}", self.pellet_composition[comp], field.SHEET_PELLET_COMPOSITION, idx, 6)
        for idx, name in enumerate(enums.SINTER_INDICATORS, start=2):
            self._compare(f"var sinter indicator {name}", self.sinter_indicator[name], field.SHEET_SINTER_INDICATOR, idx, 6)

        for row, param in self.input_data.burden_params.items():
            if not param.selected:
                continue
            self._compare(f"var burden row {row} unit_price", self.burden_unit_price[row], field.SHEET_BF_BURDEN, row, 8)
            for idx, comp in enumerate(enums.PRODUCT_COMPONENTS):
                self._compare(f"var burden row {row} {comp}", self.burden_content[row, comp], field.SHEET_BF_BURDEN, row, 9 + idx)
            self._compare(f"var burden row {row} dry_unit", self.burden_dry_unit[row], field.SHEET_BF_BURDEN, row, 30)
            self._compare(f"var burden row {row} gross_dry_unit", self.burden_gross_dry_unit[row], field.SHEET_BF_BURDEN, row, 32)
            self._compare(f"var burden row {row} return_price", self.burden_return_price[row], field.SHEET_BF_BURDEN, row, 33)
            self._compare(f"var burden row {row} return_fines", self.burden_return_fines[row], field.SHEET_BF_BURDEN, row, 35)

        for idx, hm_name in enumerate(enums.HOT_METAL_ROWS, start=2):
            self._compare(f"var hot metal composition {hm_name}", self.hot_metal_composition[hm_name], field.SHEET_HOT_METAL_COMPOSITION, idx, 6)
        self._compare("var hot metal grade", self.hot_metal_grade, field.SHEET_HOT_METAL_COMPOSITION, 19, 6)

        for idx, comp in enumerate(enums.PRODUCT_COMPONENTS, start=2):
            self._compare(f"var slag amount {comp}", self.slag_amount[comp], field.SHEET_SLAG_AMOUNT, idx, 4)
            self._compare(f"var slag composition {comp}", self.slag_composition[comp], field.SHEET_SLAG_COMPOSITION, idx, 6)
        for idx, name in enumerate(enums.SLAG_ALKALINITIES, start=2):
            self._compare(f"var slag alkalinity {name}", self.slag_alkalinity[name], field.SHEET_SLAG_ALKALINITY, idx, 6)
        for idx, name in enumerate(enums.HARMFUL_LOAD_COMPONENT, start=2):
            self._compare(f"var harmful load {name}", self.harmful_load[name], field.SHEET_HARMFUL_LOAD, idx, 6)
        self._compare("var hot metal cost", self.hot_metal_cost, field.SHEET_HOT_METAL_COST, 2, 2)

    def _compare(self, label: str, calculated: float, sheet: str, row: int, col: int, tol: float = 1e-6):
        expected = self.workbook.numeric_value(sheet, row, col, default=0.0)
        diff = calculated - expected
        scale = max(1.0, abs(expected))
        ok = abs(diff) <= tol * scale
        self.compare_total += 1
        if not ok:
            self.compare_failed += 1
            logging.warning(
                "CHECK FAIL %-55s excel=% .12g calc=% .12g diff=% .12g cell=%s!%s%s",
                label, expected, calculated, diff, sheet, self._col_letter(col), row,
            )
        else:
            logging.info(
                "CHECK PASS %-55s excel=% .12g calc=% .12g diff=% .3g cell=%s!%s%s",
                label, expected, calculated, diff, sheet, self._col_letter(col), row,
            )

    @staticmethod
    def _safe_div(numerator: float, denominator: float) -> float:
        if abs(denominator) < 1e-12:
            return 0.0
        return numerator / denominator

    @staticmethod
    def _col_letter(col: int) -> str:
        text = ""
        while col:
            col, rem = divmod(col - 1, 26)
            text = chr(65 + rem) + text
        return text
