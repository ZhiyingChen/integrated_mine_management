import logging
from typing import Dict, List

from .input_data import InputData


class InitialSolution:
    def __init__(self, input_data: InputData):
        self.input_data = input_data

    def generate_from_bounds_only(self, active_rows: Dict[str, set] = None):
        active_rows = active_rows or {}
        return {
            "sinter": self._generate_group_from_bounds(
                rows=self.input_data.sinter_rows,
                bounds={
                    row: self._active_bounds(
                        row=row,
                        bounds=self.input_data.sinter_params[row].ratio_bounds,
                        active_rows=active_rows.get("sinter"),
                    )
                    for row in self.input_data.sinter_rows
                },
            ),
            "pellet": self._generate_group_from_bounds(
                rows=self.input_data.pellet_rows,
                bounds={
                    row: self._active_bounds(
                        row=row,
                        bounds=self.input_data.pellet_params[row].ratio_bounds,
                        active_rows=active_rows.get("pellet"),
                    )
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

    def generate_from_midpoint(self, active_rows: Dict[str, set] = None):
        active_rows = active_rows or {}
        return {
            "sinter": self._project_group(
                rows=self.input_data.sinter_rows,
                values={
                    row: self._midpoint_value(
                        row=row,
                        bounds=self.input_data.sinter_params[row].ratio_bounds,
                        active_rows=active_rows.get("sinter"),
                    )
                    for row in self.input_data.sinter_rows
                },
                bounds={
                    row: self._active_bounds(
                        row=row,
                        bounds=self.input_data.sinter_params[row].ratio_bounds,
                        active_rows=active_rows.get("sinter"),
                    )
                    for row in self.input_data.sinter_rows
                },
            ),
            "pellet": self._project_group(
                rows=self.input_data.pellet_rows,
                values={
                    row: self._midpoint_value(
                        row=row,
                        bounds=self.input_data.pellet_params[row].ratio_bounds,
                        active_rows=active_rows.get("pellet"),
                    )
                    for row in self.input_data.pellet_rows
                },
                bounds={
                    row: self._active_bounds(
                        row=row,
                        bounds=self.input_data.pellet_params[row].ratio_bounds,
                        active_rows=active_rows.get("pellet"),
                    )
                    for row in self.input_data.pellet_rows
                },
            ),
            "burden": self._project_group(
                rows=self.selected_burden_rows,
                values={
                    row: sum(self.input_data.burden_params[row].ratio_bounds) / 2
                    for row in self.selected_burden_rows
                },
                bounds={
                    row: self.input_data.burden_params[row].ratio_bounds
                    for row in self.selected_burden_rows
                },
            ),
        }

    def generate_from_upper_bias(self, active_rows: Dict[str, set] = None):
        active_rows = active_rows or {}
        return {
            "sinter": self._project_group(
                rows=self.input_data.sinter_rows,
                values={
                    row: self._upper_value(
                        row=row,
                        bounds=self.input_data.sinter_params[row].ratio_bounds,
                        active_rows=active_rows.get("sinter"),
                    )
                    for row in self.input_data.sinter_rows
                },
                bounds={
                    row: self._active_bounds(
                        row=row,
                        bounds=self.input_data.sinter_params[row].ratio_bounds,
                        active_rows=active_rows.get("sinter"),
                    )
                    for row in self.input_data.sinter_rows
                },
            ),
            "pellet": self._project_group(
                rows=self.input_data.pellet_rows,
                values={
                    row: self._upper_value(
                        row=row,
                        bounds=self.input_data.pellet_params[row].ratio_bounds,
                        active_rows=active_rows.get("pellet"),
                    )
                    for row in self.input_data.pellet_rows
                },
                bounds={
                    row: self._active_bounds(
                        row=row,
                        bounds=self.input_data.pellet_params[row].ratio_bounds,
                        active_rows=active_rows.get("pellet"),
                    )
                    for row in self.input_data.pellet_rows
                },
            ),
            "burden": self._project_group(
                rows=self.selected_burden_rows,
                values={
                    row: self.input_data.burden_params[row].ratio_bounds[1]
                    for row in self.selected_burden_rows
                },
                bounds={
                    row: self.input_data.burden_params[row].ratio_bounds
                    for row in self.selected_burden_rows
                },
            ),
        }

    @staticmethod
    def _active_bounds(row: int, bounds: tuple, active_rows):
        if active_rows is not None and row not in active_rows:
            return 0.0, 0.0
        return bounds

    @staticmethod
    def _midpoint_value(row: int, bounds: tuple, active_rows):
        lower, upper = InitialSolution._active_bounds(row=row, bounds=bounds, active_rows=active_rows)
        return (lower + upper) / 2

    @staticmethod
    def _upper_value(row: int, bounds: tuple, active_rows):
        _, upper = InitialSolution._active_bounds(row=row, bounds=bounds, active_rows=active_rows)
        return upper

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

    def run_model(self, active_rows: Dict[str, set] = None):
        initial = self.generate_from_bounds_only(active_rows=active_rows)
        logging.info("initial solution seed source: bounds_only")
        return initial

    def generate_named_seeds(self, active_rows: Dict[str, set] = None):
        return [
            ("bounds_only", self.generate_from_bounds_only(active_rows=active_rows)),
            ("midpoint", self.generate_from_midpoint(active_rows=active_rows)),
            ("upper_bias", self.generate_from_upper_bias(active_rows=active_rows)),
        ]
