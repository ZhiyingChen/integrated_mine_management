from source.context import ValidationContext
from source.utils import log


if __name__ == "__main__":
    log.setup_log(log_dir="logs")
    validation = ValidationContext(exe_folder="./")
    validation.run_work_flow()
