# Integrated Mine Management

一体化配矿算法框架。

当前阶段只实现：

- 读取 Excel 直接参数
- 计算间接参数
- 用 `scipy SLSQP` 先找业务可行初始解，再从该初始解继续优化铁水成本
- 根据参数设定中的物料使用个数上限固定活跃物料集合
- 将核心决策变量写回 Excel 对应列
- 提供 Excel 当前方案与公式映射核对脚本

暂不实现真正的整数选择模型；当前版本通过求解前固定活跃物料集合来满足物料使用个数上限。

## 结构

- `source/input_data.py`：读取直接参数，并计算间接参数。
- `source/variable_data.py`：根据给定配比计算全部辅助变量。
- `source/initial_solution.py`：不读取 Excel 基准值；按上下限和活跃物料集合生成 scipy 初始种子。
- `source/model.py`：scipy SLSQP 模型入口，包含可行解阶段、成本优化阶段和迭代输出。
- `source/constraint_checker.py`：统一生成业务约束残差、惩罚和校验日志。
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

- 先运行 `initial_feasibility` 阶段：核心约束作为 scipy 约束，其余业务约束作为违约惩罚目标。
- 对 initial solution 做完整业务校验；若失败，不写回 Excel。
- 再运行 `cost_optimization` 阶段：从 initial solution 出发优化铁水成本，同时保留业务违约惩罚。
- 对 final solution 做完整业务校验；若失败，不写回 Excel。
- 将核心决策变量直接覆盖写回原始 Excel：
  `data/智能配矿一体化.xlsx`

可选参数：

- `--initial-maxiter 300`
  调整可行初始解阶段的 SLSQP 最大迭代次数。
- `--cost-maxiter 600`
  调整成本优化阶段的 SLSQP 最大迭代次数。
- `--ftol 1e-10`
  调整 SLSQP 收敛精度。
- `--quiet-scipy`
  关闭控制台逐迭代输出。
- `--output xxx.xlsx`
  仅在非原地写回时指定输出副本文件名。

```bash
python3 main.py
```

如果想输出到 Excel 副本而不是覆盖原始文件：

```bash
python3 main.py --copy --output result.xlsx
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

控制台会输出两类状态：

- `initial_solution ... business_feasible=...`
- `final_solution ... business_feasible=...`

`cost_optimization success=False` 只表示 scipy 自身可能达到迭代上限；是否能作为业务结果，以 `final_solution business_feasible=True` 和日志中的 `failed=0` 为准。

## benchmark

如果只想测试 scipy 求解，不写回 Excel：

```bash
python3 scripts/benchmark_scipy_no_count.py --mode feasibility
python3 scripts/benchmark_scipy_no_count.py --mode cost
```

## 日志

- `logs/running_results.log`
- `logs/warning.log`
