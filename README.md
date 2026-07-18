# Integrated Mine Management

一体化配矿算法程序。程序读取指定算例目录中的 `智能配矿一体化.xlsx`，搜索烧结、球团活跃物料组合，使用 SciPy SLSQP 求解连续配比，并将核心决策变量写回 Excel。

本文首先说明前后端如何调用程序、如何选择算法及配置参数，代码架构和开发说明放在后半部分。

## 1. 运行准备

### 1.1 安装依赖

建议为项目创建独立 Python 环境，然后在项目根目录安装依赖：

```powershell
python -m pip install -r requirements.txt
```

依赖包括 `numpy`、`scipy` 和 `openpyxl`，具体版本要求见 `requirements.txt`。

### 1.2 工作目录约定

程序当前以“进程工作目录”作为单个算例目录，并固定读取：

```text
<算例目录>/智能配矿一体化.xlsx
```

因此，调用时应把工作目录切换到 Excel 所在目录，再执行项目根目录下的 `main.py`。例如运行 `data/data7`：

```powershell
cd D:\CZY\NeedCopy\Project\integrated_mine_management\data\data7
python ..\..\main.py
```

Linux 调用方式相同：

```bash
cd /path/to/integrated_mine_management/data/data7
python ../../main.py
```

不要直接在项目根目录运行，除非 `智能配矿一体化.xlsx` 就放在项目根目录。后端通过子进程调用时，应把 `cwd` 设置为算例目录，并使用 `main.py` 的绝对路径。

## 2. 两种算法的调用

当前正式提供 `grid` 和 `grasp` 两种外层物料集合搜索策略。两种策略的内层都使用 SciPy SLSQP，依次执行可行性搜索、完整可行性搜索和成本优化。

### 2.1 Grid：规则化邻域搜索 + SLSQP 连续优化

Grid 需要通过参数显式选择：

```powershell
python ..\..\main.py --search-strategy grid
```

Grid 会从以下来源构造少量确定性的活跃物料集合：

- 默认低成本/高铁启发式集合；
- Excel `基准值配比` 中实际使用的物料集合；
- 单位铁成本较低的物料集合；
- TFe 较高的物料集合；
- 围绕上述集合生成的一换一邻域组合。

每个候选集合都交给 SLSQP 求连续配比。相同输入和相同参数下，Grid 通常具有更好的可重复性，适合作为确定性较强的对比策略。

推荐默认调用：

```powershell
python ..\..\main.py --search-strategy grid `
  --active-set-candidate-limit 4 `
  --active-set-time-budget-seconds 85 `
  --initial-maxiter 40 `
  --cost-maxiter 60
```

### 2.2 GRASP：随机贪心构造 + SLSQP 连续优化

GRASP 是当前默认策略。它根据成本、TFe、baseline 使用情况和物料上限构造随机贪心候选，最后对每个候选调用 SLSQP。GRASP 不复用 Grid 的 `heuristic+heuristic`、`baseline+heuristic` 确定性候选，最终结果只在 `grasp:*` 候选中选择。

```powershell
python ..\..\main.py
python ..\..\main.py --search-strategy grasp
```

推荐可重复调用：

```powershell
python ..\..\main.py --search-strategy grasp `
  --grasp-restarts 6 `
  --grasp-rcl-size 3 `
  --grasp-random-seed 42 `
  --active-set-time-budget-seconds 85
```

固定 `--grasp-random-seed` 后，同一输入与同一组参数可以复现候选构造过程。增加重启次数通常能扩大组合覆盖范围，但会增加运行时间。

### 2.3 两种策略对比

| 项目 | `grid` | `grasp` |
|---|---|---|
| 中文说明 | 规则化邻域搜索 + SLSQP 连续优化 | 随机贪心构造 + SLSQP 连续优化 |
| 是否默认 | 否 | 是 |
| 候选来源 | 启发式、baseline、高 TFe、低单位铁成本及一换一邻域 | 多权重随机贪心候选 |
| 可重复性 | 确定性较强 | 固定随机种子后可重复 |
| 主要调节参数 | 候选上限、时间预算 | 重启次数、RCL 大小、随机种子、时间预算 |
| 建议用途 | 确定性较强的对比策略 | 生产默认，扩大随机组合覆盖范围 |

两种策略都不保证一定找到业务可行解。候选比较规则为：优先选择业务可行结果；可行结果之间优先选择铁水成本更低的结果；全部不可行时，依次比较失败约束数量、最大违反量和铁水成本。

## 3. 命令行参数

### 3.1 通用求解参数

| 参数 | 类型 | 默认值 | 作用 | 调整建议 |
|---|---:|---:|---|---|
| `--search-strategy` | 枚举 | `grasp` | 外层搜索策略，可选 `grid`、`grasp` | 前端建议使用下拉框；生产默认选 `grasp` |
| `--active-set-candidate-limit` | 整数 | `4` | Grid 中限制最多评估的活跃集合数量 | 仅影响 Grid；GRASP 的候选规模由 `--grasp-restarts` 控制 |
| `--active-set-time-budget-seconds` | 浮点数 | `85` | 外层搜索软时间预算，单位为秒，Grid 与 GRASP 相同 | 只在候选之间检查，正在执行的单个 SLSQP 不会被强制中断，因此实际耗时可能超过该值 |
| `--initial-maxiter` | 整数 | `40` | 每个候选的可行性阶段和完整可行性阶段的 SLSQP 最大迭代次数 | 难以找到可行解时可提高；会明显增加总耗时 |
| `--cost-maxiter` | 整数 | `60` | 每个可行候选的成本优化阶段最大迭代次数 | 已经可行但成本改善不足时可提高 |
| `--ftol` | 浮点数 | `1e-10` | SLSQP 的目标函数停止精度 | 数值越小要求越严格，通常也越慢；业务约束是否满足仍按 `1e-2` 容忍度判断 |
| `--copy` | 开关 | 关闭 | 不覆盖输入 Excel，改为写出副本 | 后端保留原始上传文件时建议启用 |
| `--output` | 字符串 | 空 | 配合 `--copy` 指定副本文件名 | 单独传入不会生效；未指定时输出 `智能配矿一体化_scipy_cost.xlsx` |

### 3.2 GRASP 专用参数

| 参数 | 类型 | 默认值 | 作用 | 调整建议 |
|---|---:|---:|---|---|
| `--grasp-restarts` | 整数 | `6` | 随机贪心构造的重启次数，也是 GRASP 最多生成的候选数量 | 越大候选越多、耗时越长；重复活跃集合会自动跳过 |
| `--grasp-rcl-size` | 整数 | `3` | RCL（候选限制表）大小，每次从排名靠前的若干物料中随机选择 | `1` 更接近纯贪心；增大后随机性和多样性提高 |
| `--grasp-random-seed` | 整数 | `42` | GRASP 随机种子 | 后端应记录该值，便于复现结果 |

以上三个参数在 `grid` 模式下不会影响结果。

### 3.3 兼容与调试参数

| 参数 | 默认行为 | 说明 |
|---|---|---|
| `--search-active-set` | 已默认启用 | 兼容旧命令，正常接入不需要显式传入 |
| `--no-search-active-set` | 关闭 | 绕过 Grid/GRASP，回退到旧的单活跃集合流程，不建议作为前端正式算法选项 |
| `--quiet-scipy` | 关闭 | 仅对 `--no-search-active-set` 的逐迭代控制台输出有效；Grid/GRASP 默认不打印每次 SLSQP 迭代 |

### 3.4 常用调用示例

默认 GRASP，覆盖输入文件：

```powershell
python ..\..\main.py
```

显式调用 Grid，覆盖输入文件：

```powershell
python ..\..\main.py --search-strategy grid
```

Grid，保留原始文件并输出指定副本：

```powershell
python ..\..\main.py --search-strategy grid --copy --output result.xlsx
```

GRASP，显式指定当前默认搜索参数：

```powershell
python ..\..\main.py --search-strategy grasp `
  --grasp-restarts 6 `
  --grasp-rcl-size 3 `
  --grasp-random-seed 42 `
  --active-set-time-budget-seconds 85
```

## 4. 前后端接入约定

### 4.1 推荐的子进程调用方式

后端应为每次任务创建独立算例目录，把输入文件命名为 `智能配矿一体化.xlsx`，然后使用以下等价调用方式：

```text
executable: <python executable>
arguments:  [<repo>/main.py, --search-strategy, grasp]
cwd:        <case directory>
```

不要让两个进程同时操作同一个算例目录：默认模式会覆盖同一个 Excel，日志也会写入同一个 `logs` 目录。

### 4.2 如何判断结果是否可用

程序在“求解完成但业务约束不满足”时仍会写回 Excel，并正常返回退出码 `0`。因此后端不能只根据退出码判断业务成功，必须解析控制台结果或日志中的业务状态。

Grid/GRASP 最终状态示例：

```text
active_set_search best=... stage=... business_feasible=True failed=0/137 max_business_violation=... hot_metal_cost=...
hot_metal_cost=...
output=./智能配矿一体化.xlsx
```

建议判断规则：

- 进程退出码非 `0`：程序运行异常，未正常完成；
- 出现 `business_feasible=True` 且 `failed=0/...`：结果通过业务约束校验；
- 出现 `business_feasible=False`：Excel 仍已写入，但只能作为不可行结果供排查；
- 出现 `input_precheck failed=...`：输入上下限冲突，程序跳过求解并把三组核心变量全部写为 `0`。

`scipy success=False` 只表示 SciPy 可能达到迭代上限，不等同于业务失败；最终以 `business_feasible` 和 `failed` 为准。

### 4.3 输入预检查和业务行为

程序求解前会检查 `一体化烧结配矿`、`一体化球团配矿` 中所有物料上限之和。任一 Sheet 的上限总和小于 `100` 时，与“配比和等于 100”冲突，程序会：

- 不进入 Grid/GRASP；
- 将烧结配比、球团配比和高炉炉料配比全部写为 `0`；
- 在控制台打印 `input_precheck failed=...`；
- 在日志打印 `INPUT PRECHECK FAILED`。

其他业务约束失败不会阻止写回。程序会写入当前找到的最佳结果，并在控制台和日志中明确提示不可行。

高炉炉料勾选规则会纳入最终业务校验：

- `基准值烧结矿`、`基准值球团矿` 固定不参与决策；
- `一体化烧结矿` 与 `烧结矿` 必须二选一；
- `一体化球团矿` 与 `球团矿` 必须二选一；
- 块矿勾选按 Excel 输入固定。

业务约束统一使用 `1e-2` 容忍度。铁水成本是优化目标，不是硬约束。

### 4.4 Excel 写回规则

默认直接覆盖算例目录中的 `智能配矿一体化.xlsx`。使用 `--copy` 后写入副本。

程序只写回以下核心变量，并保留 4 位小数：

- `一体化烧结配矿` Sheet 的 `一体化配比` 列；
- `一体化球团配矿` Sheet 的 `一体化配比` 列；
- `一体化高炉炉料` Sheet 的 `一体化配比` 列。

其余单元格由 Excel/WPS 公式联动计算。程序会设置工作簿为打开时重算，但 `openpyxl` 本身不执行 Excel 公式。因此后端如果在 Excel/WPS 打开并重算之前直接读取公式单元格，可能读到旧缓存值或空值；算法日志中的 KPI 和约束校验来自 Python 公式计算，不依赖 Excel 重算。

### 4.5 Baseline 的作用

如果 Excel 存在非零 `基准值配比`，程序会先输出 `[BASELINE]` 业务校验，供结果对比。Baseline：

- 不要求本身可行，不会阻止后续求解；
- 不作为 SLSQP 的初始配比；
- 可作为 Grid/GRASP 构造活跃物料候选时的参考；
- 不会读取当前 `一体化配比` 作为候选来源。

如果没有基准值，控制台会输出：

```text
baseline_check skipped=no_baseline_ratios
```

## 5. 日志与结果排查

每个算例目录下会生成：

```text
logs/running_results.log
logs/warning.log
logs/runs/<run_id>/running_results.log
logs/runs/<run_id>/warning.log
```

- `running_results.log`：最近一次运行的完整日志；
- `warning.log`：最近一次运行的警告和失败约束；
- `logs/runs/<run_id>/`：每次运行的归档日志；
- `EXCEL WRITE`：记录本次实际写出的文件、铁水成本和业务可行状态。

业务校验默认只打印失败约束和汇总，不逐条打印通过项。

## 6. 校验脚本

校验脚本同样要求工作目录为算例目录。

检查当前 Excel 方案是否满足所有业务约束：

```powershell
python ..\..\scripts\validate_business_constraints.py
```

核对 Python 公式映射与 Excel 缓存值：

```powershell
$env:PYTHONPATH = (Resolve-Path ..\..)
python ..\..\scripts\validate_excel_snapshot.py
```

Linux：

```bash
PYTHONPATH=../.. python ../../scripts/validate_excel_snapshot.py
```

`validate_excel_snapshot.py` 比较的是 Excel 保存的公式缓存值。如果工作簿刚被 Python 写出但尚未在 Excel/WPS 中打开重算，公式缓存可能为空或过期，此时出现差异不一定代表 Python 公式错误。

只测试 SciPy 求解且不写回 Excel：

```powershell
python ..\..\scripts\benchmark_scipy_no_count.py --mode feasibility
python ..\..\scripts\benchmark_scipy_no_count.py --mode cost
```

## 7. 求解流程

默认 Grid/GRASP 流程如下：

```text
读取 Excel
  -> 输入上限可行性预检查
  -> baseline 约束校验
  -> 外层生成活跃物料集合（Grid 或 GRASP）
  -> 每个候选执行 initial feasibility
  -> 初始可行后执行 full feasibility
  -> 执行 cost optimization
  -> 按业务可行性和铁水成本选出最佳候选
  -> 最终业务约束校验
  -> 写回核心变量和日志
```

物料数量限制当前通过“外层固定活跃物料集合”处理，内层 SLSQP 只求连续配比；当前不是混合整数非线性模型。

## 8. 代码架构

- `main.py`：命令行入口、参数解析、输入预检查、算法路由、最终校验和写回；
- `source/active_set_search.py`：Grid 外层候选生成、候选求解和结果排序；
- `source/grasp_search.py`：纯 GRASP 随机贪心活跃集合构造和结果选择；
- `source/model.py`：SciPy SLSQP 内层模型、变量边界、约束、目标函数和迭代逻辑；
- `source/initial_solution.py`：按上下限和活跃集合生成初始种子，不读取 baseline 作为 warm start；
- `source/input_data.py`：读取 Excel 直接参数并计算间接参数；
- `source/variable_data.py`：根据核心配比计算全部辅助变量和 KPI；
- `source/constraint_checker.py`：统一生成业务约束残差、容忍度判断和校验日志；
- `source/result_storage.py`：将三组核心决策变量写回 Excel；
- `source/domain_object/`：参数、物料等领域对象；
- `source/utils/field.py`：Excel 文件名和 Sheet 名；
- `source/utils/header.py`：Excel 表头字段名；
- `source/utils/log.py`：最近日志和按运行批次归档日志。

## 9. 当前模型边界

- 物料使用个数不是整数变量，由 Grid/GRASP 外层活跃集合搜索处理；
- 内层配比优化使用 SciPy SLSQP；
- 初始解由程序根据上下限生成，不依赖 Excel 当前一体化结果；
- 即使最终业务不可行，仍写回最佳可用结果，前后端必须展示业务校验状态；
- Excel 负责展示公式联动值，Python 负责算法计算、业务校验和核心变量写回。
