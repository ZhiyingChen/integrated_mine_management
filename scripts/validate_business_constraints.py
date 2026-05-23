import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from source.constraint_checker import ConstraintChecker
from source.input_data import InputData
from source.variable_data import VariableData
from source.utils import log


def main():
    log.setup_log(log_dir="logs")
    input_data = InputData(exe_folder="./")
    input_data.read_data()

    variable_data = VariableData(input_data=input_data)
    variable_data.read_variables()
    variable_data.calculate_auxiliary_variables()

    checker = ConstraintChecker(input_data=input_data)
    total, failed = checker.validate_and_log(variable_data)
    print(f"total={total} failed={failed} passed={total - failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
