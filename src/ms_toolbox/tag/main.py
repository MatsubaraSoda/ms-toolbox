from argparse import ArgumentParser, RawDescriptionHelpFormatter
from pathlib import Path
from ms_toolbox.tag.core import tag_csv2str, tag_tag2nl, TipoRequest
import json
import sys
import random

def cli_tag_csv2str():
    """解析参数并调用标签组合生成的核心逻辑。"""
    parser = ArgumentParser(
        description=r"""
# tag-csv2str

基于列式邻接表（Column-based Adjacency List）读取标签树 CSV，遍历生成所有可能的标签组合，结果直接输出到标准输出（stdout，JSON Lines 格式）。

## CSV 数据结构规范（列优先）
CSV 的**每一列**表示一个节点及其所有可选子分支：
- **第 1 行（表头）**：父节点名称（Parent Key）。整个 CSV 必须且只能有一列表头为 `<root>` 作为遍历入口。
- **第 2 行及后续行**：该父节点的可选分支单元格（Children Branches）。
  - 同一列下存在多个非空单元格时，代表**或（OR）**的互斥选择分支。
  - 同一分支重复出现会增加该路径在输出中的出现频次（用于控制分支权重）。
  - 空单元格会被直接忽略。

## 节点与展开规则

### 1. 节点的展开与保留
- **所有非控制节点**均会保留在最终输出中：
  - **叶子节点**（未在表头定义的标签）：直接作为最终标签输出。
  - **非叶子节点**（在表头有定义的标签）：保留自身标签名，并将其子分支展开后依次回溯追加在其后（如 `long_hair` 会保留并追加其子项 `ponytail`）。

### 2. 控制节点（以 `<root>` 或 `<hidden>` 开头）
控制节点自身**永远不会**出现在最终输出字符串中，支持以下两种形态：
- **分类控制节点（如 `<hidden>发型`、`<hidden>审查`）**：
  通常定义在表头，仅用于逻辑分类和导向分流，子分支展开后该节点名会被剔除。
- **静默/空分支（单独的 `<hidden>`）**：
  通常作为未在表头定义的叶子节点使用。分支遍历到此节点时结算为空（不产生任何标签）。可用于表达“跳过/不选择该特征”，从而生成更短的标签组合；若重复出现亦可控制该空分支的命中权重。

### 3. 单元格展开规则（AND 与笛卡尔积）
- 单元格内可通过英文半角逗号 `,` 连接多个子标签（如 `"<hidden>审查, 1girl, <hidden>发型"`）。
- 程序会自动去除每个标签首尾的空格（`.strip()`），这些标签构成**与（AND）**关系。
- 展开时依次递归求解每个子标签的所有分支，并通过笛卡尔积组合所有结果。

## 输入示例 (`tags.csv`)
```csv
<root>,<hidden>审查,<hidden>发型,long_hair
"<hidden>审查, 1girl, <hidden>发型",safe,short_hair,ponytail
,,short_hair,<hidden>
,,long_hair,
```
*推演说明：*
1. `<root>` 分流至 `[<hidden>审查, 1girl, <hidden>发型]`。
2. `<hidden>审查` 为控制节点（不保留自身），展开为 `safe`。
3. `1girl` 未在表头定义，为普通叶子节点，原样保留。
4. `<hidden>发型` 为控制节点，提供 3 个 OR 分支：`short_hair`（权重为2）、`long_hair`（权重为1）。
5. `long_hair` 在表头有定义，展开时保留自身，并继续追加其 2 个分支之一：`ponytail` 或 `<hidden>`（空分支，此时产生较短组合 `long_hair`）。

## 使用命令
```powershell
# 结果直接输出至 stdout
tag-csv2str -i tags.csv

# 保存至文件
tag-csv2str -i tags.csv | Out-File -FilePath output.jsonl -Encoding utf8
```

## 输出示例 (`JSON Lines`)
```jsonl
{"tag_string": "safe, 1girl, short_hair"}
{"tag_string": "safe, 1girl, short_hair"}
{"tag_string": "safe, 1girl, long_hair, ponytail"}
{"tag_string": "safe, 1girl, long_hair"}
```
""",
        formatter_class=RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        '-i', '--input',
        type=Path,
        required=True,
        help='输入 CSV 路径 (e.g., tags.csv)'
    )

    args = parser.parse_args()

    try:
        input_file_path = Path(args.input)

        tag_strings = tag_csv2str(input_file_path)

        for tag_string in tag_strings:
            print(json.dumps({"tag_string": tag_string}, ensure_ascii=False))

        sys.exit(0)

    except Exception as e:
        print(f"\n发生错误：{e}", file=sys.stderr)
        sys.exit(2)

def cli_tag_tag2nl():
    parser = ArgumentParser(
        description=r"""
# tag-tag2nl

基于 TIPO 模型，将 Danbooru Tags 深度扩写为自然语言（NL）与丰富标签的命令行工具。  
核心逻辑：**标准输入 (stdin) 接收一组 JSONL，标准输出 (stdout) 吐出一组严格 1:1 对应的 JSONL**。

---

## 数据格式

### 输入 (`input.jsonl`)
每行一个 JSON，必须包含 `tag_string` 字段：
```jsonl
{"tag_string": "safe, 1girl, short_hair"}
{"tag_string": "safe, 1girl, short_hair"}
{"tag_string": "safe, 1girl, long_hair, ponytail"}
{"tag_string": "safe, 1girl, long_hair"}
```

### 输出 (`output.jsonl`)
与输入行数 **严格 1:1 对应**。内部换行均已转义为 `\n`，保证单条数据独占一行：
```jsonl
{"prompt": "1girl, short hair, ...\n\na charming illustration of ...\n\nsafe"}
{"prompt": "1girl, short hair, ...\n\na detailed portrait featuring ...\n\nsafe"}
{"prompt": "1girl, long hair, ponytail, ...\n\nan illustration depicting ...\n\nsafe"}
{"prompt": "1girl, long hair, ...\n\na captivating artwork of ...\n\nsafe"}
```

---

## 使用方法

### 1. 管道批处理模式（主力）
通过标准输入（stdin）传入数据，输出重定向到目标文件：

```powershell
Get-Content input.jsonl -Raw | tag-tag2nl | Out-File -FilePath output.jsonl -Encoding utf8
```
> **提示**：若在 Python / Node.js 等子进程中调用 stdin 模式，写入完成后请**主动关闭 stdin / 发送 EOF**，否则程序会挂起等待。

### 2. 参数调试模式（辅助 / 临时测试）
使用 `-t` 参数直接传入一个或多个 tag 字符串，主要用于临时测试。输出格式同样为标准 JSONL：

```powershell
tag-tag2nl -t "safe, 1girl, short_hair" "safe, 1girl, long_hair, ponytail"
```
""",
        formatter_class=RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "-t", "--tag-strings",
        nargs="+",
        help="一个或多个 tag_strings"
    )

    # dry-run
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅解析并打印参数"
    )

    args = parser.parse_args()

    if args.tag_strings:
        tag_strings = args.tag_strings
    else:
        tag_strings = [
            json.loads(line)["tag_string"]
            for line in sys.stdin
            if line.strip()
        ]

    request = [
        TipoRequest(tags=t, seed=random.randrange(0, 2**32 - 1))
        for t in tag_strings
    ]

    if args.dry_run:
        print("[DRY-RUN] 参数解析成功，请求参数如下：", file=sys.stderr)
        for req in request:
            print(f"[DRY-RUN] tags={req.tags}, seed={req.seed}", file=sys.stderr)
        sys.exit(0)

    response = tag_tag2nl(request=request)
    print(response)