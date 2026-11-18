import asyncio
import ctypes
import json
import mimetypes
import sys
import traceback
from argparse import ArgumentParser
from http import HTTPStatus
from pathlib import Path
from tkinter import Tk, filedialog

from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response

from ms_toolbox.harness.config import get_default_config, get_harness_config, open_config
from ms_toolbox.harness.session import Session, list_sessions

# 记录当前正在后台等待大模型响应或执行工具的 session_id
running_sessions: set[str] = set()

# 网页静态资源服务：自动映射同级 site/ 目录下的静态文件
SITE_DIR = (Path(__file__).parent / "site").resolve()


def serve_site(_, request):
    if request.headers.get("Upgrade", "").lower() != "websocket":
        rel_path = "index.html" if request.path == "/" else request.path.lstrip("/")
        file_path = (SITE_DIR / rel_path).resolve()

        if file_path.is_relative_to(SITE_DIR) and file_path.is_file():
            content_type, _ = mimetypes.guess_type(file_path)
            headers = Headers([("Content-Type", content_type or "application/octet-stream")])
            return Response(HTTPStatus.OK, "OK", headers, file_path.read_bytes())
        return Response(HTTPStatus.NOT_FOUND, "Not Found", Headers(), b"")
    return None


def pick_directory() -> str:
    """弹出系统原生文件夹选择框并返回所选路径"""
    if sys.platform == "win32":
        ctypes.windll.shcore.SetProcessDpiAwareness(2)

    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askdirectory()
    root.destroy()
    return path


async def ws_handler(websocket):
    async def send_ui(session_id: str, messages: list):
        await websocket.send(json.dumps({
            "type": "messages",
            "session_id": session_id,
            "data": messages,
            "sessions": list_sessions(),
        }, ensure_ascii=False))

    async def send_running_state():
        await websocket.send(json.dumps({
            "type": "running_state",
            "running_sessions": list(running_sessions),
        }, ensure_ascii=False))

    async def run_in_background(session_id: str, coro):
        """将耗时对话任务放入 running_sessions 托管，结束后自动释放"""
        running_sessions.add(session_id)
        await send_running_state()
        try:
            await coro
        finally:
            running_sessions.remove(session_id)
            await send_running_state()

    # 连接建立后，发送默认新建配置、历史对话列表、运行中对话列表
    await websocket.send(json.dumps({
        "type": "init",
        "config": get_default_config(),
        "sessions": list_sessions(),
        "running_sessions": list(running_sessions),
    }, ensure_ascii=False))

    try:
        async for raw_msg in websocket:
            data = json.loads(raw_msg)
            msg_type = data["type"]

            if msg_type == "new_session":
                await websocket.send(json.dumps({
                    "type": "init",
                    "config": get_default_config(),
                    "sessions": list_sessions(),
                    "running_sessions": list(running_sessions),
                }, ensure_ascii=False))

            elif msg_type == "load_session":
                session_id = data["session_id"]
                session = Session.load(session_id)
                await websocket.send(json.dumps({
                    "type": "session_loaded",
                    "session_id": session_id,
                    "ui_messages": session.ui_messages,
                    "sessions": list_sessions(),
                }, ensure_ascii=False))

            elif msg_type == "chat":
                session_id = data.get("session_id")

                # 新对话的第一条消息：先校验工作区目录，再创建目录与初始文件并锁定 session_id
                if session_id is None:
                    workspace_dir = data["config"]["workspace_dir"].strip()
                    if not workspace_dir or not Path(workspace_dir).is_dir():
                        await websocket.send(json.dumps({
                            "type": "workspace_error",
                            "message": "文件夹不存在",
                        }, ensure_ascii=False))
                        continue

                    session = Session.create(data["config"], on_update=send_ui)
                    session_id = session.id
                    await websocket.send(json.dumps({
                        "type": "session_loaded",
                        "session_id": session_id,
                        "ui_messages": session.ui_messages,
                        "sessions": list_sessions(),
                    }, ensure_ascii=False))
                else:
                    if session_id in running_sessions:
                        continue
                    session = Session.load(session_id, on_update=send_ui)

                asyncio.create_task(run_in_background(session_id, session.chat(data["content"])))

            elif msg_type == "continue":
                session_id = data["session_id"]
                if session_id in running_sessions:
                    continue

                session = Session.load(session_id, on_update=send_ui)
                asyncio.create_task(run_in_background(session_id, session.continue_chat()))

            elif msg_type == "pick_dir":
                path = await asyncio.to_thread(pick_directory)
                if path:
                    await websocket.send(json.dumps({
                        "type": "dir_picked",
                        "path": path,
                    }, ensure_ascii=False))

            elif msg_type == "open_settings":
                open_config()

    except ConnectionClosed:
        print("客户端已断开连接")
    except Exception:
        print(traceback.format_exc())


async def main(port: int):
    async with serve(ws_handler, "localhost", port, process_request=serve_site):
        print(f"服务 {port} 启动成功: http://localhost:{port}")
        await asyncio.Future()


def run():
    parser = ArgumentParser()
    parser.add_argument("--port", type=int, help="指定服务启动端口（未指定时读取 config.yaml 中的 harness.port）")
    args = parser.parse_args()

    port = args.port or get_harness_config()["port"]
    asyncio.run(main(port))


if __name__ == "__main__":
    run()
