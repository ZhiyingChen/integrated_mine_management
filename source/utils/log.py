import logging
import os


def setup_log(log_dir="logs", log_level=logging.INFO):
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(log_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(module)s - %(funcName)s: %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p",
    )

    file_handler = logging.FileHandler(
        os.path.join(log_dir, "running_results.log"), mode="w", encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    warning_handler = logging.FileHandler(
        os.path.join(log_dir, "warning.log"), mode="w", encoding="utf-8"
    )
    warning_handler.setLevel(logging.WARNING)
    warning_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(warning_handler)
    logger.addHandler(console_handler)
    return logger
