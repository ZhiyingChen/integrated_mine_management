import argparse
import os

from source.input_data import InputData
from source.model import Model
from source.result_storage import ResultStorage
from source.constraint_checker import ConstraintChecker
from source.utils import field, log


def default_output_filename(mode: str) -> str:
    name, ext = os.path.splitext(field.EXCEL_FILENAME)
    return f"{name}_scipy_{mode}{ext}"


def main():
    parser = argparse.ArgumentParser(description="Run scipy optimization and write core variables back to Excel.")
    parser.add_argument("--mode", choices=["feasibility", "cost"], default="cost")
    parser.add_argument("--maxiter", type=int, default=300)
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Write core decision variables to an Excel copy instead of overwriting the source workbook.",
    )
    args = parser.parse_args()

    log.setup_log(log_dir="logs")
    input_data = InputData(exe_folder="./")
    input_data.read_data()

    model = Model(input_data=input_data)
    result = model.run_model(mode=args.mode, maxiter=args.maxiter)
    variable_data = model.calculate_variable_data(result.x)

    output_filename = (args.output or default_output_filename(args.mode)) if args.copy else None
    output_path = ResultStorage(input_data=input_data).write_core_variables_to_excel(
        sinter_ratio=variable_data.sinter_ratio,
        pellet_ratio=variable_data.pellet_ratio,
        burden_ratio=variable_data.burden_ratio,
        output_filename=output_filename,
        overwrite_source=not args.copy,
    )
    ConstraintChecker(input_data=input_data).validate_and_log(variable_data)

    print(f"success={result.success} nit={getattr(result, 'nit', None)}")
    print(f"hot_metal_cost={variable_data.hot_metal_cost}")
    print(f"output={output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run scipy optimization and write core variables back to Excel.")
    parser.add_argument("--mode", choices=["feasibility", "cost"], default="cost")
    parser.add_argument("--maxiter", type=int, default=300)
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Write core decision variables to an Excel copy instead of overwriting the source workbook.",
    )
    args = parser.parse_args()

    log.setup_log(log_dir="logs")
    input_data = InputData(exe_folder="./")
    input_data.read_data()

    model = Model(input_data=input_data)
    result = model.run_model(mode=args.mode, maxiter=args.maxiter)
    variable_data = model.calculate_variable_data(result.x)

    output_filename = (args.output or default_output_filename(args.mode)) if args.copy else None
    output_path = ResultStorage(input_data=input_data).write_core_variables_to_excel(
        sinter_ratio=variable_data.sinter_ratio,
        pellet_ratio=variable_data.pellet_ratio,
        burden_ratio=variable_data.burden_ratio,
        output_filename=output_filename,
        overwrite_source=not args.copy,
    )
    ConstraintChecker(input_data=input_data).validate_and_log(variable_data)

    print(f"success={result.success} nit={getattr(result, 'nit', None)}")
    print(f"hot_metal_cost={variable_data.hot_metal_cost}")
    print(f"output={output_path}")
