# pdf-isolate

一个轻量的 PDF 页码提取命令行工具：从 PDF 中截取指定的页码范围，并另存为一个新的 PDF 文件。基于 [pypdf](https://github.com/py-pdf/pypdf) 构建。

## 功能

- 按页码范围提取 PDF，页码从 1 开始计数，包含首尾两页
- 单条命令完成，无需打开 PDF 编辑器手动删页
- 核心函数亦可作为 Python 库在代码中直接调用

## 安装

需要 Python 3.12+。推荐使用 [uv](https://docs.astral.sh/uv/) 安装为全局命令行工具：

```bash
# 从 PyPI 安装（推荐）
uv tool install pdf-isolate

# 或者不安装，直接临时运行一次
uvx pdf-isolate -i input.pdf -o output.pdf --start 5 --end 10

# 或者直接从 GitHub 仓库安装
uv tool install git+https://github.com/MatsubaraSoda/pdf-isolate
```

没有 uv 也可以用 [pipx](https://pipx.pypa.io/)：`pipx install pdf-isolate`。

## 使用

```bash
pdf-isolate -i input.pdf -o output.pdf --start 5 --end 10
```

上面的命令会把 `input.pdf` 的第 5 页到第 10 页提取出来，保存为 `output.pdf`。

### 参数说明

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `-i`, `--input` | 是 | 输入 PDF 文件路径 |
| `-o`, `--output` | 是 | 输出 PDF 文件路径 |
| `--start` | 是 | 起始页码（1 起始，包含该页） |
| `--end` | 是 | 结束页码（包含该页） |

运行示例：

```text
--- 正在启动 PDF 提取工具 ---
输入文件：input.pdf
输出文件：output.pdf
页码范围：5 到 10
成功提取第 5 页到第 10 页，并保存到 'output.pdf'。
```

### 退出码

| 退出码 | 含义 |
| --- | --- |
| `0` | 提取成功 |
| `1` | 提取失败（文件不存在或损坏、页码范围无效等） |
| `2` | 命令行参数错误（如缺少必填项）或意外的程序错误 |

## 作为 Python 库使用

核心功能也可以在 Python 代码中直接调用：

```python
from pathlib import Path
from pdf_isolate.core import extract_and_save_pages, get_total_pages

# 获取 PDF 总页数，失败时返回 None
total = get_total_pages(Path("input.pdf"))

# 提取第 5 页到第 10 页，成功返回 True，失败返回 False
ok = extract_and_save_pages(
    input_file_path=Path("input.pdf"),
    output_file_path=Path("output.pdf"),
    start_page=5,
    end_page=10,
)
```

## 本地开发

```bash
git clone https://github.com/MatsubaraSoda/pdf-isolate
cd pdf-isolate
uv sync          # 创建虚拟环境并安装依赖（含开发依赖）
uv run pytest    # 运行测试
```

也可以直接在开发环境中试用命令行工具：

```bash
uv run pdf-isolate -i tests/test_data/Campbell-Biology-Chapter-1.pdf -o sample.pdf --start 1 --end 3
```

## 许可证

本项目基于 [MIT License](LICENSE) 发布。