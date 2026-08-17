# 数据集管理

此目录用于管理整个研究工作区共享的数据集。

## 目录结构

```
datasets/
├── README.md
├── _template/
│   ├── DATASET.md
│   ├── meta_time_series.json
│   ├── meta_image.json
│   ├── meta_video.json
│   ├── meta_audio.json
│   ├── meta_text.json
│   ├── meta_multimodal.json
│   └── scripts/
│       └── profile.py
└── <dataset>/
    ├── DATASET.md
    ├── metadata.json
    ├── scripts/
    └── data/
```

每个数据集都作为独立的数据集组件进行维护。

* `DATASET.md`：数据集特有的布局、来源、划分、预处理和使用信息。
* `metadata.json`：机器可读的数据集概况和统计信息。
* `scripts/`：数据集特有的获取、分析、转换或预处理脚本。
* `data/`：实际数据集的规范访问入口。

`data/` 的内部结构由具体数据集决定，工作区不对其进行统一规范。

## 规范访问方式

使用：

`datasets/<dataset>/data/`

作为数据集的规范入口。

`data/` 可以是本地目录，也可以是指向当前机器上实际存储位置的符号链接。

工作区级实验和脚本应尽可能使用规范路径，而不是与特定机器绑定的绝对路径。

## 使用数据集

已验证且未发生变化的数据集设置可以重复使用。

需要确认布局、划分、预处理、产物含义或数据集特有要求时，请阅读 `DATASET.md`。

需要精确统计信息或机器可读属性时，请使用 `metadata.json`。

## 添加数据集

从 `_template/` 初始化新数据集：

1. 创建 `datasets/<dataset>/`。
2. 复制 `_template/DATASET.md`。
3. 选择与主要模态匹配的 `_template/meta_<modality>.json`，并将其复制为 `metadata.json`。
4. 复制 `_template/scripts/profile.py`。
5. 创建规范的 `data/` 入口。
6. 完善 `DATASET.md`。
7. 调整并运行 `scripts/profile.py`，补充 `metadata.json` 中的统计信息。未经适配的模板只更新通用统计，不会自动推断模态特有字段。
8. 仅在需要时添加其他数据集专用脚本。

元数据模板只是起点，可根据需要添加数据集特有的统计信息。

不要因为单个数据集的特有要求而修改 `_template/`。

## 数据集分析

`metadata.json` 应主要包含可度量的数据集事实，而不是描述性文档。

在适用时，应收集常见统计信息，包括：

* 样本总数；
* 各划分的大小；
* 磁盘占用；
* 缺失数据统计；
* 目标值或标签统计。

各模态专用模板定义了每种数据类型的推荐统计项。

可复用的分析逻辑应维护在 `scripts/profile.py` 中。

在可行时应分析完整数据集。如果统计信息是从子集估算的，请让适配后的采集函数实际遵守 `mode` 和 `sample_size`，并在 `metadata.json` 中记录分析模式和样本数量。

## 更新数据集

当可复用的数据产物或处理流程发生变化时：

* 布局、划分、预处理或用法发生变化时，更新 `DATASET.md`；
* 可度量事实发生变化时，重新生成或更新 `metadata.json`；
* 将可复用的数据集专用处理代码保留在 `scripts/` 下。

避免产生未记录的数据集副本、划分或处理后产物。

## 工作区特有约定

\<!-- 需要时在此处添加项目特有的数据集管理约定。 -->
