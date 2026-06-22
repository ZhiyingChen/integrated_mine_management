import logging
import time
from dataclasses import dataclass
from itertools import product
from typing import Dict, List, Sequence, Set, Tuple

from .constraint_checker import ConstraintChecker
from .input_data import InputData
from .model import Model
from .variable_data import VariableData
from .utils import field, header


@dataclass
class ActiveSetCandidate:
    name: str
    sinter_rows: Set[int]
    pellet_rows: Set[int]


@dataclass
class CandidateResult:
    candidate: ActiveSetCandidate
    variable_data: VariableData
    stage: str
    failed: int
    total: int
    max_violation: float
    hot_metal_cost: float
    scipy_success: bool
    nit: int

    @property
    def business_feasible(self) -> bool:
        return self.failed == 0

    @property
    def score(self) -> Tuple[int, int, float, float]:
        if self.business_feasible:
            return (
                0,
                0,
                self.hot_metal_cost,
                self.max_violation,
            )
        return (
            1,
            self.failed,
            self.max_violation,
            self.hot_metal_cost,
        )


class ActiveSetSearch:
    def __init__(
        self,
        input_data: InputData,
        initial_maxiter: int,
        cost_maxiter: int,
        ftol: float,
        candidate_limit: int,
        time_budget_seconds: float = None,
    ):
        self.input_data = input_data
        self.initial_maxiter = initial_maxiter
        self.cost_maxiter = cost_maxiter
        self.ftol = ftol
        self.candidate_limit = candidate_limit
        self.time_budget_seconds = time_budget_seconds
        self.checker = ConstraintChecker(input_data=input_data)

    def run(self) -> CandidateResult:
        candidates = self.generate_candidates()
        best_result = None
        start_time = time.perf_counter()
        for index, candidate in enumerate(candidates, start=1):
            if (
                best_result is not None
                and self.time_budget_seconds is not None
                and time.perf_counter() - start_time >= self.time_budget_seconds
            ):
                logging.info(
                    "active set search stopped by time budget: elapsed=%.3fs budget=%.3fs evaluated=%s/%s",
                    time.perf_counter() - start_time,
                    self.time_budget_seconds,
                    index - 1,
                    len(candidates),
                )
                break
            result = self.solve_candidate(candidate=candidate, index=index, total=len(candidates))
            if best_result is None or result.score < best_result.score:
                best_result = result
            if result.business_feasible:
                logging.info(
                    "active set feasible candidate found: index=%s/%s name=%s cost=%.12g",
                    index,
                    len(candidates),
                    candidate.name,
                    result.hot_metal_cost,
                )
        return best_result

    def generate_candidates(self) -> List[ActiveSetCandidate]:
        sinter_sets = self._blend_candidate_sets(
            group="sinter",
            rows=self.input_data.sinter_rows,
            params=self.input_data.sinter_params,
            limit_key="烧结铁矿粉仓数≤",
        )
        pellet_sets = self._blend_candidate_sets(
            group="pellet",
            rows=self.input_data.pellet_rows,
            params=self.input_data.pellet_params,
            limit_key="球团铁矿粉仓数≤",
        )
        candidates = []
        for sinter_candidate, pellet_candidate in product(sinter_sets, pellet_sets):
            candidates.append(
                ActiveSetCandidate(
                    name=f"{sinter_candidate[0]}+{pellet_candidate[0]}",
                    sinter_rows=sinter_candidate[1],
                    pellet_rows=pellet_candidate[1],
                )
            )
            if len(candidates) >= self.candidate_limit:
                return candidates
        return candidates

    def solve_candidate(self, candidate: ActiveSetCandidate, index: int, total: int) -> CandidateResult:
        active_rows = {
            "sinter": candidate.sinter_rows,
            "pellet": candidate.pellet_rows,
        }
        logging.info(
            "active set candidate start: index=%s/%s name=%s sinter_ores=%s pellet_ores=%s",
            index,
            total,
            candidate.name,
            self._active_ore_names(candidate.sinter_rows, self.input_data.sinter_params),
            self._active_ore_names(candidate.pellet_rows, self.input_data.pellet_params),
        )

        initial_model = Model(input_data=self.input_data, active_rows=active_rows)
        initial_result = initial_model.run_model(
            mode="feasibility",
            maxiter=self.initial_maxiter,
            ftol=self.ftol,
            phase=f"search_initial:{candidate.name}",
            show_iterations=False,
        )
        initial_variable_data = initial_model.calculate_variable_data(initial_result.x)
        initial_total, initial_failed, initial_max_violation = self._summary(initial_variable_data)
        if initial_failed:
            logging.info(
                "active set candidate rejected at initial stage: index=%s/%s name=%s failed=%s/%s max_violation=%.12g cost=%.12g",
                index,
                total,
                candidate.name,
                initial_failed,
                initial_total,
                initial_max_violation,
                initial_variable_data.hot_metal_cost,
            )
            return self._build_result(
                candidate=candidate,
                variable_data=initial_variable_data,
                stage="initial",
                failed=initial_failed,
                total=initial_total,
                max_violation=initial_max_violation,
                scipy_success=initial_result.success,
                nit=getattr(initial_result, "nit", None),
            )

        full_model = Model(
            input_data=self.input_data,
            initial_x=initial_model.solution_dict(initial_result.x),
            active_rows=active_rows,
        )
        full_result = full_model.run_model(
            mode="full_feasibility",
            maxiter=self.initial_maxiter,
            ftol=self.ftol,
            phase=f"search_full:{candidate.name}",
            show_iterations=False,
        )
        full_variable_data = full_model.calculate_variable_data(full_result.x)
        full_total, full_failed, full_max_violation = self._summary(full_variable_data)
        full_candidate_result = self._build_result(
            candidate=candidate,
            variable_data=full_variable_data,
            stage="full",
            failed=full_failed,
            total=full_total,
            max_violation=full_max_violation,
            scipy_success=full_result.success,
            nit=getattr(full_result, "nit", None),
        )

        cost_model = Model(
            input_data=self.input_data,
            initial_x=full_model.solution_dict(full_result.x),
            active_rows=active_rows,
        )
        cost_result = cost_model.run_model(
            mode="cost",
            maxiter=self.cost_maxiter,
            ftol=self.ftol,
            phase=f"search_cost:{candidate.name}",
            show_iterations=False,
        )
        variable_data = cost_model.calculate_variable_data(cost_result.x)
        final_total, final_failed, final_max_violation = self._summary(variable_data)
        result = self._build_result(
            candidate=candidate,
            variable_data=variable_data,
            stage="final",
            failed=final_failed,
            total=final_total,
            max_violation=final_max_violation,
            scipy_success=cost_result.success,
            nit=getattr(cost_result, "nit", None),
        )
        result = min((full_candidate_result, result), key=lambda item: item.score)
        logging.info(
            "active set candidate done: index=%s/%s name=%s full_failed=%s/%s final_failed=%s/%s selected_stage=%s selected_failed=%s/%s max_violation=%.12g cost=%.12g",
            index,
            total,
            candidate.name,
            full_failed,
            full_total,
            final_failed,
            final_total,
            result.stage,
            result.failed,
            result.total,
            result.max_violation,
            result.hot_metal_cost,
        )
        return result

    def _blend_candidate_sets(self, group: str, rows: Sequence[int], params: Dict[int, object], limit_key: str):
        ore_rows = [
            row for row in rows
            if params[row].name in self.input_data.sinter_ore_names and params[row].ratio_bounds[1] > 0
        ]
        limit = int(self.input_data.param_dict.get(limit_key, len(ore_rows)))
        non_ore_rows = set(rows) - set(ore_rows)
        seeds = []

        heuristic_rows = Model(input_data=self.input_data).active_rows[group]
        self._append_seed(seeds, "heuristic", heuristic_rows)

        baseline_ores = self._baseline_ore_rows(group=group, rows=ore_rows, params=params, limit=limit)
        if baseline_ores:
            self._append_seed(seeds, "baseline", non_ore_rows | baseline_ores)

        cheap_ores = self._top_ores(
            ore_rows,
            params,
            limit,
            key=lambda row: (
                params[row].unit_price / max(params[row].chemical_content.get("TFe", 1e-9), 1e-9),
                -params[row].chemical_content.get("TFe", 0.0),
                row,
            ),
        )
        self._append_seed(seeds, "cheap_by_fe", non_ore_rows | cheap_ores)

        high_tfe_ores = self._top_ores(
            ore_rows,
            params,
            limit,
            key=lambda row: (
                -params[row].chemical_content.get("TFe", 0.0),
                params[row].unit_price,
                row,
            ),
        )
        self._append_seed(seeds, "high_tfe", non_ore_rows | high_tfe_ores)

        return self._with_local_swaps(
            seeds=seeds,
            ore_rows=ore_rows,
            non_ore_rows=non_ore_rows,
            params=params,
            limit=max(1, min(self.candidate_limit, 18)),
        )

    def _baseline_ore_rows(self, group: str, rows: Sequence[int], params: Dict[int, object], limit: int) -> Set[int]:
        sheet = field.SHEET_INTEGRATED_SINTER if group == "sinter" else field.SHEET_INTEGRATED_PELLET
        baseline_values = []
        for row in rows:
            value = self.input_data.numeric_value_by_header(sheet, row, header.BlendHeader.baseline_ratio)
            if value > 1e-9:
                baseline_values.append((row, value))
        if not baseline_values:
            return set()
        selected = [row for row, _ in sorted(baseline_values, key=lambda item: (-item[1], item[0]))[:limit]]
        if len(selected) < limit:
            selected_set = set(selected)
            fillers = [
                row for row in self._top_ores(
                    rows,
                    params,
                    limit,
                    key=lambda row: (
                        params[row].unit_price / max(params[row].chemical_content.get("TFe", 1e-9), 1e-9),
                        -params[row].chemical_content.get("TFe", 0.0),
                        row,
                    ),
                )
                if row not in selected_set
            ]
            selected.extend(fillers[: limit - len(selected)])
        return set(selected)

    @staticmethod
    def _top_ores(rows: Sequence[int], params: Dict[int, object], limit: int, key) -> Set[int]:
        return set(sorted(rows, key=key)[:limit])

    @staticmethod
    def _append_seed(seeds: List[Tuple[str, Set[int]]], name: str, rows: Set[int]):
        row_set = set(rows)
        if any(existing_rows == row_set for _, existing_rows in seeds):
            return
        seeds.append((name, row_set))

    def _with_local_swaps(
        self,
        seeds: List[Tuple[str, Set[int]]],
        ore_rows: Sequence[int],
        non_ore_rows: Set[int],
        params: Dict[int, object],
        limit: int,
    ) -> List[Tuple[str, Set[int]]]:
        result = list(seeds)
        ore_set = set(ore_rows)
        for seed_name, active_rows in seeds:
            active_ores = sorted(active_rows & ore_set)
            inactive_ores = sorted(ore_set - set(active_ores))
            replacement_pool = sorted(
                inactive_ores,
                key=lambda row: (
                    params[row].unit_price / max(params[row].chemical_content.get("TFe", 1e-9), 1e-9),
                    -params[row].chemical_content.get("TFe", 0.0),
                    row,
                ),
            )[:6]
            for out_row in active_ores:
                for in_row in replacement_pool:
                    swapped_ores = (set(active_ores) - {out_row}) | {in_row}
                    candidate_rows = non_ore_rows | swapped_ores
                    self._append_seed(result, f"{seed_name}:swap_{out_row}_{in_row}", candidate_rows)
                    if len(result) >= limit:
                        return result
        return result

    def _summary(self, variable_data: VariableData) -> Tuple[int, int, float]:
        residuals = self.checker.all_business_residuals(variable_data)
        failed = 0
        max_violation = 0.0
        for residual in residuals:
            if residual.violation > self.checker.BUSINESS_TOLERANCE:
                failed += 1
            max_violation = max(max_violation, residual.violation)
        return len(residuals), failed, max_violation

    def _build_result(
        self,
        candidate: ActiveSetCandidate,
        variable_data: VariableData,
        stage: str,
        failed: int,
        total: int,
        max_violation: float,
        scipy_success: bool,
        nit: int,
    ) -> CandidateResult:
        return CandidateResult(
            candidate=candidate,
            variable_data=variable_data,
            stage=stage,
            failed=failed,
            total=total,
            max_violation=max_violation,
            hot_metal_cost=variable_data.hot_metal_cost,
            scipy_success=scipy_success,
            nit=nit or 0,
        )

    def _active_ore_names(self, rows: Set[int], params: Dict[int, object]) -> List[str]:
        return [
            f"{row}:{params[row].name}"
            for row in sorted(rows)
            if params[row].name in self.input_data.sinter_ore_names
        ]
