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

- 先按 `基准值配比` 列构造一份 `baseline_check`，检查 baseline 在当前一体化模型口径下违反了哪些业务约束。
- 默认启用 `active_set_search`：在多组活跃物料集合上运行 `initial_feasibility -> full_feasibility -> cost_optimization`，并保留业务约束最优、再比较铁水成本最优的候选。
- 对最终选中的 `SEARCH_BEST` 结果做完整业务校验。
- 业务校验日志默认只输出 `FAIL` 项和最终汇总，不逐条打印 `PASS` 项。
- 将核心决策变量直接覆盖写回原始 Excel：
  `data/智能配矿一体化.xlsx`

可选参数：

- `--initial-maxiter 40`
  调整可行初始解阶段的 SLSQP 最大迭代次数。
- `--cost-maxiter`
  调整成本优化阶段的 SLSQP 最大迭代次数。不指定时按策略给默认值：`grid=120`，`probe/beam=60`。
- `--ftol 1e-10`
  调整 SLSQP 收敛精度。
- `--quiet-scipy`
  关闭控制台逐迭代输出。
- `--output xxx.xlsx`
  仅在非原地写回时指定输出副本文件名。
- `--search-active-set`
  显式启用活跃物料集合搜索；当前默认已经启用，保留该参数只是为了兼容旧命令。
- `--no-search-active-set`
  关闭活跃物料集合搜索，回退到旧的单组活跃物料集合流程。
- `--active-set-candidate-limit 4`
  控制活跃物料集合搜索最多评估多少组候选。
- `--active-set-time-budget-seconds 85`
  控制活跃物料集合搜索的总耗时预算；超过后停止搜索并保留当前最优候选。
- `--search-strategy grid`
  外层活跃物料集合搜索策略。可选 `grid`、`probe`、`beam`。
- `--probe-neighbor-limit 9`
  `probe` 策略中，每个种子集合最多尝试多少个一换一探针候选。
- `--beam-width 2 --beam-depth 2 --beam-neighbor-limit 8`
  `beam` 策略的前沿宽度、扩展深度和每层邻居候选上限。

```bash
python3 main.py
```

默认会启用活跃物料集合搜索。基准值候选只读取 `基准值配比` 列；如果没有基准值，则不会把 Excel 当前 `一体化配比` 当作候选来源。

## 搜索策略

默认策略是 `grid`，等价于：

```bash
python3 main.py --search-strategy grid
```

`grid` 方法（领域搜索 + 梯度下降）：

- 方法：外层先做活跃物料集合的领域搜索，生成少量稳定候选集合，包括启发式低成本/高铁集合、基准值活跃集合、高 TFe 集合，以及局部一换一集合；内层对每个候选集合用 SLSQP 做连续配比优化，可理解为梯度下降类的非线性约束优化。
- 默认参数：`--active-set-candidate-limit 4`，`--active-set-time-budget-seconds 85`，`--cost-maxiter 120`。
- 适用场景：日常默认使用，速度和稳定性最好；当前五组数据通常 30-45 秒完成。

`probe` 方法（领域搜索 + 邻域探针搜索 + 梯度下降）：

```bash
python3 main.py --search-strategy probe
```

- 方法：外层先完整运行一轮 `grid` 种子，保证不丢默认结果；然后围绕每个种子集合做 hill-style 一换一邻域探针搜索，例如替换一个烧结矿粉或球团矿粉活跃物料；内层仍对每个候选集合用 SLSQP 做连续配比优化。
- 默认参数：`--probe-neighbor-limit 9`，`--cost-maxiter 60`，`--active-set-time-budget-seconds 85`。
- 适用场景：想多花一点时间找更低成本结果时使用；当前五组数据中 `data0/data2/data4` 优于旧默认，`data1/data3` 持平，运行时间通常接近 95 秒。

`beam` 方法（领域搜索 + 束搜索 + 梯度下降）：

```bash
python3 main.py --search-strategy beam
```

- 方法：外层先运行 `grid` 种子，再保留当前最好的若干活跃物料集合组成 beam frontier，对这些集合继续做一换一扩展，逐层做束搜索；内层仍对每个候选集合用 SLSQP 做连续配比优化。
- 默认参数：`--beam-width 2`，`--beam-depth 2`，`--beam-neighbor-limit 8`，`--cost-maxiter 60`。
- 适用场景：研究/深搜使用；部分数据有改善，但耗时更高，暂不作为默认。

如果要关闭活跃物料集合搜索，只跑单组默认活跃集合：

```bash
python3 main.py --no-search-active-set
```

本轮实测的铁水成本对比：

- 旧默认 `grid + cost_maxiter=60`：`data0=2124.4661`，`data1=2193.4560`，`data2=2195.4883`，`data3=2206.9030`，`data4=2196.7824`。
- 新默认 `grid + cost_maxiter=120`：`data0=2124.4129`，`data1=2193.4560`，`data2=2194.2694`，`data3=2206.9030`，`data4=2196.7810`。
- 可选 `probe + cost_maxiter=60`：`data0=2124.3006`，`data1=2193.4560`，`data2=2194.8378`，`data3=2206.9030`，`data4=2195.3609`。

如果想输出到 Excel 副本而不是覆盖原始文件：

```bash
python3 main.py --copy --output result.xlsx
```

当前写回的核心变量列：

- `一体化烧结配矿!E`
- `一体化球团配矿!E`
- `一体化高炉炉料!G`

其余单元格依赖 Excel/WPS 自身公式重算。

如果 Excel 中存在 `基准值铁水成本`，程序仍会把优化结果和基准值做比较，并把比较结果记到日志里；但不再因为高于基准值而拦截写回。

注意：

- `baseline_check` 的目的，是回答“baseline 列在当前一体化模型约束下违反了哪些约束”。它不是直接复用 Excel 里 `基准值烧结矿/基准值球团矿` 分支公式的严格复刻校验。
- 默认 `baseline` 候选只把 `基准值配比` 用作活跃物料集合来源，不会把 baseline 比例本身直接作为 scipy warm start。

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

`main.py` 在运行时也会自动把这些业务约束校验结果写入日志，先输出 `[BASELINE]` 的失败约束和汇总，再输出最终 `[SEARCH_BEST]` 或其他阶段结果的失败约束和汇总。

控制台会输出两类状态：

- `baseline_check ... business_feasible=...`
- `active_set_search ... business_feasible=...`

如果使用 `--no-search-active-set` 回退旧流程，控制台仍会输出：

- `initial_solution ... business_feasible=...`
- `full_feasibility ... business_feasible=...`
- `final_solution ... business_feasible=...`

`cost_optimization success=False` 只表示 scipy 自身可能达到迭代上限；是否能作为业务可行结果，以对应阶段的 `business_feasible=True` 和日志中的 `failed=0` 为准。即使业务约束未全部满足，程序也会写回当前核心变量，方便在 Excel 中查看公式计算结果。

## benchmark

如果只想测试 scipy 求解，不写回 Excel：

```bash
python3 scripts/benchmark_scipy_no_count.py --mode feasibility
python3 scripts/benchmark_scipy_no_count.py --mode cost
```

## 日志

- `logs/running_results.log`
- `logs/warning.log`
- `logs/runs/<run_id>/running_results.log`
- `logs/runs/<run_id>/warning.log`

`logs/running_results.log` 和 `logs/warning.log` 是最近一次运行的日志；`logs/runs/<run_id>/` 是每次运行的归档日志。判断某个 Excel 是否由某次运行写出，以该次日志中的 `EXCEL WRITE` 记录为准。业务校验日志默认只打印失败约束和汇总，不打印通过项。
