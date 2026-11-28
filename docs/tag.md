# Tag 工具

与 ComfyUI 生图提示词（Danbooru Tags）生成与扩写相关的 Python 工具库（`ms_toolbox.tag`）。

## 快速上手

```python
from ms_toolbox.tag import TipoRequest, csv2tag, tag2nl

# 1. 读取标签树 CSV，展开所有标签组合 -> list[str]
tag_list = csv2tag("tags.csv")

# 2. 调用本地 TIPO 模型扩写提示词 -> list[str]
requests = [TipoRequest(tags=t) for t in tag_list]
prompts = tag2nl(requests)

for p in prompts:
    print(p)
```

---

## `csv2tag` — CSV 标签树编写规则

`csv2tag(csv_file_path)` 基于**列式邻接表**从 `<root>` 开始深度优先展开所有标签组合，返回 `list[str]`。

### 1. 结构与逻辑规则（OR 与 AND）
- **列代表节点与 OR 分支**：CSV 的每一列表示一个父节点及其子分支。
  - **第 1 行（表头）**：父节点名，整个表必须包含 `<root>` 列作为遍历入口。
  - **第 2 行起**：该父节点的**或（OR）**可选分支（空单元格自动忽略；重复填写同一分支可提高其出现频次/权重）。
- **单元格内逗号代表 AND 组合**：单个单元格内可用英文逗号 `,` 连接多个子标签（如 `"<hidden>审查, 1girl, <hidden>发型"`），程序会依次递归展开每个子标签并做笛卡尔积拼接。
- **普通节点保留自身**：未在表头定义的标签作为叶子节点直接输出；在表头有定义的普通标签（如 `long_hair`）会保留自身，并在其后追加子分支标签（如 `long_hair, ponytail`）。

### 2. 控制节点（`<root>` 与 `<hidden>`）
以 `<root>` 或 `<hidden>` 开头的节点**不会进入最终输出字符串**，仅用于组织树结构：
- **分类节点**（如 `<hidden>审查`、`<hidden>发型`）：写在表头，用于逻辑分组与分流。
- **空分支**（单独的 `<hidden>`）：作为叶子节点时结算为空，表示“跳过/不附加该子特征”。

### 3. 最小示例

输入 `tags.csv`：

```csv
<root>,<hidden>审查,<hidden>发型,long_hair
"<hidden>审查, 1girl, <hidden>发型",safe,short_hair,ponytail
,,short_hair,<hidden>
,,long_hair,
```

`csv2tag("tags.csv")` 返回值：

```python
[
    "safe, 1girl, short_hair",
    "safe, 1girl, short_hair",
    "safe, 1girl, long_hair, ponytail",
    "safe, 1girl, long_hair",
]
```

---

## `tag2nl` — 用 TIPO 扩写提示词

`tag2nl(request: list[TipoRequest]) -> list[str]` 将每条标签请求交给本地 [TIPO](https://huggingface.co/KBlueLeaf/TIPO-500M-ft) 模型扩写，按 1:1 顺序返回扩写后的提示词字符串列表。

### 请求参数（`TipoRequest`）

除 `tags` 必填外，其余参数均有默认值，可按需覆盖：

```python
TipoRequest(
    tags="safe, 1girl, long_hair",
    nl_prompt="",
    black_list="",
    output_format="Both, tag first (recommend)",  # 可选见 tipo_meta.py 中的 DEFAULT_FORMAT
    target_length="long",
    temp=0.5,
    top_p=0.95,
    min_p=0.05,
    top_k=60,
    seed=20090220,
    escape_brackets=False,
)
```

### Worker 环境配置

运行 `tag2nl` 前，需在 `%LOCALAPPDATA%\ms-toolbox\config.yaml` 中指定 `tipo_worker_python_exe`，指向已安装下列依赖的独立 Python（Windows + Conda + CUDA）解释器：

| 库 | 版本 | 说明 |
| --- | --- | --- |
| `tipo-kgen` | 0.3.1 | 扩写核心 |
| `transformers` | 5.20.2 | 官方依赖限制较旧，5.x 实测可用但需额外安装 protobuf |
| `sentencepiece` | 0.2.2 | 解析 `tokenizer.model` |
| `protobuf` | 7.36.2 | transformers 5.x 加载 tokenizer 所需补丁依赖 |
| `tiktoken` | 0.14.0 | 解析失败时的兜底 |
| `torch` | 2.6.0+cu124 | CUDA 推理依赖 |
| `huggingface_hub` | 1.31.0 | 读取本地模型缓存 |
