# Run 执行记录

此目录存放 Experiment 产生的实际执行记录。

一个 Run 代表某个 Experiment 下的一种具体执行条件。

Run 用于存储执行事实。研究层面的解释和结论应写入对应的 `EXPERIMENT.md`。

## 目录结构

```text
runs/
└── <repo>/
    └── E###-<type>-<name>/
        ├── R001-<condition>/
        │   ├── run.json
        │   ├── config/
        │   ├── stdout.log
        │   ├── stderr.log
        │   ├── metrics.json
        │   └── output/
        ├── R002-<condition>/
        └── ...
```

如果 Run 不会产生有意义的结构化评估指标，则 `metrics.json` 是可选的。

## Run 粒度

一个 Run 代表某个 Experiment 的一种具体执行条件。

实验变量的不同取值、不同数据集、不同随机种子或重复执行，通常都应产生不同的 Run。

Run ID 使用：

```text
R001
R002
R003
...
```

目录名称应遵循：

```text
R###-<short-condition>
```

条件名称应保持简洁。详细配置应写入 `config/` 和 `run.json`。

不要在 `experiments/` 下创建 Run 目录。

所有 Run 必须在执行前由 Experiment 的 `register.sh` 统一注册。注册时显式指定 `R###`，远程服务器不得在执行时自行分配 Run ID。

## run.json

`run.json` 是 Run 的标准执行记录。

它应包含识别和监控执行过程所需的信息，包括：

* Run ID；
* 完整 Run 目录名称；
* Experiment ID；
* Git 提交；
* 执行状态；
* 实际命令及其参数数组；
* 配置来源；
* 配置快照和 runner/adapter 指纹；
* 远程派发服务器、服务器脚本及脚本指纹；
* 请求的资源；
* 执行主机；
* 相关时的 GPU 或设备信息；
* 开始时间；
* 结束时间；
* 退出码；
* 失败原因和人工收敛时间（如适用）。

其中 `resources_requested` 是注册时保存的声明性需求，不表示资源已经被预留或由调度器自动强制执行；它应由派发前的资源检查和服务器脚本分配共同落实。

推荐的状态值：

```text
pending
running
done
failed
```

`run.json` 应由运行器创建和更新，而不是手动维护。

`run.py register` 创建 `pending` 记录，并将配置和当时的 runner/adapter 保存到 `config/`（内部执行快照位于 `config/_execution/`），同时记录 SHA256 指纹；远程 prepare 会保存并记录服务器脚本快照。`run.py execute` 会先验证注册阶段的执行定义没有变化，再读取保存的命令并更新 `running`、`done` 或 `failed`。执行阶段不得修改注册时确定的命令、commit、配置或执行接口。

## config/

`config/` 存储该 Run 注册时的配置快照。

优先存储最终生效的配置，而不是只记录基础配置和覆盖项。

在可行时保留仓库原生的配置格式。

示例：

```text
config/
├── config.yaml
└── _execution/
    └── runner/
```

或者：

```text
config/
├── model.yaml
├── dataset.yaml
├── train.yaml
└── _execution/
    ├── runner/
    └── server/       # 远程派发后出现
```

`_execution/` 由 runner 和远程派发工具维护，不要手工编辑，也不要在仓库配置中使用这个保留名称。

运行前，runner 会确认配置来源与快照均和注册时一致。adapter 应从 `RUN_CONFIG_DIR` 使用这些快照；如果框架在运行时生成最终解析配置，还应将该配置写入 `RUN_CONFIG_DIR/effective/`，不要覆盖原始快照。

## stdout.log

存储执行过程中产生的标准输出。

运行器应将进程输出写入此处，以便无需在原始仓库中搜索就能检查实验进度。

## stderr.log

存储执行过程中产生的标准错误。

故障和诊断信息应始终与对应的 Run 关联。

## metrics.json

当存在有意义的结构化评估结果时，在 `metrics.json` 中存储简明的机器可读总结。

指标名称和值由任务决定，不应强行套用统一模式。

示例：

```json
{
  "metric_a": 0.0,
  "metric_b": 0.0
}
```

不要仅为了填充此文件而人为创建指标。不适用时可省略 `metrics.json`。

## output/

`output/` 包含原始仓库产生的持久化实验产物。

将其内部布局视为黑盒。

其中可能包括检查点、预测结果、中间结果、仓库原生日志、图片或其他生成产物。

工作区不规范 `output/` 的内部结构。

运行器或仓库适配器应确保能够在对应 Run 下找到持久化输出，而不是仅将它们留在仓库内任意的结果目录中。

## Run 生命周期

Run 在 Experiment 派发前完成注册：

```text
register.sh
   ↓
pending
   ↓
running
   ↓
done
```

或者：

```text
pending
   ↓
running
   ↓
failed
```

运行器负责在此生命周期中更新 `run.json`。

失败的 Run 仍是执行记录的一部分，通常不应仅因失败而删除。

Run 一旦达到 `done` 或 `failed`，不应再次执行同一个 Run ID。需要重复执行时应注册新的 Run。

如果服务器重启、进程被外部终止或其他异常导致 Run 长期停留在 `running`，应先确认原进程已经不存在，再使用 `run.py mark-failed` 显式记录失败原因。不要通过手工编辑 `run.json` 将其重置为 `pending`，也不要重新执行同一个 Run ID。

远程执行时，中央工作区先将已注册 Run 同步到指定服务器。远程 `run.py execute` 更新该服务器上的 `run.json`；`status.sh` 按需通过 SSH 查询，`collect.sh` 在执行结束后将规范 Run 目录回收到中央工作区。本工作区不持续轮询远程状态。

## 创建规则

* 仅在对应的 Experiment 下创建 Run。
* 在 `experiments/` 和 `runs/` 下使用相同的 Experiment 目录名称。
* 在每个 Experiment 内按顺序使用 `R###` 标识符。
* 在派发前注册全部 Run，并保持 Run ID 在所有服务器上一致。
* 将实际执行元数据存储在 `run.json` 中。
* 将生效配置的快照保存到 `config/`。
* 在 Run 层面捕获标准输出和标准错误。
* 将仓库生成的持久化产物保留在 `output/` 下。
* 仅在存在有意义的结构化指标时使用 `metrics.json`。
* 不要将研究分析或结论放入 Run 中。
* 除非是在修正明显无效的元数据，否则不要手动修改已完成的 Run 记录。
* 当失败的 Run 有助于追溯执行过程时，予以保留。
* 不要在 Experiment 的 Run 根目录中创建额外的派发计划、任务清单、包装脚本或状态文件。

## 核心原则

```text
Experiment = 研究问题与结论
Run        = 具体执行事实
```

任何已完成的研究结论都应能够从 `EXPERIMENT.md` 追溯到产生支持性证据的 Run。
