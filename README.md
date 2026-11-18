# ms-toolbox

MatsubaraSoda 个人工具箱

## 安装

需要 Python 3.12+。推荐使用 [uv](https://docs.astral.sh/uv/) 安装为全局命令行工具：

```bash
# 从 PyPI 安装（推荐）
uv tool install ms-toolbox
```

## 工具模块

- **[PDF 工具](docs/pdf.md)** — PDF 瑞士军刀
- **[Tag 工具](docs/tag.md)** — Comfyui 提示词生成与加工
- **[Harness](docs/harness.md)** — Toy 级个人 Harness 工具

## 本地开发

```bash
git clone https://github.com/MatsubaraSoda/ms-toolbox
cd ms-toolbox
uv sync             # 创建虚拟环境并安装依赖（含开发依赖）
uv run pytest -v    # 运行测试
```

## 许可证

本项目基于 [MIT License](LICENSE) 发布。
