import logging
import time
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from .active_set_search import ActiveSetCandidate, ActiveSetSearch, CandidateResult


class BeamSearch(ActiveSetSearch):
    """Beam search over active material sets.

    The search first evaluates the same seed candidates as ActiveSetSearch, then
    expands the best active sets with one-for-one ore swaps while the time budget
    allows. This keeps the current grid result available and uses remaining time
    for local exploration around promising sets.
    """

    def __init__(
        self,
        *args,
        beam_width: int = 2,
        beam_depth: int = 2,
        beam_neighbor_limit: int = 8,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.beam_width = max(1, beam_width)
        self.beam_depth = max(0, beam_depth)
        self.beam_neighbor_limit = max(1, beam_neighbor_limit)

    def run(self) -> CandidateResult:
        start_time = time.perf_counter()
        seen = set()
        evaluated_results: List[CandidateResult] = []
        best_result = None

        seed_candidates = self.generate_candidates()
        for index, candidate in enumerate(seed_candidates, start=1):
            if self._time_exhausted(start_time) and best_result is not None:
                break
            result = self._evaluate_candidate(
                candidate=candidate,
                index=index,
                total=len(seed_candidates),
                seen=seen,
            )
            if result is None:
                continue
            evaluated_results.append(result)
            best_result = self._select_best(best_result, result)

        frontier = self._frontier(evaluated_results)
        for depth in range(1, self.beam_depth + 1):
            if not frontier or self._time_exhausted(start_time):
                break
            neighbor_candidates = self._ranked_neighbors(frontier=frontier, seen=seen)
            if not neighbor_candidates:
                break
            depth_results = []
            for index, candidate in enumerate(neighbor_candidates, start=1):
                if self._time_exhausted(start_time):
                    logging.info(
                        "beam search stopped by time budget: depth=%s elapsed=%.3fs budget=%.3fs evaluated=%s",
                        depth,
                        time.perf_counter() - start_time,
                        self.time_budget_seconds,
                        len(evaluated_results),
                    )
                    break
                result = self._evaluate_candidate(
                    candidate=candidate,
                    index=index,
                    total=len(neighbor_candidates),
                    seen=seen,
                )
                if result is None:
                    continue
                depth_results.append(result)
                evaluated_results.append(result)
                best_result = self._select_best(best_result, result)
            frontier = self._frontier(evaluated_results)

        logging.info(
            "beam search finished: evaluated=%s best=%s stage=%s failed=%s/%s cost=%.12g",
            len(evaluated_results),
            best_result.candidate.name if best_result else None,
            best_result.stage if best_result else None,
            best_result.failed if best_result else None,
            best_result.total if best_result else None,
            best_result.hot_metal_cost if best_result else float("nan"),
        )
        return best_result

    def _evaluate_candidate(
        self,
        candidate: ActiveSetCandidate,
        index: int,
        total: int,
        seen: Set[Tuple[Tuple[int, ...], Tuple[int, ...]]],
    ):
        key = self._candidate_key(candidate)
        if key in seen:
            return None
        seen.add(key)
        return self.solve_candidate(candidate=candidate, index=index, total=total)

    def _ranked_neighbors(self, frontier: Sequence[CandidateResult], seen) -> List[ActiveSetCandidate]:
        neighbor_lists = [
            self._neighbors(result.candidate)
            for result in frontier[: self.beam_width]
        ]
        unique_candidates = []
        unique_keys = set()
        max_neighbors = max((len(items) for items in neighbor_lists), default=0)
        for offset in range(max_neighbors):
            for items in neighbor_lists:
                if offset >= len(items):
                    continue
                candidate = items[offset]
                key = self._candidate_key(candidate)
                if key in seen or key in unique_keys:
                    continue
                unique_keys.add(key)
                unique_candidates.append(candidate)
                if len(unique_candidates) >= self.beam_neighbor_limit:
                    return unique_candidates
        return unique_candidates

    def _neighbors(self, candidate: ActiveSetCandidate) -> List[ActiveSetCandidate]:
        return (
            self._swap_neighbors(candidate=candidate, group="sinter")
            + self._swap_neighbors(candidate=candidate, group="pellet")
        )

    def _swap_neighbors(self, candidate: ActiveSetCandidate, group: str) -> List[ActiveSetCandidate]:
        rows, params, active_rows = self._group_context(candidate=candidate, group=group)
        ore_rows = [
            row for row in rows
            if params[row].name in self.input_data.sinter_ore_names
            and params[row].ratio_bounds[1] > 0
        ]
        ore_set = set(ore_rows)
        active_ores = sorted(set(active_rows) & ore_set)
        inactive_ores = sorted(ore_set - set(active_ores))
        if not active_ores or not inactive_ores:
            return []

        out_pool = self._unique_rows(
            active_ores[:4]
            + sorted(active_ores, key=lambda row: self._ore_expense_key(row, params), reverse=True)[:4]
        )
        in_pool = self._unique_rows(inactive_ores[:4] + self._replacement_pool(inactive_ores, params))
        non_ore_rows = set(rows) - ore_set
        neighbors = []
        for out_row in out_pool:
            for in_row in in_pool:
                swapped_ores = (set(active_ores) - {out_row}) | {in_row}
                new_rows = non_ore_rows | swapped_ores
                if group == "sinter":
                    neighbors.append(
                        ActiveSetCandidate(
                            name=f"{candidate.name}:s{out_row}_{in_row}",
                            sinter_rows=new_rows,
                            pellet_rows=set(candidate.pellet_rows),
                        )
                    )
                else:
                    neighbors.append(
                        ActiveSetCandidate(
                            name=f"{candidate.name}:p{out_row}_{in_row}",
                            sinter_rows=set(candidate.sinter_rows),
                            pellet_rows=new_rows,
                        )
                    )
        return neighbors

    def _replacement_pool(self, inactive_ores: Sequence[int], params: Dict[int, object]) -> List[int]:
        cheap = sorted(inactive_ores, key=lambda row: self._ore_cheap_key(row, params))[:6]
        high_tfe = sorted(
            inactive_ores,
            key=lambda row: (
                -params[row].chemical_content.get("TFe", 0.0),
                params[row].unit_price,
                row,
            ),
        )[:4]
        result = []
        for row in cheap + high_tfe:
            if row not in result:
                result.append(row)
        return result

    def _group_context(self, candidate: ActiveSetCandidate, group: str):
        if group == "sinter":
            return self.input_data.sinter_rows, self.input_data.sinter_params, candidate.sinter_rows
        return self.input_data.pellet_rows, self.input_data.pellet_params, candidate.pellet_rows

    def _active_set_proxy_cost(self, candidate: ActiveSetCandidate):
        return (
            self._group_proxy_cost(candidate.sinter_rows, self.input_data.sinter_params),
            self._group_proxy_cost(candidate.pellet_rows, self.input_data.pellet_params),
            candidate.name,
        )

    def _group_proxy_cost(self, active_rows: Iterable[int], params: Dict[int, object]) -> float:
        ore_rows = [
            row for row in active_rows
            if params[row].name in self.input_data.sinter_ore_names
        ]
        if not ore_rows:
            return 0.0
        return sum(self._ore_price_per_fe(row, params) for row in ore_rows) / len(ore_rows)

    def _ore_cheap_key(self, row: int, params: Dict[int, object]):
        return (
            self._ore_price_per_fe(row, params),
            -params[row].chemical_content.get("TFe", 0.0),
            row,
        )

    def _ore_expense_key(self, row: int, params: Dict[int, object]):
        return (
            self._ore_price_per_fe(row, params),
            params[row].unit_price,
            -params[row].chemical_content.get("TFe", 0.0),
            row,
        )

    @staticmethod
    def _ore_price_per_fe(row: int, params: Dict[int, object]) -> float:
        tfe = max(params[row].chemical_content.get("TFe", 0.0), 1e-9)
        return params[row].unit_price / tfe

    @staticmethod
    def _unique_rows(rows: Sequence[int]) -> List[int]:
        result = []
        for row in rows:
            if row not in result:
                result.append(row)
        return result

    @staticmethod
    def _candidate_key(candidate: ActiveSetCandidate) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
        return tuple(sorted(candidate.sinter_rows)), tuple(sorted(candidate.pellet_rows))

    @staticmethod
    def _select_best(current, candidate):
        if current is None or candidate.score < current.score:
            return candidate
        return current

    def _frontier(self, results: Sequence[CandidateResult]) -> List[CandidateResult]:
        feasible = [result for result in results if result.business_feasible]
        pool = feasible or list(results)
        return sorted(pool, key=lambda result: result.score)[: self.beam_width]

    def _time_exhausted(self, start_time: float) -> bool:
        return (
            self.time_budget_seconds is not None
            and time.perf_counter() - start_time >= self.time_budget_seconds
        )
