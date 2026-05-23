from .input_data import InputData


class ResultStorage:
    def __init__(self, input_data: InputData):
        self.input_data = input_data

    def write_to_excel(self):
        raise NotImplementedError("当前阶段不写回 Excel 输出。")
