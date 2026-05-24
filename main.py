import argparse
import os

from source.input_data import InputData
from source.model import Model
from source.result_storage import ResultStorage
from source.constraint_checker import ConstraintChecker
from source.utils import field, log


def default_output_filename() -> str:
    name, ext = os.path.splitext(field.EXCEL_FILENAME)
    return f"{name}_scipy_cost{ext}"


def main():
    parser = argparse.ArgumentParser(description="Find initial feasible solution, optimize cost, and write core variables back to Excel.")
    parser.add_argument("--initial-maxiter", type=int, default=300)
    parser.add_argument("--cost-maxiter", type=int, default=600)
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
    args = parser.parse_args()

    log.setup_log(log_dir="logs")
    input_data = InputData(exe_folder="./")
    input_data.read_data()

    checker = ConstraintChecker(input_data=input_data)

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
    )
    initial_feasible = initial_failed == 0
    print(
        "initial_solution "
        f"success={initial_result.success} "
        f"nit={getattr(initial_result, 'nit', None)} "
        f"business_feasible={initial_feasible} "
        f"failed={initial_failed}/{initial_total} "
        f"max_business_violation={checker.max_business_violation(initial_variable_data):.12g}",
        flush=True,
    )
    if not initial_feasible:
        print("initial_solution is not business feasible; skip cost optimization and Excel write.", flush=True)
        return 1

    cost_model = Model(
        input_data=input_data,
        initial_x=initial_model.solution_dict(initial_result.x),
        active_rows=initial_model.active_rows,
    )
    result = cost_model.run_model(
        mode="cost",
        maxiter=args.cost_maxiter,
        ftol=args.ftol,
        phase="cost_optimization",
        show_iterations=not args.quiet_scipy,
    )
    variable_data = cost_model.calculate_variable_data(result.x)
    final_total, final_failed = checker.validate_and_log(variable_data, stage="[FINAL]")
    final_feasible = final_failed == 0

    print(f"cost_optimization success={result.success} nit={getattr(result, 'nit', None)}")
    print(
        "final_solution "
        f"business_feasible={final_feasible} "
        f"failed={final_failed}/{final_total} "
        f"max_business_violation={checker.max_business_violation(variable_data):.12g}",
        flush=True,
    )
    if not final_feasible:
        print("final_solution is not business feasible; skip Excel write.", flush=True)
        return 1

    output_filename = (args.output or default_output_filename()) if args.copy else None
    output_path = ResultStorage(input_data=input_data).write_core_variables_to_excel(
        sinter_ratio=variable_data.sinter_ratio,
        pellet_ratio=variable_data.pellet_ratio,
        burden_ratio=variable_data.burden_ratio,
        output_filename=output_filename,
        overwrite_source=not args.copy,
    )
    print(f"hot_metal_cost={variable_data.hot_metal_cost}")
    print(f"output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
