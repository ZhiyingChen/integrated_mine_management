from typing import Dict

from .input_data import InputData


class Model:
    def __init__(self, input_data: InputData, initial_x: Dict[str, float] | None = None):
        self.input_data = input_data
        self.initial_x = initial_x or {}
        self.constraints = []
        self.keys = []

    def run_model(self):
        raise NotImplementedError("当前阶段只读取参数和校验辅助变量，暂不构建优化模型。")
