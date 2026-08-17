# 研究工作区 Agent 指南

本工作区用于跨多个代码仓库开展、执行和记录机器学习研究。

根级指南只负责工作路由和跨层约束。进入具体任务后，应读取对应目录的 README、模板或规范文档，不要在此处寻找全部操作细节。

---

# 开始任务

开始研究任务或恢复中断工作时：

1. 阅读 `docs/CURRENT.md`，了解当前重点、停止位置、下一步和阻塞项。
2. 需要判断研究阶段或整体缺口时，阅读 `docs/PROJECT_STATUS.md`。
3. 根据任务类型使用下方路由，读取对应的局部规则和现有记录。
4. 修改或决策前，先检查已有文档、Experiment、Run、代码、配置和参考资料；存在可靠证据时不要猜测。

简单的工作区维护任务无需强行更新研究状态。

---

# 信息分层

| 层 | 权威内容 |
| --- | --- |
| `docs/` | 当前状态、研究历史和规范研究知识 |
| `datasets/` | 数据集入口、元数据和数据集专用说明 |
| `references/` | 外部论文、补充材料和其他参考证据 |
| `repos/` | 研究代码实现 |
| `experiments/` | 研究问题、Run 汇总、分析和实验结论 |
| `scripts/` | 稳定执行接口与 Experiment 编排 |
| `runs/` | 配置、日志、输出、指标和执行状态 |

同一信息只在其权威层完整记录，其他位置使用路径、Experiment、Run、创新点或提交编号建立索引。

除非现有结构无法合理承载信息，否则不要新建规范 Markdown、额外目录、包装层或状态文件。

---

# 任务路由

| 任务 | 首先阅读 | 主要记录位置 |
| --- | --- | --- |
| 恢复工作、安排近期任务 | `docs/CURRENT.md`、`docs/PROJECT_STATUS.md` | `docs/CURRENT.md` |
| 管理研究文档 | `docs/README.md` | `docs/` 下对应文档 |
| 梳理研究问题、背景或相关路线 | `docs/README.md`、`docs/research/RESEARCH_BASIS.md` | `RESEARCH_BASIS.md` |
| 确定数据与评估协议 | `docs/README.md`、`docs/research/DATA_PROTOCOL.md` | `DATA_PROTOCOL.md` |
| 添加或使用数据集 | `datasets/README.md`、对应 `DATASET.md` | 对应数据集目录；必要时同步 `DATA_PROTOCOL.md` |
| 复现或分析基线 | `docs/research/BASELINE.md`、`experiments/README.md` | `BASELINE.md` 和对应 Experiment |
| 开发或验证创新点 | `docs/research/METHOD.md`、`experiments/README.md` | `METHOD.md` 和对应 Experiment |
| 创建、执行或分析 Experiment | `experiments/README.md`、对应 `EXPERIMENT.md` | 对应 Experiment |
| 创建运行接口、注册或派发 Run | `scripts/README.md`、`runs/README.md`、对应 Experiment | `scripts/` 和规范 Run 目录 |
| 查询执行状态或检查结果 | `runs/README.md`、对应 `run.json` 和输出 | Run 保存执行事实；Experiment 保存分析 |
| 规划正式实验和论文证据 | `docs/research/EXPERIMENT_PLAN.md`、相关方法与协议文档 | `EXPERIMENT_PLAN.md` |
| 修改仓库代码 | 仓库内的 `AGENTS.md`、README 和开发说明；若由实验驱动，再读对应 Experiment | 对应 `repos/<repo>` |
| 形成临时分析或任务报告 | `docs/README.md` | `docs/reports/` |

局部文档负责具体格式、命名、命令和执行步骤。根级指南与局部说明冲突时，优先遵守适用范围更具体且与当前结构一致的规则；无法判断时先核对实际文件和已有记录。

---

# 核心工作流

研究通常沿以下阶段推进：

```text
研究基础
    ↓
数据与评估
    ↓
基线与问题验证
    ↓
方法开发与初步验证
    ↓
完整方法与正式实验证据
    ↓
论文就绪
```

研究可以迭代回退。新证据推翻旧假设时，应修正当前结论并保留演进记录，不要为了维持进度而忽略冲突。

实验的基本追溯链为：

```text
研究问题 / 创新点 / 正式证据需求
    ↓
Experiment
    ↓
Git 提交 + 执行脚本
    ↓
Run(s)
    ↓
结果、分析和结论
    ↓
规范研究文档
```

跨层必须保持以下约束：

* 一个 Experiment 回答一个明确的研究问题。
* 一个 Run 是最小可执行单位；全部 Run 应在派发前注册。
* 有效 Experiment 应绑定明确的 Git 提交，不要基于未提交的代码生成有效研究结果。
* `runs/` 保存执行事实，`experiments/` 保存实验分析，`docs/research/` 保存提炼后的稳定研究知识，`scripts/` 不写研究结论。
* 已产生有效结果后，不要静默替换代码版本、Run 或历史结论；按局部规则保留旧证据并创建可追溯的新记录。

具体的 Experiment 粒度、命名、注册、远程派发、状态查询、结果回收和 Run 生命周期，以 `experiments/README.md`、`scripts/README.md` 和 `runs/README.md` 为准。

---

# 研究文档自动同步

当任务形成或改变持久研究状态时，文档同步属于任务的一部分。结束任务前应主动更新受影响的现有文档，但不要机械修改无关文件。

| 事件 | 更新位置 |
| --- | --- |
| Experiment 被创建、完成、判定无效或得出有意义结论 | 对应 `EXPERIMENT.md` |
| 研究基础、数据协议、基线、方法或正式证据形成稳定认识 | `docs/research/` 下对应规范文档 |
| 创新点状态或完整方法组成变化 | `METHOD.md`，并同步 `PROJECT_STATUS.md` 中对应条目 |
| 项目阶段或成熟度发生实质变化 | `PROJECT_STATUS.md` |
| 当前重点、停止位置、下一步或阻塞项变化 | `CURRENT.md` |
| 出现影响后续研究理解的重要结论、决策、方向变化或里程碑 | 向 `RESEARCH_LOG.md` 追加简洁条目 |

一次事件涉及多个文档时，通常按以下顺序更新：

```text
EXPERIMENT.md
    ↓
对应规范研究文档
    ↓
PROJECT_STATUS.md（仅在成熟度变化时）
    ↓
RESEARCH_LOG.md（仅记录长期重要事件）
    ↓
CURRENT.md（更新接下来的工作）
```

不要为普通命令、每个 Run、单项指标、临时编辑、短暂失败或仅处于 `pending/running` 的状态追加研究日志。`RESEARCH_LOG.md` 仅允许追加，不得重写已有条目。

没有足够证据时，不要提前勾选 `PROJECT_STATUS.md`；不确定的结论应明确标记为待验证。

---

# 证据与交付原则

始终区分：

* 计划与已经执行的事实；
* 预期行为与观察到的现象；
* 实验结果与从结果提炼出的研究结论；
* 方法说明与实现正确性的证据。

重要主张应能够追溯到：

```text
规范研究文档
    ↓
EXPERIMENT.md
    ↓
Run(s)
    ↓
Git 提交 + 生效配置 + 日志 + 输出
```

完成任务前：

1. 验证结果是否满足当前请求。
2. 按自动同步规则更新真正受影响的记录。
3. 确认没有把计划写成事实，也没有覆盖仍需保留的研究历史。
4. 向用户简要说明完成内容、验证情况和仍存在的阻塞。

不确定具体做法时，读取与目标目录最接近的 README 和已有示例，不要自行发明新的工作区协议。
