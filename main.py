import argparse
import logging
import os

from source.input_data import InputData
from source.model import Model
from source.result_storage import ResultStorage
from source.constraint_checker import ConstraintChecker
from source.active_set_search import ActiveSetSearch
from source.variable_data import VariableData
from source.utils import field, header, log


def default_output_filename() -> str:
    name, ext = os.path.splitext(field.EXCEL_FILENAME)
    return f"{name}_scipy_cost{ext}"


def _baseline_ratio_map(input_data: InputData, sheet_name: str, rows, header_name: str) -> dict:
    return {
        row: input_data.numeric_value_by_header(sheet_name, row, header_name)
        for row in rows
    }


def build_baseline_variable_data(input_data: InputData):
    sinter_ratio = _baseline_ratio_map(
        input_data=input_data,
        sheet_name=field.SHEET_INTEGRATED_SINTER,
        rows=input_data.sinter_rows,
        header_name=header.BlendHeader.baseline_ratio,
    )
    pellet_ratio = _baseline_ratio_map(
        input_data=input_data,
        sheet_name=field.SHEET_INTEGRATED_PELLET,
        rows=input_data.pellet_rows,
        header_name=header.BlendHeader.baseline_ratio,
    )
    burden_ratio = _baseline_ratio_map(
        input_data=input_data,
        sheet_name=field.SHEET_BF_BURDEN,
        rows=input_data.burden_rows,
        header_name=header.BurdenHeader.baseline_ratio,
    )
    total_baseline = (
        sum(abs(value) for value in sinter_ratio.values())
        + sum(abs(value) for value in pellet_ratio.values())
        + sum(abs(value) for value in burden_ratio.values())
    )
    if total_baseline <= 1e-9:
        return None
    return VariableData.build_from_ratios(
        input_data=input_data,
        sinter_ratio=sinter_ratio,
        pellet_ratio=pellet_ratio,
        burden_ratio=burden_ratio,
    )


def log_baseline_check(input_data: InputData, checker: ConstraintChecker):
    baseline_variable_data = build_baseline_variable_data(input_data=input_data)
    if baseline_variable_data is None:
        logging.info("BASELINE CHECK SKIPPED: no baseline ratios found.")
        print("baseline_check skipped=no_baseline_ratios", flush=True)
        return
    baseline_total, baseline_failed = checker.validate_and_log(
        baseline_variable_data,
        stage="[BASELINE]",
        log_passes=False,
    )
    baseline_feasible = baseline_failed == 0
    print(
        "baseline_check "
        f"business_feasible={baseline_feasible} "
        f"failed={baseline_failed}/{baseline_total} "
        f"max_business_violation={checker.max_business_violation(baseline_variable_data):.12g} "
        f"hot_metal_cost={baseline_variable_data.hot_metal_cost:.12g}",
        flush=True,
    )
    log_hot_metal_cost_hint(checker=checker, variable_data=baseline_variable_data, stage="[BASELINE]")


def log_hot_metal_cost_hint(checker: ConstraintChecker, variable_data, stage: str):
    residual = checker.hot_metal_cost_residual(variable_data)
    if residual.violation > checker.BUSINESS_TOLERANCE:
        logging.warning(
            "%s HOT METAL COST LIMIT EXCEEDED value=% .12g upper=% .12g violation=% .12g",
            stage,
            residual.value,
            residual.upper,
            residual.violation,
        )
        print(
            f"{stage} hot_metal_cost_limit_exceeded "
            f"value={residual.value:.12g} upper={residual.upper:.12g} violation={residual.violation:.12g}",
            flush=True,
        )
    else:
        logging.info(
            "%s hot metal cost limit within tolerance value=% .12g upper=% .12g violation=% .12g",
            stage,
            residual.value,
            residual.upper,
            residual.violation,
        )


def should_write_solution(input_data: InputData, variable_data) -> tuple:
    baseline_cost = input_data.baseline_hot_metal_cost()
    if baseline_cost is None:
        return True, "no baseline hot metal cost"
    if variable_data.hot_metal_cost > baseline_cost + 1e-9:
        return True, f"hot_metal_cost={variable_data.hot_metal_cost:.12g} > baseline_hot_metal_cost={baseline_cost:.12g}"
    return True, f"hot_metal_cost={variable_data.hot_metal_cost:.12g} <= baseline_hot_metal_cost={baseline_cost:.12g}"


def write_solution(input_data: InputData, variable_data, args, final_feasible: bool, final_failed: int, final_total: int) -> str:
    should_write, reason = should_write_solution(input_data=input_data, variable_data=variable_data)
    output_filename = (args.output or default_output_filename()) if args.copy else None
    output_path = ResultStorage(input_data=input_data).write_core_variables_to_excel(
        sinter_ratio=variable_data.sinter_ratio,
        pellet_ratio=variable_data.pellet_ratio,
        burden_ratio=variable_data.burden_ratio,
        output_filename=output_filename,
        overwrite_source=not args.copy,
    )
    logging.info(
        "EXCEL WRITE: core variables written output=%s hot_metal_cost=%.12g business_feasible=%s failed=%s/%s guard=%s",
        output_path,
        variable_data.hot_metal_cost,
        final_feasible,
        final_failed,
        final_total,
        reason,
    )
    print(f"hot_metal_cost={variable_data.hot_metal_cost}")
    print(f"output={output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Find initial feasible solution, optimize cost, and write core variables back to Excel.")
    parser.add_argument("--initial-maxiter", type=int, default=40)
    parser.add_argument("--cost-maxiter", type=int, default=60)
    parser.add_argument("--ftol", type=float, default=1e-10)
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Write core decision variables to an Excel copy instead of overwriting the source workbook.",
    )
    parser.add_argument(
        "--quiet-scipy",
        action="store_true",
        help="Disable per-iteration scipy console output.",
    )
    parser.add_argument(
        "--search-active-set",
        action="store_true",
        dest="search_active_set",
        help="Try multiple active material sets before writing the best result. Enabled by default.",
    )
    parser.add_argument(
        "--no-search-active-set",
        action="store_false",
        dest="search_active_set",
        help="Disable active material set search and run the legacy single-active-set flow.",
    )
    parser.add_argument(
        "--active-set-candidate-limit",
        type=int,
        default=4,
        help="Maximum number of active material set candidates to evaluate.",
    )
    parser.add_argument(
        "--active-set-time-budget-seconds",
        type=float,
        default=85.0,
        help="Stop active material set search after this many seconds and keep the best evaluated candidate.",
    )
    parser.set_defaults(search_active_set=True)
    args = parser.parse_args()

    log.setup_log(log_dir="logs")
    input_data = InputData(exe_folder="./")
    input_data.read_data()
    logging.info("RUN MODE: active_set_search=%s", args.search_active_set)
    print(f"run_mode active_set_search={args.search_active_set}", flush=True)

    checker = ConstraintChecker(input_data=input_data)
    log_baseline_check(input_data=input_data, checker=checker)
    if args.search_active_set:
        search_result = ActiveSetSearch(
            input_data=input_data,
            initial_maxiter=args.initial_maxiter,
            cost_maxiter=args.cost_maxiter,
            ftol=args.ftol,
            candidate_limit=args.active_set_candidate_limit,
            time_budget_seconds=args.active_set_time_budget_seconds,
        ).run()
        final_total, final_failed = checker.validate_and_log(
            search_result.variable_data,
            stage="[SEARCH_BEST]",
            log_passes=False,
        )
        final_feasible = final_failed == 0
        print(
            "active_set_search "
            f"best={search_result.candidate.name} "
            f"stage={search_result.stage} "
            f"business_feasible={final_feasible} "
            f"failed={final_failed}/{final_total} "
            f"max_business_violation={checker.max_business_violation(search_result.variable_data):.12g} "
            f"hot_metal_cost={search_result.hot_metal_cost:.12g}",
            flush=True,
        )
        log_hot_metal_cost_hint(checker=checker, variable_data=search_result.variable_data, stage="[SEARCH_BEST]")
        if not final_feasible:
            logging.warning("active_set_search best result is not business feasible; write best available solution.")
            print("active_set_search best result is not business feasible; write best available solution.", flush=True)
        write_solution(
            input_data=input_data,
            variable_data=search_result.variable_data,
            args=args,
            final_feasible=final_feasible,
            final_failed=final_failed,
            final_total=final_total,
        )
        return 0

    initial_model = Model(input_data=input_data)
    initial_result = initial_model.run_model(
        mode="feasibility",
        maxiter=args.initial_maxiter,
        ftol=args.ftol,
        phase="initial_feasibility",
        show_iterations=not args.quiet_scipy,
    )
    initial_variable_data = initial_model.calculate_variable_data(initial_result.x)
    initial_total, initial_failed = checker.validate_and_log(
        initial_variable_data,
        stage="[INITIAL]",
        include_hot_metal_cost_limit=False,
        log_passes=False,
    )
    initial_feasible = initial_failed == 0
    print(
        "initial_solution "
        f"success={initial_result.success} "
        f"nit={getattr(initial_result, 'nit', None)} "
        f"business_feasible={initial_feasible} "
        f"failed={initial_failed}/{initial_total} "
        f"max_business_violation={checker.max_business_violation(initial_variable_data, include_hot_metal_cost_limit=False):.12g} "
        f"hot_metal_cost={initial_variable_data.hot_metal_cost:.12g}",
        flush=True,
    )
    log_hot_metal_cost_hint(checker=checker, variable_data=initial_variable_data, stage="[INITIAL]")
    if not initial_feasible:
        logging.warning("initial_solution is not business feasible; write initial solution and skip downstream optimization.")
        print("initial_solution is not business feasible; write initial solution and skip downstream optimization.", flush=True)
        write_solution(
            input_data=input_data,
            variable_data=initial_variable_data,
            args=args,
            final_feasible=False,
            final_failed=initial_failed,
            final_total=initial_total,
        )
        return 0

    full_feasibility_model = Model(
        input_data=input_data,
        initial_x=initial_model.solution_dict(initial_result.x),
        active_rows=initial_model.active_rows,
    )
    full_feasibility_result = full_feasibility_model.run_model(
        mode="full_feasibility",
        maxiter=args.initial_maxiter,
        ftol=args.ftol,
        phase="full_feasibility",
        show_iterations=not args.quiet_scipy,
    )
    full_feasibility_variable_data = full_feasibility_model.calculate_variable_data(full_feasibility_result.x)
    full_total, full_failed = checker.validate_and_log(
        full_feasibility_variable_data,
        stage="[FULL_FEASIBILITY]",
        log_passes=False,
    )
    full_feasible = full_failed == 0
    print(
        "full_feasibility "
        f"success={full_feasibility_result.success} "
        f"nit={getattr(full_feasibility_result, 'nit', None)} "
        f"business_feasible={full_feasible} "
        f"failed={full_failed}/{full_total} "
        f"max_business_violation={checker.max_business_violation(full_feasibility_variable_data):.12g} "
        f"hot_metal_cost={full_feasibility_variable_data.hot_metal_cost:.12g}",
        flush=True,
    )
    log_hot_metal_cost_hint(checker=checker, variable_data=full_feasibility_variable_data, stage="[FULL_FEASIBILITY]")
    if not full_feasible:
        logging.warning("full_feasibility is not business feasible; continue cost optimization from best available solution.")
        print("full_feasibility is not business feasible; continue cost optimization from best available solution.", flush=True)

    cost_model = Model(
        input_data=input_data,
        initial_x=full_feasibility_model.solution_dict(full_feasibility_result.x),
        active_rows=full_feasibility_model.active_rows,
    )
    result = cost_model.run_model(
        mode="cost",
        maxiter=args.cost_maxiter,
        ftol=args.ftol,
        phase="cost_optimization",
        show_iterations=not args.quiet_scipy,
    )
    variable_data = cost_model.calculate_variable_data(result.x)
    final_total, final_failed = checker.validate_and_log(
        variable_data,
        stage="[FINAL]",
        log_passes=False,
    )
    final_feasible = final_failed == 0

    print(f"cost_optimization success={result.success} nit={getattr(result, 'nit', None)}")
    print(
        "final_solution "
        f"business_feasible={final_feasible} "
        f"failed={final_failed}/{final_total} "
        f"max_business_violation={checker.max_business_violation(variable_data):.12g}",
        flush=True,
    )
    log_hot_metal_cost_hint(checker=checker, variable_data=variable_data, stage="[FINAL]")
    if not final_feasible:
        logging.warning("final_solution is not business feasible; write infeasible solution for Excel-side review.")
        print("final_solution is not business feasible; write infeasible solution for Excel-side review.", flush=True)

    write_solution(
        input_data=input_data,
        variable_data=variable_data,
        args=args,
        final_feasible=final_feasible,
        final_failed=final_failed,
        final_total=final_total,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
