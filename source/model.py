import logging
import time
from typing import Dict, List, Sequence

from .constraint_checker import ConstraintChecker
from .input_data import InputData
from .initial_solution import InitialSolution
from .variable_data import VariableData


class Model:
    COST_PENALTY_WEIGHT = 1e10

    def __init__(
        self,
        input_data: InputData,
        initial_x: Dict[str, float] = None,
        active_rows: Dict[str, set] = None,
        solver_strategy: str = "slsqp",
    ):
        self.input_data = input_data
        self.initial_x = initial_x or {}
        self.active_rows = active_rows or self._default_active_rows()
        self.solver_strategy = solver_strategy
        self.checker = ConstraintChecker(input_data=input_data)
        self.sinter_rows = [
            row for row in input_data.sinter_rows
            if row in self.active_rows["sinter"]
        ]
        self.pellet_rows = [
            row for row in input_data.pellet_rows
            if row in self.active_rows["pellet"]
        ]
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

    def _default_active_rows(self) -> Dict[str, set]:
        return {
            "sinter": self._select_active_blend_rows(
                rows=self.input_data.sinter_rows,
                params=self.input_data.sinter_params,
                count_limit_key="烧结铁矿粉仓数≤",
            ),
            "pellet": self._select_active_blend_rows(
                rows=self.input_data.pellet_rows,
                params=self.input_data.pellet_params,
                count_limit_key="球团铁矿粉仓数≤",
            ),
        }

    def _select_active_blend_rows(self, rows: List[int], params: Dict[int, object], count_limit_key: str) -> set:
        active_rows = set(rows)
        limit = int(self.input_data.param_dict.get(count_limit_key, len(rows)))
        ore_rows = [
            row for row in rows
            if params[row].name in self.input_data.sinter_ore_names
            and params[row].ratio_bounds[1] > 0
        ]
        if len(ore_rows) <= limit:
            return active_rows
        selected_ore_rows = sorted(
            ore_rows,
            key=lambda row: (
                params[row].unit_price / max(params[row].chemical_content.get("TFe", 1e-9), 1e-9),
                -params[row].chemical_content.get("TFe", 0.0),
                row,
            ),
        )[:limit]
        inactive_ore_rows = set(ore_rows) - set(selected_ore_rows)
        active_rows -= inactive_ore_rows
        logging.info(
            "active ore rows selected for %s: selected=%s inactive=%s",
            count_limit_key,
            selected_ore_rows,
            sorted(inactive_ore_rows),
        )
        return active_rows

    def generate_initial_x(self) -> List[float]:
        if self.initial_x:
            return [self.initial_x[kind][row] for kind, row in self.keys]
        initial = InitialSolution(input_data=self.input_data).run_model(active_rows=self.active_rows)
        return [initial[kind][row] for kind, row in self.keys]

    def solution_dict(self, x: Sequence[float]) -> Dict[str, Dict[int, float]]:
        sinter_ratio, pellet_ratio, burden_ratio = self.decode_x(x)
        return {
            "sinter": sinter_ratio,
            "pellet": pellet_ratio,
            "burden": {
                row: value
                for row, value in burden_ratio.items()
                if row in self.burden_rows
            },
        }

    def generate_bounds(self):
        bounds = []
        for kind, row in self.keys:
            if kind == "sinter":
                bounds.append(self._bounds_for_active_row(kind, row, self.input_data.sinter_params[row].ratio_bounds))
            elif kind == "pellet":
                bounds.append(self._bounds_for_active_row(kind, row, self.input_data.pellet_params[row].ratio_bounds))
            else:
                bounds.append(self.input_data.burden_params[row].ratio_bounds)
        return bounds

    def _bounds_for_active_row(self, kind: str, row: int, bounds: tuple):
        if row not in self.active_rows[kind]:
            return 0.0, 0.0
        return bounds

    def decode_x(self, x: Sequence[float]):
        sinter_ratio = {
            row: 0.0 for row in self.input_data.sinter_rows
        }
        pellet_ratio = {
            row: 0.0 for row in self.input_data.pellet_rows
        }
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

    def objective_feasibility(self, x: Sequence[float], include_hot_metal_cost_limit: bool = False) -> float:
        variable_data = self.calculate_variable_data(x)
        return self.checker.business_violation_penalty(
            variable_data,
            include_hot_metal_cost_limit=include_hot_metal_cost_limit,
        )

    def objective_cost(self, x: Sequence[float]) -> float:
        variable_data = self.calculate_variable_data(x)
        return variable_data.hot_metal_cost + self.COST_PENALTY_WEIGHT * self.checker.business_violation_penalty(variable_data)

    def nonlinear_ineq_residuals(self, x: Sequence[float], include_hot_metal_cost_limit: bool = True):
        variable_data = self.calculate_variable_data(x)
        return self.checker.scipy_ineq_values(
            variable_data,
            include_hot_metal_cost_limit=include_hot_metal_cost_limit,
        )

    def generate_core_constraints(self):
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
        ]

    def generate_constraints(self, include_hot_metal_cost_limit: bool = True):
        return self.generate_core_constraints() + [
            {
                "type": "ineq",
                "fun": lambda x: self.nonlinear_ineq_residuals(
                    x,
                    include_hot_metal_cost_limit=include_hot_metal_cost_limit,
                ),
                "name": "business_bounds",
            }
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

    def _build_iteration_callback(self, phase: str, objective, include_hot_metal_cost_limit: bool):
        iteration = {"count": 0}

        def callback(xk):
            iteration["count"] += 1
            variable_data = self.calculate_variable_data(xk)
            objective_value = objective(xk)
            penalty = self.checker.business_violation_penalty(
                variable_data,
                include_hot_metal_cost_limit=include_hot_metal_cost_limit,
            )
            max_violation = self.checker.max_business_violation(
                variable_data,
                include_hot_metal_cost_limit=include_hot_metal_cost_limit,
            )
            print(
                "SCIPY ITER "
                f"phase={phase} "
                f"iter={iteration['count']} "
                f"objective={objective_value:.12g} "
                f"penalty={penalty:.12g} "
                f"max_business_violation={max_violation:.12g} "
                f"hot_metal_cost={variable_data.hot_metal_cost:.12g}",
                flush=True,
            )

        return callback

    def run_model(
        self,
        mode: str = "feasibility",
        maxiter: int = 500,
        ftol: float = 1e-8,
        phase: str = None,
        show_iterations: bool = True,
    ):
        try:
            from scipy.optimize import minimize
        except ModuleNotFoundError as exc:
            raise RuntimeError("当前 Python 环境缺少 scipy，无法运行求解器。") from exc

        include_cost_limit = mode != "feasibility"
        if mode in ("feasibility", "full_feasibility"):
            objective = lambda x: self.objective_feasibility(
                x,
                include_hot_metal_cost_limit=include_cost_limit,
            )
        else:
            objective = self.objective_cost
        phase_name = phase or mode
        if self.solver_strategy == "multi_slsqp":
            return self._run_multi_start_slsqp(
                minimize=minimize,
                objective=objective,
                mode=mode,
                maxiter=maxiter,
                ftol=ftol,
                phase_name=phase_name,
                include_cost_limit=include_cost_limit,
                show_iterations=show_iterations,
            )
        return self._run_single_solver(
            minimize=minimize,
            objective=objective,
            mode=mode,
            maxiter=maxiter,
            ftol=ftol,
            phase_name=phase_name,
            include_cost_limit=include_cost_limit,
            show_iterations=show_iterations,
            x0=self.generate_initial_x(),
            solver_method="SLSQP",
        )

    def _run_single_solver(
        self,
        minimize,
        objective,
        mode: str,
        maxiter: int,
        ftol: float,
        phase_name: str,
        include_cost_limit: bool,
        show_iterations: bool,
        x0,
        solver_method: str,
    ):
        start = time.time()
        bounds = self.generate_bounds()
        constraints = self.generate_constraints(include_hot_metal_cost_limit=include_cost_limit)
        callback = self._build_iteration_callback(
            phase_name,
            objective,
            include_hot_metal_cost_limit=include_cost_limit,
        ) if show_iterations else None

        result = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            callback=callback,
            options={
                "maxiter": maxiter,
                "ftol": ftol,
                "disp": show_iterations,
            },
        )
        logging.info(
            "scipy finished: phase=%s mode=%s solver=%s success=%s status=%s nit=%s fun=%.12g time=%.3fs message=%s",
            phase_name,
            mode,
            solver_method,
            result.success,
            result.status,
            getattr(result, "nit", None),
            result.fun,
            time.time() - start,
            result.message,
        )
        self.summarize_solution(result.x)
        return result

    def _run_multi_start_slsqp(
        self,
        minimize,
        objective,
        mode: str,
        maxiter: int,
        ftol: float,
        phase_name: str,
        include_cost_limit: bool,
        show_iterations: bool,
    ):
        best_result = None
        best_score = None
        seed_generator = InitialSolution(input_data=self.input_data)
        for seed_name, seed_solution in seed_generator.generate_named_seeds(active_rows=self.active_rows):
            x0 = [seed_solution[kind][row] for kind, row in self.keys]
            result = self._run_single_solver(
                minimize=minimize,
                objective=objective,
                mode=mode,
                maxiter=maxiter,
                ftol=ftol,
                phase_name=f"{phase_name}:{seed_name}",
                include_cost_limit=include_cost_limit,
                show_iterations=show_iterations,
                x0=x0,
                solver_method="SLSQP",
            )
            variable_data = self.calculate_variable_data(result.x)
            failed = self._failed_count(
                variable_data=variable_data,
                include_cost_limit=include_cost_limit,
            )
            score = (failed, variable_data.hot_metal_cost)
            if best_result is None or score < best_score:
                best_result = result
                best_score = score
                logging.info(
                    "multi-start improved: phase=%s seed=%s failed=%s cost=%.12g",
                    phase_name,
                    seed_name,
                    failed,
                    variable_data.hot_metal_cost,
                )
        return best_result

    def _failed_count(self, variable_data: VariableData, include_cost_limit: bool) -> int:
        residuals = (
            self.checker.all_business_residuals(variable_data)
            if include_cost_limit
            else self.checker.business_residuals_without_hot_metal_cost_limit(variable_data)
        )
        return sum(
            1
            for residual in residuals
            if residual.violation > self.checker.BUSINESS_TOLERANCE
        )
