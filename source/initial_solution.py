import logging
from typing import Dict, List

from .input_data import InputData
from .utils import field, header


class InitialSolution:
    def __init__(self, input_data: InputData):
        self.input_data = input_data

    def generate_from_excel_snapshot(self):
        if not self._has_excel_baseline_values():
            raise ValueError("Excel baseline ratio columns are empty.")
        return {
            "sinter": self._project_group(
                rows=self.input_data.sinter_rows,
                values=self._read_sheet_values(
                    sheet_name=field.SHEET_INTEGRATED_SINTER,
                    rows=self.input_data.sinter_rows,
                    col=self.input_data.header_col(
                        sheet_name=field.SHEET_INTEGRATED_SINTER,
                        header_name=header.BlendHeader.baseline_ratio,
                    ),
                ),
                bounds={
                    row: self.input_data.sinter_params[row].ratio_bounds
                    for row in self.input_data.sinter_rows
                },
            ),
            "pellet": self._project_group(
                rows=self.input_data.pellet_rows,
                values=self._read_sheet_values(
                    sheet_name=field.SHEET_INTEGRATED_PELLET,
                    rows=self.input_data.pellet_rows,
                    col=self.input_data.header_col(
                        sheet_name=field.SHEET_INTEGRATED_PELLET,
                        header_name=header.BlendHeader.baseline_ratio,
                    ),
                ),
                bounds={
                    row: self.input_data.pellet_params[row].ratio_bounds
                    for row in self.input_data.pellet_rows
                },
            ),
            "burden": self._project_group(
                rows=self.selected_burden_rows,
                values=self._read_sheet_values(
                    sheet_name=field.SHEET_BF_BURDEN,
                    rows=self.selected_burden_rows,
                    col=self.input_data.header_col(
                        sheet_name=field.SHEET_BF_BURDEN,
                        header_name=header.BurdenHeader.baseline_ratio,
                    ),
                ),
                bounds={
                    row: self.input_data.burden_params[row].ratio_bounds
                    for row in self.selected_burden_rows
                },
            ),
        }

    def _has_excel_baseline_values(self) -> bool:
        checks = [
            (
                field.SHEET_INTEGRATED_SINTER,
                self.input_data.sinter_rows,
                header.BlendHeader.baseline_ratio,
            ),
            (
                field.SHEET_INTEGRATED_PELLET,
                self.input_data.pellet_rows,
                header.BlendHeader.baseline_ratio,
            ),
            (
                field.SHEET_BF_BURDEN,
                self.selected_burden_rows,
                header.BurdenHeader.baseline_ratio,
            ),
        ]
        for sheet, rows, header_name in checks:
            col = self.input_data.header_col(sheet, header_name)
            for row in rows:
                value = self.input_data.workbook.value(sheet, row, col, default=None)
                if value not in (None, ""):
                    return True
        return False

    def _read_sheet_values(self, sheet_name: str, rows: List[int], col: int) -> Dict[int, float]:
        return {
            row: self.input_data.workbook.numeric_value(sheet_name, row, col, default=0.0)
            for row in rows
        }

    def generate_from_bounds_only(self):
        return {
            "sinter": self._generate_group_from_bounds(
                rows=self.input_data.sinter_rows,
                bounds={
                    row: self.input_data.sinter_params[row].ratio_bounds
                    for row in self.input_data.sinter_rows
                },
            ),
            "pellet": self._generate_group_from_bounds(
                rows=self.input_data.pellet_rows,
                bounds={
                    row: self.input_data.pellet_params[row].ratio_bounds
                    for row in self.input_data.pellet_rows
                },
            ),
            "burden": self._generate_group_from_bounds(
                rows=self.selected_burden_rows,
                bounds={
                    row: self.input_data.burden_params[row].ratio_bounds
                    for row in self.selected_burden_rows
                },
            ),
        }

    @property
    def selected_burden_rows(self) -> List[int]:
        return [
            row for row in self.input_data.burden_rows
            if self.input_data.burden_params[row].selected
        ]

    def _project_group(
        self,
        rows: List[int],
        values: Dict[int, float],
        bounds: Dict[int, tuple],
        target: float = 100.0,
    ) -> Dict[int, float]:
        result = {
            row: min(max(values.get(row, 0.0), bounds[row][0]), bounds[row][1])
            for row in rows
        }
        self._repair_sum_within_bounds(result=result, bounds=bounds, target=target)
        logging.info(
            "initial group projected: rows=%s sum=%.12g",
            len(rows),
            sum(result.values()),
        )
        return result

    def _generate_group_from_bounds(
        self,
        rows: List[int],
        bounds: Dict[int, tuple],
        target: float = 100.0,
    ) -> Dict[int, float]:
        result = {row: bounds[row][0] for row in rows}
        self._repair_sum_within_bounds(result=result, bounds=bounds, target=target)
        logging.info(
            "initial group generated from bounds: rows=%s sum=%.12g",
            len(rows),
            sum(result.values()),
        )
        return result

    @staticmethod
    def _repair_sum_within_bounds(
        result: Dict[int, float],
        bounds: Dict[int, tuple],
        target: float,
        tol: float = 1e-9,
    ):
        for _ in range(100):
            diff = target - sum(result.values())
            if abs(diff) <= tol:
                return
            if diff > 0:
                movable = [row for row, value in result.items() if value < bounds[row][1] - tol]
                capacity = sum(bounds[row][1] - result[row] for row in movable)
            else:
                movable = [row for row, value in result.items() if value > bounds[row][0] + tol]
                capacity = sum(result[row] - bounds[row][0] for row in movable)
            if not movable or capacity <= tol:
                raise ValueError("无法在上下限内修复配比和为 100 的初始解。")
            for row in movable:
                room = bounds[row][1] - result[row] if diff > 0 else result[row] - bounds[row][0]
                step = diff * room / capacity
                result[row] += step

    def run_model(self):
        try:
            initial = self.generate_from_excel_snapshot()
            logging.info("initial solution source: excel_baseline_ratio")
            return initial
        except Exception as exc:
            logging.warning("excel baseline ratio initial solution unavailable, fallback to bounds-only: %s", exc)
            initial = self.generate_from_bounds_only()
            logging.info("initial solution source: bounds_only")
            return initial
