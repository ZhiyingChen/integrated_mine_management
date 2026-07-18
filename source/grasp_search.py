import random
import time
from typing import Dict, Sequence, Set, Tuple

from .active_set_search import ActiveSetCandidate, ActiveSetSearch, CandidateResult
from .utils import field, header


class GraspSearch(ActiveSetSearch):
    PROFILE_WEIGHTS = (
        ("balanced", {"cost": 0.45, "tfe": 0.25, "baseline": 0.20, "upper": 0.10}),
        ("cheap", {"cost": 0.60, "tfe": 0.20, "baseline": 0.10, "upper": 0.10}),
        ("high_tfe", {"cost": 0.20, "tfe": 0.55, "baseline": 0.15, "upper": 0.10}),
        ("baseline", {"cost": 0.25, "tfe": 0.15, "baseline": 0.50, "upper": 0.10}),
    )

    def __init__(
        self,
        input_data,
        initial_maxiter: int,
        cost_maxiter: int,
        ftol: float,
        candidate_limit: int,
        time_budget_seconds: float = None,
        restarts: int = 20,
        rcl_size: int = 5,
        random_seed: int = 7,
    ):
        super().__init__(
            input_data=input_data,
            initial_maxiter=initial_maxiter,
            cost_maxiter=cost_maxiter,
            ftol=ftol,
            candidate_limit=candidate_limit,
            time_budget_seconds=time_budget_seconds,
        )
        self.restarts = max(1, restarts)
        self.rcl_size = max(1, rcl_size)
        self.random_seed = random_seed
        self.random = random.Random(random_seed)
        default_model = self._default_model()
        self.heuristic_sinter_rows = set(default_model.active_rows["sinter"])
        self.heuristic_pellet_rows = set(default_model.active_rows["pellet"])

    def run(self) -> CandidateResult:
        start_time = time.perf_counter()
        best_result = None
        seen = set()
        evaluated = 0

        total_candidates = self.restarts
        for restart in range(self.restarts):
            if self._time_budget_exhausted(start_time) and best_result is not None:
                break
            candidate = self._construct_candidate(restart=restart)
            key = self._candidate_key(candidate)
            if key in seen:
                continue
            seen.add(key)
            evaluated += 1
            result = self.solve_candidate(candidate=candidate, index=evaluated, total=total_candidates)
            if best_result is None or result.score < best_result.score:
                best_result = result

        return best_result

    def _construct_candidate(self, restart: int) -> ActiveSetCandidate:
        profile_name, weights = self.PROFILE_WEIGHTS[restart % len(self.PROFILE_WEIGHTS)]
        pellet_mode = "heuristic" if restart % 2 == 0 else "random"
        sinter_rows = self._construct_group(
            group="sinter",
            rows=self.input_data.sinter_rows,
            params=self.input_data.sinter_params,
            limit_key="烧结铁矿粉仓数≤",
            weights=weights,
        )
        if pellet_mode == "heuristic":
            pellet_rows = set(self.heuristic_pellet_rows)
        else:
            pellet_rows = self._construct_group(
                group="pellet",
                rows=self.input_data.pellet_rows,
                params=self.input_data.pellet_params,
                limit_key="球团铁矿粉仓数≤",
                weights=weights,
            )
        return ActiveSetCandidate(
            name=f"grasp:{profile_name}:{pellet_mode}:{restart + 1}",
            sinter_rows=sinter_rows,
            pellet_rows=pellet_rows,
        )

    def _construct_group(
        self,
        group: str,
        rows: Sequence[int],
        params: Dict[int, object],
        limit_key: str,
        weights: Dict[str, float],
    ) -> Set[int]:
        ore_rows = [
            row for row in rows
            if params[row].name in self.input_data.sinter_ore_names and params[row].ratio_bounds[1] > 0
        ]
        non_ore_rows = set(rows) - set(ore_rows)
        limit = int(self.input_data.param_dict.get(limit_key, len(ore_rows)))
        if len(ore_rows) <= limit:
            return set(rows)

        metrics = self._normalized_metrics(group=group, ore_rows=ore_rows, params=params)
        remaining = list(ore_rows)
        selected = []

        while len(selected) < limit and remaining:
            ranked = sorted(
                remaining,
                key=lambda row: self._grasp_score(row=row, metrics=metrics, weights=weights),
                reverse=True,
            )
            rcl = ranked[: min(self.rcl_size, len(ranked))]
            picked = self.random.choice(rcl)
            selected.append(picked)
            remaining.remove(picked)

        return non_ore_rows | set(selected)

    def _normalized_metrics(self, group: str, ore_rows: Sequence[int], params: Dict[int, object]) -> Dict[int, Dict[str, float]]:
        sheet = field.SHEET_INTEGRATED_SINTER if group == "sinter" else field.SHEET_INTEGRATED_PELLET
        raw = {}
        for row in ore_rows:
            tfe = params[row].chemical_content.get("TFe", 0.0)
            raw[row] = {
                "cost": params[row].unit_price / max(tfe, 1e-9),
                "tfe": tfe,
                "baseline": self.input_data.numeric_value_by_header(sheet, row, header.BlendHeader.baseline_ratio),
                "upper": params[row].ratio_bounds[1],
            }

        metrics = {}
        for key in ("cost", "tfe", "baseline", "upper"):
            values = [raw[row][key] for row in ore_rows]
            lower = min(values)
            upper = max(values)
            span = upper - lower
            for row in ore_rows:
                metrics.setdefault(row, {})
                if span <= 1e-9:
                    normalized = 1.0
                else:
                    normalized = (raw[row][key] - lower) / span
                metrics[row][key] = normalized
        return metrics

    def _grasp_score(self, row: int, metrics: Dict[int, Dict[str, float]], weights: Dict[str, float]) -> float:
        row_metrics = metrics[row]
        return (
            weights["cost"] * (1.0 - row_metrics["cost"])
            + weights["tfe"] * row_metrics["tfe"]
            + weights["baseline"] * row_metrics["baseline"]
            + weights["upper"] * row_metrics["upper"]
            + self.random.random() * 0.02
        )

    def _time_budget_exhausted(self, start_time: float) -> bool:
        return (
            self.time_budget_seconds is not None
            and time.perf_counter() - start_time >= self.time_budget_seconds
        )

    def _default_model(self):
        from .model import Model

        return Model(input_data=self.input_data)

    @staticmethod
    def _candidate_key(candidate: ActiveSetCandidate) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
        return tuple(sorted(candidate.sinter_rows)), tuple(sorted(candidate.pellet_rows))
