import logging
import time

from .input_data import InputData
from .variable_data import VariableData


class ValidationContext:
    def __init__(self, exe_folder: str = "./"):
        self.exe_folder = exe_folder
        self.input_data = InputData(exe_folder=exe_folder)
        self.variable_data = None

    def run_work_flow(self):
        start = time.time()
        self.input_data.read_data()

        self.variable_data = VariableData(input_data=self.input_data)
        self.variable_data.read_variables()
        self.variable_data.calculate_auxiliary_variables()
        self.variable_data.validate_against_excel()

        logging.info("finished in %.3fs", time.time() - start)
        return self.variable_data
