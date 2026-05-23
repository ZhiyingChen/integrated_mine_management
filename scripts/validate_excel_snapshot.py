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
    variable_data.validate_against_excel()


if __name__ == "__main__":
    main()
