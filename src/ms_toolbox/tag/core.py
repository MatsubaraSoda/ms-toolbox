import csv
import json
import os
import subprocess
from pathlib import Path
from dataclasses import asdict, dataclass
from ms_toolbox.config import get_config


# 以 `<root>` / `<hidden> 开头的节点只在树中起组织作用，其名字本身不进入最终组合
def _is_hidden(tag: str) -> bool:
    if tag.startswith('<root>') or tag.startswith('<hidden>'):
        return True
    else:
        return False

# 递归遍历标签邻接表，生成所有合法的标签组合列表
def _traverse(adj: dict[str, list[str]], tag: str) -> list[list[str]]:
    # 基准条件：若该 tag 不在字典 keys 中，则作为叶子节点结束递归
    if tag not in adj:
        if _is_hidden(tag):
            return [[]]
        else:
            return [[tag]]

    result = []
    # 遍历当前 tag 的所有可选分支（对应 CSV 中该 tag 所在列的所有单元格）
    for cell in adj[tag]:
        # 单个单元格内可能由逗号连接多个子标签
        cell_tags = [t.strip() for t in cell.split(',') if t.strip()]
        if not cell_tags:
            continue

        # 依次展开单元格内的每个子标签，并通过笛卡尔积合并其所有分支
        # 注意：此处使用局部变量 t 避免与函数入参 tag 同名遮蔽
        acc_paths = [[]]
        for t in cell_tags:
            sub_paths = _traverse(adj, t)
            acc_paths = [
                acc + sub
                for acc in acc_paths
                for sub in sub_paths
            ]
        # 将当前单元格产生的所有有效组合合并到最终分支集合中
        result.extend(acc_paths)

    # 递归回溯组装：根据当前 tag 是否需要隐藏，决定是否保留自己
    if _is_hidden(tag):
        return [[] + res for res in result]
    else:
        return [[tag] + res for res in result]

def csv2tag(csv_file_path: Path | str) -> list[str]:
    # 读取 CSV 文件
    with open(csv_file_path, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
        columns = [list(column) for column in zip(*rows)]

    # 构建标签邻接表
    tag_adj = {
        p: [c for c in map(str.strip, children) if c]
        for parent, *children in columns
        if (p := parent.strip())
    }

    # 约定 CSV 中的 `<root>` 为根
    result = _traverse(tag_adj, '<root>')
    # list[list[str]] 转化为 list[str]
    tag_strings = []
    for res in result:
        tag_strings.append(', '.join(res))

    return tag_strings


# 仅针对 Windows 11 + Conda 环境
WORKER_SCRIPT = Path(__file__).resolve().with_name("tipo_worker.py")

@dataclass
class TipoRequest:
    tags: str
    nl_prompt: str = ""
    black_list: str = ""
    output_format: str = "Both, tag first (recommend)"
    target_length: str = "long"
    temp: float = 0.5
    top_p: float = 0.95
    min_p: float = 0.05
    top_k: int = 60
    seed: int = 20090220
    escape_brackets: bool = False

def _get_worker_env(python_exe: Path) -> dict[str, str]:
    """补齐 Windows Conda 环境必要的 PATH 与编码环境变量"""
    env_dir = python_exe.parent
    extra_paths = [
        str(env_dir),
        str(env_dir / "Library" / "bin"),
        str(env_dir / "Library" / "mingw-w64" / "bin"),
        str(env_dir / "Scripts"),
    ]
    return {
        **os.environ,
        "PATH": ";".join(extra_paths) + ";" + os.environ.get("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }

def tag2nl(request: list[TipoRequest]) -> list[str]:
    python_exe = Path(get_config()["tipo_worker_python_exe"])
    env = _get_worker_env(python_exe)

    # 约定 JSONL 作为 runner 与 worker 之间的数据交换格式
    payload = "\n".join(json.dumps(asdict(item), ensure_ascii=False) for item in request) + "\n"

    result = subprocess.run(
        [str(python_exe), str(WORKER_SCRIPT)],
        input=payload,
        capture_output=True,    # 捕获标准输出和标准错误，不在终端中打印。
        text=True,              # 自动把 stdout/stderr 转成字符串，不手动 decode
        encoding="utf-8",       # 指定编码
        errors="replace",       # 解码出错时自动替换，不报错
        env=env,
        check=True,             # 替代 returncode
    )

    return [
        json.loads(line)["prompt"]
        for line in result.stdout.splitlines()
        if line.strip()
    ]
