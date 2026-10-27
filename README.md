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
| `references/` | 外部论文、精选参考图、写作结构分析及其他外部证据 |
| `manuscripts/` | 作者稿件、候选与采用图、构建说明和投稿归档 |
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

## 参考论文

按 [references/README.md](references/README.md) 收集论文，在 [论文索引](references/papers/INDEX.md) 登记，将单篇模板复制到 `references/papers/<paper-id>/`。一份原文与笔记同时支持摘图和写作结构分析，两种用途可分别整理。

精选图记录原图号、PDF 页码和可借鉴设计；结构笔记分析章节任务、段落推进及对自己稿件的启发。后续绘图或拟定提纲时引用这些记录。

## 论文与图

需要撰写论文时，按 [manuscripts/README.md](manuscripts/README.md) 将稿件模板复制到 `manuscripts/<manuscript>/`，填写正文入口、构建命令、关联代码和实验依据。稿件名可以与代码仓库名不同。

论文源码放在 `source/`，编译产物输出到 `build/`，需要归档的投稿版放在 `release/`。图索引记录论文图号、候选版本、当前采用图及其来源；新图默认生成候选，明确采用后再更新稳定入口。

## Git 与资产管理

外层工作区仓库保存研究文档、实验分析、执行脚本、Run 元数据、配置、指标和必要日志，以及稿件源码、图索引、候选图、采用图和需要长期保存的发布版。`repos/<repo>/` 中的实现代码由各自独立的 Git 仓库管理；其提交与恢复入口应在已有项目或 Experiment 记录中明确。

默认忽略数据集的 `data` 实体或本机链接、Run 的 `output/`、稿件构建产物、本地 `.venvs/`，以及根级 `tmp/`、`output/`、`smoke/`。数据集说明、元数据和处理脚本仍保留；稿件 `build/.gitkeep` 用于保留目录。参考论文的 `paper.pdf` 与 `supplement*.pdf` 默认本地保存，来源和版本记入笔记，索引、笔记与精选参考图仍可跟踪。PDF、CSV、JSON、ZIP 不按扩展名统一忽略，其他外部材料按项目需要设置。

克隆工作区后，独立代码仓库需按项目入口恢复，数据按对应 `DATASET.md` 准备，大型输出和权重按 Experiment 记录的来源恢复。被忽略的本地资产需要单独保存，外层 Git 不构成它们的完整备份。新增忽略规则不会自动取消已跟踪文件的版本管理。
