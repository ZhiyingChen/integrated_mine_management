import logging
import os
from datetime import datetime


def setup_log(log_dir="logs", log_level=logging.INFO):
    os.makedirs(log_dir, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_log_dir = os.path.join(log_dir, "runs", run_id)
    os.makedirs(run_log_dir, exist_ok=True)

    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(log_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(module)s - %(funcName)s: %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p",
    )

    file_handler = logging.FileHandler(os.path.join(log_dir, "running_results.log"), mode="w", encoding="utf-8")
    latest_warning_handler = logging.FileHandler(os.path.join(log_dir, "warning.log"), mode="w", encoding="utf-8")
    run_file_handler = logging.FileHandler(os.path.join(run_log_dir, "running_results.log"), mode="w", encoding="utf-8")
    run_warning_handler = logging.FileHandler(os.path.join(run_log_dir, "warning.log"), mode="w", encoding="utf-8")
    for handler in (file_handler, run_file_handler):
        handler.setFormatter(formatter)
    for handler in (latest_warning_handler, run_warning_handler):
        handler.setLevel(logging.WARNING)
        handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(latest_warning_handler)
    logger.addHandler(run_file_handler)
    logger.addHandler(run_warning_handler)
    logger.addHandler(console_handler)
    logger.info("log run_id=%s latest_log=%s archive_log=%s", run_id, log_dir, run_log_dir)
    return logger
