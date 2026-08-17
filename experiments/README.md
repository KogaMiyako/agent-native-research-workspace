# 实验

此目录管理从规划到初步结论的研究实验。

一个 Experiment 代表一个具体的研究问题，并将其代码版本、执行脚本、Run、结果和分析关联起来。

## 目录结构

```text
experiments/
├── README.md
├── _template/
│   └── EXPERIMENT.md
└── <repo>/
    ├── E001-<type>-<name>/
    │   └── EXPERIMENT.md
    └── ...
```

相关资源使用相同的 Experiment ID：

```text
scripts/<repo>/experiments/E001-<type>-<name>/
├── register.sh
├── dispatch.sh
├── status.sh
├── collect.sh
└── servers/
    └── <server>.sh

runs/<repo>/E001-<type>-<name>/
├── R001-<condition>/
├── R002-<condition>/
└── ...
```

## Experiment 粒度

一个 Experiment 应回答一个具体问题。

当研究问题或主要实验变量发生变化时，应创建新的 Experiment。

用于回答同一问题的不同取值或条件，应归入同一 Experiment 下的不同 Run。

例如：

```text
E003-param-topk
→ 研究 top-k 的影响

R001-k50
R002-k100
R003-k200
```

测试另一个参数时，应创建另一个 Experiment。

用于回答同一问题的不同随机种子、重复执行或多个数据集，通常不需要创建新的 Experiment。

## 命名

使用：

```text
E###-<type>-<short-name>
```

推荐类型：

* `rep` — 复现
* `try` — 探索性方法试验
* `param` — 参数研究
* `abl` — 消融研究
* `ana` — 机制或结果分析
* `main` — 正式主实验

示例：

```text
E001-rep-baseline
E002-try-adaptive-gate
E003-param-topk
E004-abl-retrieval
E005-ana-attention
```

`E###` 是唯一标识符。其余名称应简短且具有描述性。

## 创建 Experiment

创建新的 Experiment 时：

1. 在对应仓库下分配下一个 `E###`。
2. 创建 `experiments/<repo>/E###-<type>-<name>/`。
3. 将 `_template/EXPERIMENT.md` 复制到该目录。
4. 完善“目的”章节。
5. 准备实验所需的实现。
6. 提交仓库。
7. 在 `EXPERIMENT.md` 中记录确切的 Git 提交。
8. 从 `scripts/_template/experiments/E###/` 创建对应的 Experiment 脚本目录。
9. 在 `register.sh` 中定义并注册全部 Run。
10. 使用 `status.py` 确认全部 Run 均为 `pending`。
11. 对照各 Run 在 `run.json` 中声明的资源需求检查服务器和 GPU，由 Agent 在 `servers/<server>.sh` 的 `GPU_QUEUES` 中生成 Run 队列；资源字段仅用于规划，不代表已经预留。
12. 在 `dispatch.sh` 中登记服务器与脚本并执行；派发前必须通过全部 `pending` Run 恰好分配一次的校验。
13. 按需执行 `status.sh` 查询远程状态。
14. 远程执行结束后执行 `collect.sh` 回收结果。
15. 返回 `EXPERIMENT.md`，完善“结果”“分析”和“结论”章节。

Run 必须在派发前统一注册。远程服务器只执行已经注册的 Run，不得自行分配新的 `R###`。

## 代码版本规则

一个 Experiment 通常应对应一个有效的 Git 提交。

在启动有效的实验 Run 之前：

* 完成所需的代码变更；
* 提交仓库；
* 在 `EXPERIMENT.md` 中记录该提交；
* 注册全部 Run；
* 然后执行对应的派发脚本。

如果某个缺陷导致实验无法产生有效结果：

* 修复缺陷；
* 创建新提交；
* 更新现有 `EXPERIMENT.md` 中的 Git 提交；
* 如有必要，更新对应的 Experiment 执行脚本；
* 继续使用同一个 Experiment。

如果已经产生了有效结果，而之后发现的缺陷可能影响这些结果：

* 保留原始 Experiment 和 Run；
* 在原始 `EXPERIMENT.md` 中标记受影响的结果或结论；
* 修复缺陷并创建新提交；
* 创建新的 Experiment；
* 使用新的 Experiment ID 重新运行修正后的实验。

产生有效结果后，不要静默替换 Experiment 的代码版本。

## 完成 Experiment

进程结束并不代表 Experiment 已经完成。

所需 Run 完成后：

* 在 `EXPERIMENT.md` 中汇总相关结果；
* 进行回答原始问题所需的分析；
* 在有用时检查模块行为或内部证据；
* 写出直接的初步结论。

原始执行信息保留在 `runs/` 中。之后可将稳定的研究结论提炼到 `docs/research/` 下的规范文档中。

## 创建规则

* 始终从 `_template/EXPERIMENT.md` 创建新的 Experiment。
* 一个 Experiment 回答一个具体问题。
* 每个 Experiment 使用一个主要实验变量。
* 在 `experiments/`、`scripts/` 和 `runs/` 中使用相同的 Experiment ID。
* 不要在 `experiments/` 下创建 `R###` 目录。
* 在执行或远程派发前注册全部 Run。
* Run ID 由 `register.sh` 显式指定，不在远程执行时动态生成。
* 服务器脚本中的 `GPU_QUEUES` 是任务分配的唯一来源；所有当前 `pending` Run 必须恰好出现一次。
* 已被 Run 的 `dispatch_snapshot` 引用的服务器脚本不得改写；重试或补充派发使用新的服务器脚本文件。
* 一台服务器使用一个服务器脚本，不要为每个 Run 创建单独脚本。
* 不要在运行时生成额外的派发计划、包装脚本或状态文件。
* 在产生有效实验结果前提交仓库。
* 不要在一个 Experiment 中混用存在实质差异的代码版本。
* 注册后不要修改 runner、adapter 或配置来源并继续执行原 Run；执行接口或配置变化时注册新的 Run。
* Run 结束后，返回 `EXPERIMENT.md` 完成实验记录。
* 将已完成和已废弃的 Experiment 作为研究历史保留。
* 除非确有必要，否则不要在 Experiment 内创建额外的 Markdown 文件。
