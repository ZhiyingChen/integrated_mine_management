from .input_data import InputData


class InitialSolution:
    def __init__(self, input_data: InputData):
        self.input_data = input_data

    def run_model(self):
        raise NotImplementedError("当前阶段只校验 Excel 公式映射，暂不生成优化初始解。")
