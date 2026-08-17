# Agent-native 科研工作区

这个工作区用于组织机器学习研究中的长期上下文、代码、数据、实验执行和可追溯证据。核心关系是：

```text
研究问题 → Experiment → Run → 结果与分析 → 稳定研究结论
```

## 目录

| 目录 | 用途 |
| --- | --- |
| `docs/` | 当前状态、研究历史和规范研究文档 |
| `datasets/` | 数据集入口、元数据和数据集专用脚本 |
| `references/` | 论文及其他外部证据 |
| `repos/` | 实际研究代码仓库 |
| `experiments/` | 实验问题、Run 汇总、分析和结论 |
| `scripts/` | 仓库执行接口、Run 注册和远程派发 |
| `runs/` | 配置、日志、输出、指标和执行状态 |

## 首次使用

1. 阅读 `AGENTS.md`；恢复已有项目时再阅读 `docs/CURRENT.md` 和 `docs/PROJECT_STATUS.md`。
2. 将研究代码放入 `repos/<repo>/`，并确保它是可提交、可复现的 Git 仓库。
3. 按 `datasets/README.md` 准备所需数据集；不需要工作区管理的数据可跳过。
4. 按 `scripts/README.md` 从模板创建 `scripts/<repo>/runner/`，配置 `adapter.sh`。
5. 按 `experiments/README.md` 创建 Experiment、固定代码提交并注册 Run。
6. 本地执行 Run，或在配置服务器后检查资源、生成 GPU 队列并远程派发。
7. 将执行事实保留在 `runs/`，实验分析写回 `EXPERIMENT.md`，稳定结论再提炼到 `docs/research/`。

具体格式和命令由目标目录中的 README 负责；根级 `AGENTS.md` 只负责任务路由和跨层约束。
