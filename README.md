# Integrated Mine Management

一体化配矿算法框架。

当前阶段只实现：

- 读取 Excel 直接参数
- 计算间接参数
- 读取 Excel 当前变量值
- 计算辅助变量
- 将辅助变量与 Excel 公式缓存值逐项核对并输出日志

暂不实现优化建模和结果写回。

## 结构

- `source/context.py`：装配当前校验 workflow。
- `source/input_data.py`：读取直接参数，并计算间接参数。
- `source/variable_data.py`：读取当前变量快照，并计算辅助变量。
- `source/domain_object/`：参数、物料等领域对象。
- `source/utils/field.py`：Excel 文件名和 sheet 名。
- `source/utils/header.py`：表头字段名。
- `source/model.py`、`source/result_storage.py`、`source/initial_solution.py`：后续建模与输出扩展入口，当前只保留边界占位。

## 运行

```bash
cd /home/czy/projects/integrated_mine_management
python3 main.py
```

日志输出：

- `logs/running_results.log`
- `logs/warning.log`
