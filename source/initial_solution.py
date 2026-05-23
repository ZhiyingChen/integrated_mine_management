import logging
from typing import Dict, List

from .input_data import InputData
from .variable_data import VariableData


class InitialSolution:
    def __init__(self, input_data: InputData):
        self.input_data = input_data

    def generate_from_excel_snapshot(self):
        variable_data = VariableData(input_data=self.input_data)
        variable_data.read_variables()
        return {
            "sinter": self._project_group(
                rows=self.input_data.sinter_rows,
                values=variable_data.sinter_ratio,
                bounds={
                    row: self.input_data.sinter_params[row].ratio_bounds
                    for row in self.input_data.sinter_rows
                },
            ),
            "pellet": self._project_group(
                rows=self.input_data.pellet_rows,
                values=variable_data.pellet_ratio,
                bounds={
                    row: self.input_data.pellet_params[row].ratio_bounds
                    for row in self.input_data.pellet_rows
                },
            ),
            "burden": self._project_group(
                rows=self.selected_burden_rows,
                values=variable_data.burden_ratio,
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
        return self.generate_from_excel_snapshot()
