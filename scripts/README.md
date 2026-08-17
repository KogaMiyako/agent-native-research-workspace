# 实验执行脚本

此目录提供稳定的 Run 生命周期、Experiment 执行入口和简化的多服务器远程操作。

核心原则：

```text
Experiment 脚本 → 定义和分配 Run
run.py           → 注册、校验分配、执行或收敛一个 Run
adapter.sh       → 调用仓库原生入口
status.py        → 读取 run.json
remote.py        → 按需检查、同步、启动、查询、回收和异常收敛
```

Run 是最小可执行单位。一个 Experiment 必须先注册全部 Run，之后才能本地执行或分配到远程服务器。

---

## 目录结构

```text
scripts/
├── README.md
├── remote/
│   ├── servers.json
│   └── remote.py
├── _template/
│   ├── runner/
│   │   ├── run.py
│   │   ├── adapter.sh
│   │   └── status.py
│   └── experiments/
│       └── E###/
│           ├── register.sh
│           ├── dispatch.sh
│           ├── status.sh
│           ├── collect.sh
│           └── servers/
│               └── SERVER.sh
└── <repo>/
    ├── runner/
    │   ├── run.py
    │   ├── adapter.sh
    │   └── status.py
    └── experiments/
        └── E###-<type>-<name>/
            ├── register.sh
            ├── dispatch.sh
            ├── status.sh
            ├── collect.sh
            └── servers/
                ├── server-a.sh
                └── server-b.sh
```

不要为每个 Run 创建单独脚本。一台服务器使用一个服务器脚本，其中每张 GPU 对应一条顺序 Run 队列。

---

## 为仓库创建执行接口

首次接入仓库时：

1. 将 `_template/runner/` 复制到 `scripts/<repo>/runner/`；
2. 修改 `adapter.sh`，使其调用仓库原生训练、评估或分析入口；
3. 保持 `run.py` 和 `status.py` 通用，除非工作区协议本身发生变化；
4. 确保 `repos/<repo>` 是干净的 Git 工作树；
5. 确保 `EXPERIMENT.md` 中记录了确切的 Git commit。

`adapter.sh` 可以读取以下环境变量：

```text
WORKSPACE_ROOT
REPO_ROOT
EXPERIMENT_ID
RUN_ID
RUN_NAME
RUN_DIR
RUN_OUTPUT_DIR
RUN_CONFIG_DIR
```

仓库需要持久保存的输出必须写入或收集到 `RUN_OUTPUT_DIR`。配置应从 `RUN_CONFIG_DIR` 中的注册快照读取；如果运行时生成最终解析配置，应写入 `RUN_CONFIG_DIR/effective/`，不要覆盖原始快照。

注册时会记录整个 `scripts/<repo>/runner/` 目录的 SHA256 指纹。注册后修改 `run.py`、`adapter.sh` 或同目录下的其他执行文件，会导致已有 `pending` Run 拒绝执行；此时应注册新的 Run。

---

## 创建 Experiment 执行目录

创建新的 Experiment 时，将：

```text
scripts/_template/experiments/E###/
```

完整复制为：

```text
scripts/<repo>/experiments/E###-<type>-<name>/
```

然后：

1. 在 `register.sh` 中定义全部 Run；
2. 执行 `register.sh`；
3. 配置 `scripts/remote/servers.json`；
4. 让 Agent 检查候选服务器和 GPU；
5. 根据检查结果，将 `SERVER.sh` 替换为实际的服务器脚本，并填写其中的 `GPU_QUEUES`；
6. 在 `dispatch.sh` 中填写对应的服务器和服务器脚本；
7. 删除未使用的 `SERVER.sh` 占位模板；
8. 执行 `dispatch.sh`。

Experiment 脚本目录是本次实验实际执行分配的持久记录，不要在运行过程中额外生成派发计划、任务清单或包装脚本。

---

## Run 注册

`run.py register` 只创建 Run，不启动命令。

示例：

```bash
python scripts/<repo>/runner/run.py register \
    --experiment E001-rep-baseline \
    --run-id R001 \
    --name dataset-a-seed1 \
    --gpus 1 \
    --min-gpu-memory-mb 20000 \
    --config repos/<repo>/configs/baseline.yaml \
    -- \
    scripts/<repo>/runner/adapter.sh \
    --dataset dataset-a \
    --seed 1
```

注册后生成：

```text
runs/<repo>/E001-rep-baseline/
└── R001-dataset-a-seed1/
    ├── run.json
    ├── config/
    └── output/
```

此时 `run.json` 状态为 `pending`，并已记录配置快照、配置内容指纹和 runner/adapter 指纹。

Run ID 必须由 `register.sh` 显式指定。重复注册完全相同的定义是安全的；如果同一 Run ID 的名称、命令、commit、配置来源或资源需求不同，注册会失败，不会覆盖已有记录。

`--gpus`、`--min-gpu-memory-mb`、`--cpus` 和 `--memory-gb` 是写入 `run.json` 的声明性资源需求，用于 Agent 检查资源和规划队列；当前简化派发器不会自动预留资源，也不会根据这些字段自动选择服务器或阻止超额分配。派发前必须将它们与实际服务器检查结果核对。默认 `SERVER.sh` 面向“每个 Run 使用一张可见 GPU”；CPU-only 或单个 Run 跨多 GPU 的实验需要按仓库启动方式调整服务器脚本，但仍须保留 `--list-runs` 和 Run 唯一分配校验。

---

## Run 执行

`run.py execute` 只执行已经注册且状态为 `pending` 的 Run：

```bash
python scripts/<repo>/runner/run.py execute \
    --experiment E001-rep-baseline \
    --run-id R001
```

状态变化：

```text
pending
   ↓
running
   ↓
done / failed
```

执行时会创建：

```text
stdout.log
stderr.log
```

并更新 `run.json` 中的：

```text
host
device
started_at
finished_at
exit_code
status
```

Run 一旦执行完成，不应再次执行同一个 Run ID。需要重新执行时注册新的 Run。

---

## 本地多 GPU 执行

服务器脚本使用唯一的 `GPU_QUEUES` 定义任务分配：

```bash
GPU_QUEUES=(
    "0:R001 R004"
    "1:R002 R005"
)
```

含义：

```text
GPU 0 → 顺序执行 R001、R004
GPU 1 → 顺序执行 R002、R005
```

不同 GPU 并行，同一 GPU 内顺序执行。某个 Run 失败后，服务器脚本会记录失败并继续该 GPU 队列中的后续 Run。

`dispatch.sh` 直接从各服务器脚本读取 Run，不再维护第二份 Run 列表。派发前会验证所有当前 `pending` Run 均被分配且恰好出现一次，同时拒绝遗漏、重复、未知或状态非 `pending` 的 Run；已经结束的历史 Run 不会再次进入分配。

---

## 服务器配置

在 `scripts/remote/servers.json` 中配置允许使用的服务器：

```json
{
  "servers": [
    {
      "name": "server-a",
      "ssh": "researcher@server-a",
      "workspace": "/data/research/workspace",
      "python": "/opt/conda/envs/research/bin/python"
    }
  ]
}
```

字段：

* `name`：Experiment 脚本使用的稳定名称；
* `ssh`：传给 `ssh` 和 `rsync` 的目标；
* `workspace`：远程工作区绝对路径；
* `python`：远程环境中的 Python 可执行文件。

不要在该文件中保存密码或私钥。

---

## 远程检查与派发

`dispatch.sh` 先对所有选定服务器执行一次检查。检查内容包括：

* SSH 是否可达；
* 远程 workspace 和 repo 是否存在；
* repo HEAD 是否与 `EXPERIMENT.md` 一致；
* repo 是否有未提交修改；
* 指定的数据集入口是否存在；
* Python 是否可用；
* 磁盘空间；
* GPU 型号、空闲显存和利用率。

GPU 信息优先使用 `nvidia-smi`；如果该命令缺失或不可用，则使用服务器配置中指定的 Python，通过 PyTorch 检查 CUDA 可用性和设备显存。两种方式都无法确认可用 GPU 时，检查失败，不继续派发。

检查通过后，`dispatch.sh`：

1. 同步 runner、adapter 和 `EXPERIMENT.md`；
2. 只同步该服务器负责的已注册 Run；
3. 上传该服务器的执行脚本；
4. 通过 SSH 和 `nohup` 启动服务器脚本。

prepare 时会把服务器、脚本名称和脚本 SHA256 写入相应 Run 的 `dispatch_snapshot`，并把脚本快照保存到 Run 的 `config/_execution/server/`。启动前会再次校验远端脚本指纹并执行 Bash 语法检查，随后在启动后一秒进行一次存活检查。这不是持续轮询，只用于尽早发现脚本被替换、配置错误或启动失败。

服务器脚本一旦写入某个 Run 的 `dispatch_snapshot`，就不应再改写。重试或补充 Run 时应创建新的服务器脚本文件，并让 `dispatch.sh` 指向新的脚本；旧脚本继续保留以便追溯。

如果远程已存在同一 Run，远程工具会验证注册定义并保留已有 `run.json`，不会用中央的 `pending` 状态覆盖远程结果。已完成或失败的 Run 也不会被 `run.py execute` 再次执行。

本框架不预留 GPU，也不持续轮询。Agent 应在派发前读取检查结果，立即生成并执行分配。如果 GPU 在检查后被其他任务占用，相关 Run 可能失败；不要自动等待或抢占资源。

---

## 按需查询远程状态

执行：

```bash
bash scripts/<repo>/experiments/E001-rep-baseline/status.sh
```

它只在调用时通过 SSH 运行远程 `status.py`，不会启动常驻进程或定时轮询。

本地 `status.py` 只读取本地已回收的 `run.json`：

```bash
python scripts/<repo>/runner/status.py E001-rep-baseline
python scripts/<repo>/runner/status.py --all
```

---

## 回收远程结果

执行：

```bash
bash scripts/<repo>/experiments/E001-rep-baseline/collect.sh
```

它按照 `dispatch.sh` 中记录的服务器与 Run 分配，通过 `rsync` 将对应 Run 目录同步回中央工作区。

回收内容只使用规范 Run 结构：

```text
run.json
config/
stdout.log
stderr.log
metrics.json
output/
```

`metrics.json` 仍为可选。回收操作不会删除远程结果；确认中央结果完整后，如需清理远程文件，应显式进行。

---

## 异常中断处理

如果服务器重启或进程被外部终止，Run 可能停留在 `running`。确认原进程已经不存在后，可在远程服务器上显式标记失败：

```bash
python scripts/remote/remote.py mark-failed \
    --server server-a \
    --repo <repo> \
    --experiment E001-rep-baseline \
    --run R001 \
    --reason "server rebooted"
```

随后执行 `collect.sh` 回收更新后的 `run.json`。需要重新执行时注册新的 Run ID；不要把旧 Run 手工改回 `pending`。

---

## 完整执行顺序

```text
创建 EXPERIMENT.md
    ↓
准备代码并固定 Git commit
    ↓
从模板创建 Experiment 脚本目录
    ↓
填写并执行 register.sh
    ↓
本地 status.py 确认全部 Run 为 pending
    ↓
检查候选服务器资源
    ↓
Agent 生成每台服务器的 GPU Run 队列
    ↓
填写服务器脚本的 GPU_QUEUES，并在 dispatch.sh 中登记服务器与脚本
    ↓
执行 dispatch.sh
    ↓
需要时执行 status.sh
    ↓
远程完成后执行 collect.sh
    ↓
本地 status.py 检查最终状态
    ↓
返回 EXPERIMENT.md 汇总、分析和结论
```

不要将研究结论写入脚本或 Run 目录。
