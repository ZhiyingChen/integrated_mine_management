import logging
import time
from typing import Dict, List, Sequence

from .constraint_checker import ConstraintChecker
from .input_data import InputData
from .initial_solution import InitialSolution
from .variable_data import VariableData


class Model:
    def __init__(self, input_data: InputData, initial_x: Dict[str, float]  = None):
        self.input_data = input_data
        self.initial_x = initial_x or {}
        self.checker = ConstraintChecker(input_data=input_data)
        self.sinter_rows = list(input_data.sinter_rows)
        self.pellet_rows = list(input_data.pellet_rows)
        self.burden_rows = [
            row for row in input_data.burden_rows
            if input_data.burden_params[row].selected
        ]
        self.keys = (
            [("sinter", row) for row in self.sinter_rows]
            + [("pellet", row) for row in self.pellet_rows]
            + [("burden", row) for row in self.burden_rows]
        )
        self._last_eval_x = None
        self._last_eval_variable_data = None

    def generate_initial_x(self) -> List[float]:
        if self.initial_x:
            return [self.initial_x[kind][row] for kind, row in self.keys]
        initial = InitialSolution(input_data=self.input_data).run_model()
        return [initial[kind][row] for kind, row in self.keys]

    def generate_bounds(self):
        bounds = []
        for kind, row in self.keys:
            if kind == "sinter":
                bounds.append(self.input_data.sinter_params[row].ratio_bounds)
            elif kind == "pellet":
                bounds.append(self.input_data.pellet_params[row].ratio_bounds)
            else:
                bounds.append(self.input_data.burden_params[row].ratio_bounds)
        return bounds

    def decode_x(self, x: Sequence[float]):
        sinter_ratio = {}
        pellet_ratio = {}
        burden_ratio = {
            row: 0.0 for row in self.input_data.burden_rows
        }
        for value, (kind, row) in zip(x, self.keys):
            if kind == "sinter":
                sinter_ratio[row] = float(value)
            elif kind == "pellet":
                pellet_ratio[row] = float(value)
            else:
                burden_ratio[row] = float(value)
        return sinter_ratio, pellet_ratio, burden_ratio

    def calculate_variable_data(self, x: Sequence[float]) -> VariableData:
        x_tuple = tuple(float(v) for v in x)
        if x_tuple == self._last_eval_x and self._last_eval_variable_data is not None:
            return self._last_eval_variable_data
        sinter_ratio, pellet_ratio, burden_ratio = self.decode_x(x_tuple)
        variable_data = VariableData.build_from_ratios(
            input_data=self.input_data,
            sinter_ratio=sinter_ratio,
            pellet_ratio=pellet_ratio,
            burden_ratio=burden_ratio,
        )
        self._last_eval_x = x_tuple
        self._last_eval_variable_data = variable_data
        return variable_data

    def objective_feasibility(self, x: Sequence[float]) -> float:
        variable_data = self.calculate_variable_data(x)
        return self.checker.violation_penalty(variable_data)

    def objective_cost(self, x: Sequence[float]) -> float:
        variable_data = self.calculate_variable_data(x)
        return variable_data.hot_metal_cost + 1e8 * self.checker.violation_penalty(variable_data)

    def nonlinear_ineq_residuals(self, x: Sequence[float]):
        variable_data = self.calculate_variable_data(x)
        return self.checker.scipy_ineq_values(variable_data)

    def generate_constraints(self):
        return [
            {
                "type": "eq",
                "fun": lambda x: sum(
                    x[idx] for idx, key in enumerate(self.keys) if key[0] == "sinter"
                ) - 100.0,
                "name": "sinter_ratio_sum",
            },
            {
                "type": "eq",
                "fun": lambda x: sum(
                    x[idx] for idx, key in enumerate(self.keys) if key[0] == "pellet"
                ) - 100.0,
                "name": "pellet_ratio_sum",
            },
            {
                "type": "eq",
                "fun": lambda x: sum(
                    x[idx] for idx, key in enumerate(self.keys) if key[0] == "burden"
                ) - 100.0,
                "name": "burden_ratio_sum",
            },
            {
                "type": "ineq",
                "fun": self.nonlinear_ineq_residuals,
                "name": "enabled_model_inequalities",
            },
        ]

    def summarize_solution(self, x: Sequence[float]):
        variable_data = self.calculate_variable_data(x)
        logging.info("solution hot metal cost: %.12g", variable_data.hot_metal_cost)
        logging.info("solution max violation: %.12g", self.checker.max_violation(variable_data))
        logging.info(
            "solution sums: sinter=%.12g pellet=%.12g burden=%.12g",
            sum(variable_data.sinter_ratio.values()),
            sum(variable_data.pellet_ratio.values()),
            sum(variable_data.burden_ratio.values()),
        )
        return variable_data

    def run_model(self, mode: str = "feasibility", maxiter: int = 500, ftol: float = 1e-8):
        try:
            from scipy.optimize import minimize
        except ModuleNotFoundError as exc:
            raise RuntimeError("当前 Python 环境缺少 scipy，无法运行求解器。") from exc

        x0 = self.generate_initial_x()
        objective = self.objective_feasibility if mode == "feasibility" else self.objective_cost
        start = time.time()
        result = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=self.generate_bounds(),
            constraints=self.generate_constraints(),
            options={
                "maxiter": maxiter,
                "ftol": ftol,
                "disp": False,
            },
        )
        logging.info(
            "scipy SLSQP finished: mode=%s success=%s status=%s nit=%s fun=%.12g time=%.3fs message=%s",
            mode,
            result.success,
            result.status,
            getattr(result, "nit", None),
            result.fun,
            time.time() - start,
            result.message,
        )
        self.summarize_solution(result.x)
        return result
