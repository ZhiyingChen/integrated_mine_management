import os
import sys
import argparse

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from source.input_data import InputData
from source.model import Model
from source.utils import log


def main():
    parser = argparse.ArgumentParser(description="Run scipy benchmark without material-count constraints.")
    parser.add_argument(
        "--mode",
        choices=["feasibility", "cost"],
        default="feasibility",
        help="feasibility minimizes bound violations; cost minimizes hot metal cost with violation penalty.",
    )
    parser.add_argument("--maxiter", type=int, default=300)
    args = parser.parse_args()

    log.setup_log(log_dir="logs")
    input_data = InputData(exe_folder="./")
    input_data.read_data()

    model = Model(input_data=input_data)
    try:
        result = model.run_model(mode=args.mode, maxiter=args.maxiter)
    except RuntimeError as exc:
        print(exc)
        print("可安装依赖后重试：python3 -m pip install scipy numpy")
        return 2

    print(f"success={result.success} nit={getattr(result, 'nit', None)} fun={result.fun}")
    return 0 if result.success else 1


if __name__ == "__main__":
    main()
