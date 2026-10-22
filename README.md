# ms-toolbox

MatsubaraSoda 个人工具箱

## 安装

需要 Python 3.12+。推荐使用 [uv](https://docs.astral.sh/uv/) 安装为全局命令行工具：

```bash
# 从 PyPI 安装（推荐）
uv tool install ms-toolbox
```

## 工具列表

安装 ms-toolbox 后，下列命令均可直接使用；完整参数以各命令的 `--help` 输出为准。

### pdf-extract — 提取 PDF 的指定页码范围，另存为新文件

```bash
pdf-extract -i input.pdf -o output.pdf --start 5 --end 10
```

把 `input.pdf` 的第 5 页到第 10 页（含首尾）保存为 `output.pdf`，成功时退出码为 0。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `-i`, `--input` | 是 | 输入 PDF 文件路径 |
| `-o`, `--output` | 是 | 输出 PDF 文件路径 |
| `--start` | 是 | 起始页码（1 起始，包含该页） |
| `--end` | 是 | 结束页码（包含该页） |

退出码：`0` 成功；`1` 提取失败；`2` 意外错误。

```text
--- 正在启动 PDF 提取工具 ---
输入文件：input.pdf
输出文件：output.pdf
页码范围：5 到 10
成功提取第 5 页到第 10 页，并保存到 'output.pdf'。
```

## 本地开发

```bash
git clone https://github.com/MatsubaraSoda/ms-toolbox
cd ms-toolbox
uv sync             # 创建虚拟环境并安装依赖（含开发依赖）
uv run pytest -v    # 运行测试
```

## 许可证

本项目基于 [MIT License](LICENSE) 发布。