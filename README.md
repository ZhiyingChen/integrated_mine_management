# Integrated Mine Management

一体化配矿算法框架。

当前阶段只实现：

- 读取 Excel 直接参数
- 计算间接参数
- 用 `scipy SLSQP` 求解不含物料个数约束的连续配比问题
- 将核心决策变量写回 Excel 对应列
- 提供 Excel 当前方案与公式映射核对脚本

暂不实现物料个数约束、整数选择逻辑和最终生产级模型。

## 结构

- `source/input_data.py`：读取直接参数，并计算间接参数。
- `source/variable_data.py`：根据给定配比计算全部辅助变量。
- `source/initial_solution.py`：从 Excel 当前解生成 scipy 初始连续配比。
- `source/model.py`：无物料个数约束版本的 scipy SLSQP 模型入口。
- `source/constraint_checker.py`：统一生成已启用质量上下限约束的残差和惩罚。
- `source/result_storage.py`：将核心变量写回 Excel。
- `source/domain_object/`：参数、物料等领域对象。
- `source/utils/field.py`：Excel 文件名和 sheet 名。
- `source/utils/header.py`：表头字段名。

## 主入口

```bash
cd /home/czy/projects/integrated_mine_management
python3 main.py
```

默认行为：

- 使用 `cost` 模式求解
- 将核心决策变量直接覆盖写回原始 Excel：
  `data/智能配矿一体化20260522.xlsx`

可选参数：

- `--mode feasibility`
  只找可行解，最小化约束违约。
- `--mode cost`
  在约束惩罚下最小化铁水成本。
- `--maxiter 500`
  调整 SLSQP 最大迭代次数。
- `--output xxx.xlsx`
  仅在非原地写回时指定输出副本文件名。

```bash
python3 main.py --mode cost
```

如果想输出到 Excel 副本而不是覆盖原始文件：

```bash
python3 main.py --mode cost --copy --output result.xlsx
```

当前写回的核心变量列：

- `一体化烧结配矿!E`
- `一体化球团配矿!E`
- `一体化高炉炉料!G`

其余单元格依赖 Excel/WPS 自身公式重算。

## 校验脚本

如果要核对当前公式映射是否和 Excel 一致：

```bash
python3 scripts/validate_excel_snapshot.py
```

该脚本会读取当前 Excel 变量值，重算间接参数和辅助变量，并与 Excel 缓存值逐项比较。

如果要校验当前结果是否满足每条业务约束：

```bash
python3 scripts/validate_business_constraints.py
```

该脚本会逐条输出：

- 三组配比和是否等于 `100`
- 每个核心决策变量是否满足上下限
- 未勾选高炉炉料是否被置零
- 烧结矿成分、烧结矿成分指标、球团矿成分、铁水成分/品位、炉渣成分、炉渣碱度、有害元素负荷是否满足上下限

`main.py` 在完成求解和写回 Excel 后，也会自动把这些业务约束校验结果写入日志。

## benchmark

如果只想测试 scipy 求解，不写回 Excel：

```bash
python3 scripts/benchmark_scipy_no_count.py --mode feasibility
python3 scripts/benchmark_scipy_no_count.py --mode cost
```

## 日志

- `logs/running_results.log`
- `logs/warning.log`
