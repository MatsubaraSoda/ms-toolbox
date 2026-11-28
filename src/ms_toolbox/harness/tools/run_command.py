import subprocess
import uuid
from pathlib import Path

MAX_OUTPUT_CHARS = 10000

# 记录当前已经启动了 Docker 容器的 session_id
active_containers: set[str] = set()


def truncate_output(text: str, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= max_chars:
        return text

    head_chars = max_chars // 2
    tail_chars = max_chars - head_chars
    omitted_chars = len(text) - max_chars
    return (
        f"{text[:head_chars]}\n"
        f"... [中间已省略 {omitted_chars} 个字符，如需查看特定内容请使用 grep / head / tail 等命令过滤] ...\n"
        f"{text[-tail_chars:]}"
    )


def start_container(session_id: str, workspace_dir: str, docker_image: str) -> str | None:
    if session_id in active_containers:
        return None

    image = docker_image.strip()
    if not image:
        return "error: 未配置 docker_image，请在 config.yaml 或右侧对话设置中填写 Docker 镜像名称。"

    container_name = f"msh-{session_id}"
    abs_workspace = Path(workspace_dir).resolve()

    cmd = [
        "docker", "run",
        "-d",
        "--name", container_name,
        "-v", f"{abs_workspace}:/workspace",
        "-w", "/workspace",
        image,
        "sleep", "infinity",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        return "error: 未找到 docker 命令，请确认本机已安装 Docker。"

    if result.returncode != 0:
        return (
            f"error: 启动 Docker 容器失败（请确认 Docker 服务已启动且镜像 '{image}' 有效）。\n"
            f"stderr:\n{result.stderr}"
        )

    active_containers.add(session_id)
    print(f"[Docker] 已启动容器: {container_name} ({image})")
    return None


def exec_in_container(
    session_id: str,
    command: str,
    timeout: int = 30,
    background: bool = False,
) -> str:
    container_name = f"msh-{session_id}"

    if background:
        log_path = f"/tmp/bg_{uuid.uuid4().hex[:6]}.log"
        cmd = [
            "docker", "exec", "-d",
            container_name,
            "sh", "-c", f"{command} > {log_path} 2>&1",
        ]
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        return (
            f"命令已在后台启动。\n"
            f"log_path: {log_path}\n"
            f"提示: 可使用 `cat {log_path}` 查看运行日志。"
        )

    cmd = [
        "docker", "exec",
        container_name,
        "timeout", str(timeout),
        "sh", "-c", command,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    stdout = truncate_output(result.stdout)
    stderr = truncate_output(result.stderr)

    if result.returncode == 124:
        return (
            f"error: 命令执行超时（超过 {timeout} 秒已被终止）。"
            f"耗时任务可调大 timeout，常驻服务请设置 background=True。\n"
            f"stdout:\n{stdout}"
            f"stderr:\n{stderr}"
        )

    return (
        f"exit_code: {result.returncode}\n"
        f"stdout:\n{stdout}"
        f"stderr:\n{stderr}"
    )


def stop_container(session_id: str):
    if session_id not in active_containers:
        return

    container_name = f"msh-{session_id}"
    cmd = ["docker", "rm", "-f", container_name]
    subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    active_containers.remove(session_id)
    print(f"[Docker] 已销毁容器: {container_name}")


def stop_all_containers():
    for session_id in list(active_containers):
        stop_container(session_id)


def create_run_command_tool(session_id: str, workspace_dir: str, docker_image: str):
    def run_command(command: str, timeout: int = 30, background: bool = False) -> str:
        """在当前工作区对应的 Linux 容器中执行 Shell 命令。

        Args:
            command (str): 要执行的 Shell 命令（例如 "ls -la" 或 "python3 main.py"）。
            timeout (int, optional): 超时时间（秒），默认为 30。耗时较长的任务（如安装依赖）可调大此值。
            background (bool, optional): 是否在后台常驻运行，默认为 False。启动 Web 服务等不会主动退出的命令时设为 True。
        """
        if session_id not in active_containers:
            err = start_container(session_id, workspace_dir, docker_image)
            if err:
                return err

        return exec_in_container(session_id, command, timeout, background)

    return run_command
