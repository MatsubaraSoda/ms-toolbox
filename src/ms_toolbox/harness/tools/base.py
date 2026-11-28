from pathlib import Path
import pathspec


def load_gitignore(gitignore_file: Path) -> pathspec.PathSpec:
    """读取单个 .gitignore 文件并生成匹配器"""
    lines = gitignore_file.read_text(encoding="utf-8").splitlines()
    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def load_upward_matchers(root: Path) -> dict[Path, pathspec.PathSpec]:
    """从 root 开始向上检查父目录，收集沿途的 .gitignore（遇到 .git 目录即停止）"""
    matchers = {}

    for folder in [root, *root.parents]:
        gitignore_file = folder / ".gitignore"
        if gitignore_file.is_file():
            matchers[folder] = load_gitignore(gitignore_file)

        if (folder / ".git").exists():
            break

    return matchers


def is_ignored(target: Path, matchers: dict[Path, pathspec.PathSpec]) -> bool:
    """判断目标路径是否被已知的 .gitignore 规则忽略"""
    if target.name == ".git":
        return True

    for folder, matcher in matchers.items():
        if target.is_relative_to(folder):
            rel_path = target.relative_to(folder).as_posix()
            if target.is_dir():
                rel_path += "/"
            if matcher.match_file(rel_path):
                return True
    return False


def resolve_workspace_path(workspace_dir: str, path: str) -> tuple[Path, str] | str:
    """限制路径必须在 workspace_dir 内，返回 (绝对路径, 相对路径字符串) 或错误提示"""
    base_dir = Path(workspace_dir).resolve()
    target = (base_dir / path).resolve()

    if not target.is_relative_to(base_dir):
        return f"访问被拒绝：路径 '{path}' 位于工作区之外。"

    rel_path = target.relative_to(base_dir).as_posix()
    return target, rel_path


def create_base_tools(workspace_dir: str) -> list:
    def list_files(path: str) -> str:
        """列出指定目录下的文件树结构，用于了解项目文件布局。

        Args:
            path (str): 要查看的目录相对路径（例如 "." 表示当前工作区根目录）。
        """
        resolved = resolve_workspace_path(workspace_dir, path)
        if isinstance(resolved, str):
            return resolved
        root, rel_path = resolved

        if not root.exists():
            return f"错误：目录 '{rel_path}' 不存在。"
        if not root.is_dir():
            return f"错误：'{rel_path}' 是文件而不是目录。"

        matchers = load_upward_matchers(root)
        lines = []

        def _walk(directory: Path, prefix: str = ""):
            sub_gitignore = directory / ".gitignore"
            if directory not in matchers and sub_gitignore.is_file():
                matchers[directory] = load_gitignore(sub_gitignore)

            items = sorted(
                [
                    item
                    for item in directory.iterdir()
                    if not is_ignored(item, matchers)
                ]
            )
            total = len(items)

            for index, item in enumerate(items):
                is_last = index == total - 1
                connector = "└── " if is_last else "├── "
                suffix = "/" if item.is_dir() else ""
                lines.append(f"{prefix}{connector}{item.name}{suffix}")

                if item.is_dir():
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    _walk(item, next_prefix)

        _walk(root)
        return "\n".join(lines) if lines else "（空目录）"

    def read_file(path: str) -> str:
        """读取并返回指定文件的全部文本内容。

        Args:
            path (str): 要读取的目标文件相对路径（例如 main.py 或 tests/test_main.py）。
        """
        resolved = resolve_workspace_path(workspace_dir, path)
        if isinstance(resolved, str):
            return resolved
        p, rel_path = resolved

        if not p.exists():
            return f"错误：文件 '{rel_path}' 不存在。"
        if p.is_dir():
            return f"错误：'{rel_path}' 是目录而不是文件，请使用 list_files 查看。"
        return p.read_text(encoding="utf-8")

    def write_file(path: str, content: str) -> str:
        """创建新文件或覆盖写入现有文件的全部内容。

        Args:
            path (str): 目标文件的相对路径（例如 hello.py）。
            content (str): 要写入文件的完整文本内容。
        """
        resolved = resolve_workspace_path(workspace_dir, path)
        if isinstance(resolved, str):
            return resolved
        p, rel_path = resolved

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="\n")
        return f"文件 '{rel_path}' 写入成功。"

    def edit_file(path: str, old_str: str, new_str: str) -> str:
        """通过查找并替换文本，对现有文本进行局部修改。

        Args:
            path (str): 要修改的目标文件相对路径。
            old_str (str): 要被替换的原始文本（请包含足够的上下文行，确保在文件中唯一出现）。
            new_str (str): 替换后的新文本。
        """
        resolved = resolve_workspace_path(workspace_dir, path)
        if isinstance(resolved, str):
            return resolved
        p, rel_path = resolved

        if not p.exists():
            return f"错误：文件 '{rel_path}' 不存在。"
        if p.is_dir():
            return f"错误：'{rel_path}' 是目录而不是文件。"
        if not old_str:
            return "错误：old_str 不能为空。"

        content = p.read_text(encoding="utf-8")
        count = content.count(old_str)

        if count == 0:
            return "错误：未找到 old_str，请确保与原文件完全一致。"
        if count > 1:
            return f"错误：old_str 在文件中出现了 {count} 次，无法确定改哪一个。请补充前后几行代码作为上下文，使其唯一。"

        new_content = content.replace(old_str, new_str, 1)
        p.write_text(new_content, encoding="utf-8", newline="\n")
        return f"文件 '{rel_path}' 修改成功。"

    return [list_files, read_file, write_file, edit_file]
