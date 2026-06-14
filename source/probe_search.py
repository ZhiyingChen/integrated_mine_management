import logging
import time
from typing import List, Sequence, Set, Tuple

from .active_set_search import ActiveSetCandidate, ActiveSetSearch, CandidateResult


class ProbeSearch(ActiveSetSearch):
    """Grid search plus focused one-swap probes around seed active sets."""

    def __init__(self, *args, probe_neighbor_limit: int = 9, **kwargs):
        super().__init__(*args, **kwargs)
        self.probe_neighbor_limit = max(1, probe_neighbor_limit)

    def run(self) -> CandidateResult:
        start_time = time.perf_counter()
        seen = set()
        best_result = None
        evaluated = 0
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
            evaluated += 1
            best_result = self._select_best(best_result, result)

        probe_candidates = self._probe_candidates(seed_candidates=seed_candidates, seen=seen)
        for index, candidate in enumerate(probe_candidates, start=1):
            if self._time_exhausted(start_time):
                logging.info(
                    "probe search stopped by time budget: elapsed=%.3fs budget=%.3fs evaluated=%s",
                    time.perf_counter() - start_time,
                    self.time_budget_seconds,
                    evaluated,
                )
                break
            result = self._evaluate_candidate(
                candidate=candidate,
                index=index,
                total=len(probe_candidates),
                seen=seen,
            )
            if result is None:
                continue
            evaluated += 1
            best_result = self._select_best(best_result, result)

        logging.info(
            "probe search finished: evaluated=%s best=%s stage=%s failed=%s/%s cost=%.12g",
            evaluated,
            best_result.candidate.name if best_result else None,
            best_result.stage if best_result else None,
            best_result.failed if best_result else None,
            best_result.total if best_result else None,
            best_result.hot_metal_cost if best_result else float("nan"),
        )
        return best_result

    def _probe_candidates(self, seed_candidates: Sequence[ActiveSetCandidate], seen) -> List[ActiveSetCandidate]:
        result = []
        unique_keys = set()
        for seed in seed_candidates:
            for candidate in self._hill_style_neighbors(seed)[: self.probe_neighbor_limit]:
                key = self._candidate_key(candidate)
                if key in seen or key in unique_keys:
                    continue
                unique_keys.add(key)
                result.append(candidate)
        return result

    def _hill_style_neighbors(self, candidate: ActiveSetCandidate) -> List[ActiveSetCandidate]:
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
        active_ores = sorted(set(active_rows) & set(ore_rows))
        inactive_ores = sorted(set(ore_rows) - set(active_ores))
        neighbors = []
        for out_row in active_ores[:3]:
            for in_row in inactive_ores[:3]:
                swapped_ores = (set(active_ores) - {out_row}) | {in_row}
                new_rows = (set(rows) - set(ore_rows)) | swapped_ores
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

    def _group_context(self, candidate: ActiveSetCandidate, group: str):
        if group == "sinter":
            return self.input_data.sinter_rows, self.input_data.sinter_params, candidate.sinter_rows
        return self.input_data.pellet_rows, self.input_data.pellet_params, candidate.pellet_rows

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

    @staticmethod
    def _candidate_key(candidate: ActiveSetCandidate) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
        return tuple(sorted(candidate.sinter_rows)), tuple(sorted(candidate.pellet_rows))

    @staticmethod
    def _select_best(current, candidate):
        if current is None or candidate.score < current.score:
            return candidate
        return current

    def _time_exhausted(self, start_time: float) -> bool:
        return (
            self.time_budget_seconds is not None
            and time.perf_counter() - start_time >= self.time_budget_seconds
        )
