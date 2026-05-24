import logging
from dataclasses import dataclass
from typing import Dict, List

from .input_data import InputData
from .variable_data import VariableData
from .utils import field


@dataclass
class ConstraintResidual:
    label: str
    value: float
    lower: float
    upper: float
    lower_residual: float
    upper_residual: float

    @property
    def violation(self) -> float:
        return max(0.0, -self.lower_residual, -self.upper_residual)


class ConstraintChecker:
    def __init__(self, input_data: InputData):
        self.input_data = input_data

    def model_ineq_residuals(self, variable_data: VariableData) -> List[ConstraintResidual]:
        return self.count_and_objective_residuals(variable_data) + self.bound_residuals(variable_data)

    def parameter_logic_residuals(self) -> List[ConstraintResidual]:
        result: List[ConstraintResidual] = []
        burden_name_to_param = {
            param.name: param
            for param in self.input_data.burden_params.values()
        }

        for name in ["基准值烧结矿", "基准值球团矿"]:
            param = burden_name_to_param.get(name)
            if param is not None:
                result.append(
                    self._build_equality_residual(
                        label=f"勾选逻辑:{name}固定不参与决策",
                        value=float(param.selected),
                        target=0.0,
                    )
                )

        result.extend(
            self._exclusive_selection_residuals(
                label="勾选逻辑:烧结矿二选一",
                names=["一体化烧结矿", "烧结矿"],
                burden_name_to_param=burden_name_to_param,
            )
        )
        result.extend(
            self._exclusive_selection_residuals(
                label="勾选逻辑:球团矿二选一",
                names=["一体化球团矿", "球团矿"],
                burden_name_to_param=burden_name_to_param,
            )
        )

        for row, param in self.input_data.burden_params.items():
            if param.category == "块矿":
                result.append(
                    self._build_equality_residual(
                        label=f"勾选逻辑:块矿固定参与:{param.name}[row={row}]",
                        value=float(param.selected),
                        target=1.0,
                    )
                )
        return result

    def ratio_sum_residuals(self, variable_data: VariableData) -> List[ConstraintResidual]:
        return [
            self._build_equality_residual(
                label=f"配比和:{field.SHEET_INTEGRATED_SINTER}",
                value=sum(variable_data.sinter_ratio.values()),
                target=100.0,
            ),
            self._build_equality_residual(
                label=f"配比和:{field.SHEET_INTEGRATED_PELLET}",
                value=sum(variable_data.pellet_ratio.values()),
                target=100.0,
            ),
            self._build_equality_residual(
                label=f"配比和:{field.SHEET_BF_BURDEN}",
                value=sum(variable_data.burden_ratio.values()),
                target=100.0,
            ),
        ]

    def count_and_objective_residuals(self, variable_data: VariableData) -> List[ConstraintResidual]:
        sinter_ore_count = sum(
            1
            for row, value in variable_data.sinter_ratio.items()
            if self.input_data.sinter_params[row].name in self.input_data.sinter_ore_names and value > 1e-6
        )
        pellet_ore_count = sum(
            1
            for row, value in variable_data.pellet_ratio.items()
            if self.input_data.pellet_params[row].name in self.input_data.sinter_ore_names and value > 1e-6
        )
        return [
            self._build_bound_residual(
                label=f"使用个数:{field.SHEET_INTEGRATED_SINTER}中烧结铁矿粉仓数≤",
                value=float(sinter_ore_count),
                lower=0.0,
                upper=self.input_data.param_dict.get("烧结铁矿粉仓数≤", 0.0),
            ),
            self._build_bound_residual(
                label=f"使用个数:{field.SHEET_INTEGRATED_PELLET}中烧结铁矿粉仓数≤",
                value=float(pellet_ore_count),
                lower=0.0,
                upper=self.input_data.param_dict.get("球团铁矿粉仓数≤", 0.0),
            ),
            self._build_bound_residual(
                label="目标上限:一体化铁水成本≤参考铁成本",
                value=variable_data.hot_metal_cost,
                lower=0.0,
                upper=self.input_data.param_dict.get("参考铁成本", 0.0),
            ),
        ]

    def ratio_bound_residuals(self, variable_data: VariableData) -> List[ConstraintResidual]:
        result: List[ConstraintResidual] = []

        for row in self.input_data.sinter_rows:
            param = self.input_data.sinter_params[row]
            result.append(
                self._build_bound_residual(
                    label=f"配比上下限:{field.SHEET_INTEGRATED_SINTER}:{param.name}[row={row}]",
                    value=variable_data.sinter_ratio.get(row, 0.0),
                    lower=param.ratio_bounds[0],
                    upper=param.ratio_bounds[1],
                )
            )

        for row in self.input_data.pellet_rows:
            param = self.input_data.pellet_params[row]
            result.append(
                self._build_bound_residual(
                    label=f"配比上下限:{field.SHEET_INTEGRATED_PELLET}:{param.name}[row={row}]",
                    value=variable_data.pellet_ratio.get(row, 0.0),
                    lower=param.ratio_bounds[0],
                    upper=param.ratio_bounds[1],
                )
            )

        for row in self.input_data.burden_rows:
            param = self.input_data.burden_params[row]
            value = variable_data.burden_ratio.get(row, 0.0)
            if param.selected:
                result.append(
                    self._build_bound_residual(
                        label=f"配比上下限:{field.SHEET_BF_BURDEN}:{param.name}[row={row}]",
                        value=value,
                        lower=param.ratio_bounds[0],
                        upper=param.ratio_bounds[1],
                    )
                )
            else:
                result.append(
                    self._build_equality_residual(
                        label=f"未勾选置零:{field.SHEET_BF_BURDEN}:{param.name}[row={row}]",
                        value=value,
                        target=0.0,
                    )
                )
        return result

    def bound_residuals(self, variable_data: VariableData) -> List[ConstraintResidual]:
        result: List[ConstraintResidual] = []
        self._extend_bound_group(
            result=result,
            group_name="烧结矿成分",
            values=variable_data.sinter_composition,
            bounds=self.input_data.sinter_composition_bounds,
        )
        self._extend_bound_group(
            result=result,
            group_name="烧结矿成分指标",
            values=variable_data.sinter_indicator,
            bounds=self.input_data.sinter_indicator_bounds,
        )
        self._extend_bound_group(
            result=result,
            group_name="球团矿成分",
            values=variable_data.pellet_composition,
            bounds=self.input_data.pellet_composition_bounds,
        )
        hot_metal_values = dict(variable_data.hot_metal_composition)
        hot_metal_values["品位"] = variable_data.hot_metal_grade
        self._extend_bound_group(
            result=result,
            group_name="铁水成分",
            values=hot_metal_values,
            bounds=self.input_data.hot_metal_bounds,
        )
        self._extend_bound_group(
            result=result,
            group_name="炉渣成分",
            values=variable_data.slag_composition,
            bounds=self.input_data.slag_composition_bounds,
        )
        self._extend_bound_group(
            result=result,
            group_name="炉渣碱度",
            values=variable_data.slag_alkalinity,
            bounds=self.input_data.slag_alkalinity_bounds,
        )
        self._extend_bound_group(
            result=result,
            group_name="有害元素负荷",
            values=variable_data.harmful_load,
            bounds=self.input_data.harmful_load_bounds,
        )
        return result

    def all_business_residuals(self, variable_data: VariableData) -> List[ConstraintResidual]:
        return (
            self.parameter_logic_residuals()
            + self.ratio_sum_residuals(variable_data)
            + self.count_and_objective_residuals(variable_data)
            + self.ratio_bound_residuals(variable_data)
            + self.bound_residuals(variable_data)
        )

    def scipy_ineq_values(self, variable_data: VariableData) -> List[float]:
        values = []
        for residual in self.model_ineq_residuals(variable_data):
            values.append(residual.lower_residual)
            values.append(residual.upper_residual)
        return values

    def violation_penalty(self, variable_data: VariableData) -> float:
        penalty = 0.0
        for residual in self.model_ineq_residuals(variable_data):
            scale = max(1.0, abs(residual.lower), abs(residual.upper))
            penalty += (max(0.0, -residual.lower_residual) / scale) ** 2
            penalty += (max(0.0, -residual.upper_residual) / scale) ** 2
        return penalty

    def max_violation(self, variable_data: VariableData) -> float:
        violations = [residual.violation for residual in self.model_ineq_residuals(variable_data)]
        return max(violations) if violations else 0.0

    def validate_and_log(self, variable_data: VariableData, tol: float = 1e-6):
        total = 0
        failed = 0
        for residual in self.all_business_residuals(variable_data):
            total += 1
            scale = max(1.0, abs(residual.lower), abs(residual.upper))
            ok = residual.violation <= tol * scale
            if ok:
                logging.info(
                    "BUSINESS CHECK PASS %-55s value=% .12g lower=% .12g upper=% .12g violation=% .3g",
                    residual.label,
                    residual.value,
                    residual.lower,
                    residual.upper,
                    residual.violation,
                )
            else:
                failed += 1
                logging.warning(
                    "BUSINESS CHECK FAIL %-55s value=% .12g lower=% .12g upper=% .12g violation=% .12g",
                    residual.label,
                    residual.value,
                    residual.lower,
                    residual.upper,
                    residual.violation,
                )
        logging.info(
            "business constraint summary: total=%s failed=%s passed=%s",
            total,
            failed,
            total - failed,
        )
        return total, failed

    @staticmethod
    def _extend_bound_group(
        result: List[ConstraintResidual],
        group_name: str,
        values: Dict[str, float],
        bounds,
    ):
        for name, bound_item in bounds.items():
            if not bound_item.selected:
                continue
            value = values.get(name, 0.0)
            lower, upper = bound_item.bounds
            result.append(
                ConstraintResidual(
                    label=f"{group_name}:{name}",
                    value=value,
                    lower=lower,
                    upper=upper,
                    lower_residual=value - lower,
                    upper_residual=upper - value,
                )
            )

    @staticmethod
    def _build_bound_residual(label: str, value: float, lower: float, upper: float) -> ConstraintResidual:
        return ConstraintResidual(
            label=label,
            value=value,
            lower=lower,
            upper=upper,
            lower_residual=value - lower,
            upper_residual=upper - value,
        )

    @staticmethod
    def _build_equality_residual(label: str, value: float, target: float) -> ConstraintResidual:
        return ConstraintResidual(
            label=label,
            value=value,
            lower=target,
            upper=target,
            lower_residual=value - target,
            upper_residual=target - value,
        )

    @staticmethod
    def _exclusive_selection_residuals(
        label: str,
        names: List[str],
        burden_name_to_param: Dict[str, object],
    ) -> List[ConstraintResidual]:
        values = [
            float(burden_name_to_param[name].selected)
            for name in names
            if name in burden_name_to_param
        ]
        if len(values) != len(names):
            return []
        return [
            ConstraintResidual(
                label=label,
                value=sum(values),
                lower=1.0,
                upper=1.0,
                lower_residual=sum(values) - 1.0,
                upper_residual=1.0 - sum(values),
            )
        ]
