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

from ms_toolbox.harness.config import (
    SESSIONS_DIR,
    get_harness_config,
    get_presets,
    open_config,
    open_presets,
)
from ms_toolbox.harness.runtime import (
    continue_chat,
    get_running_sessions,
    is_running,
    start_chat,
    stop_chat,
)
from ms_toolbox.harness.session import Session, list_sessions
from ms_toolbox.harness.tools.run_command import (
    active_containers,
    start_container,
    stop_all_containers,
    stop_container,
)

# 网页静态资源服务：自动映射同级 site/ 目录下的静态文件与 sessions/ 下的会话资源
SITE_DIR = (Path(__file__).parent / "site").resolve()
mimetypes.add_type("text/javascript", ".js")

# 记录当前所有在线的 Web UI 客户端连接
webui_clients: set = set()


def serve_site(_, request):
    if request.headers.get("Upgrade", "").lower() != "websocket":
        if request.path.startswith("/sessions/"):
            rel_path = request.path.removeprefix("/sessions/")
            base_dir = SESSIONS_DIR.resolve()
        else:
            rel_path = "index.html" if request.path == "/" else request.path.lstrip("/")
            base_dir = SITE_DIR

        file_path = (base_dir / rel_path).resolve()

        if file_path.is_relative_to(base_dir) and file_path.is_file():
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


async def send_to_frontend(websocket, data: dict):
    """将 Python 字典序列化为 JSON 字符串并发送给指定的单个前端客户端"""
    await websocket.send(json.dumps(data, ensure_ascii=False))


async def broadcast_to_frontend(data: dict):
    """向所有在线的 Web UI 客户端广播消息"""
    for ws in list(webui_clients):
        try:
            await send_to_frontend(ws, data)
        except ConnectionClosed:
            webui_clients.discard(ws)


async def receive_from_frontend(websocket):
    """持续接收前端发来的 JSON 字符串，并解析为 Python 字典逐条产出"""
    async for raw_msg in websocket:
        yield json.loads(raw_msg)


async def ws_handler(websocket):
    async def send_fn(data: dict):
        await send_to_frontend(websocket, data)

    async def send_init_state():
        await send_fn({
            "type": "init_state",
            "presets": get_presets(),
            "sessions": list_sessions(),
            "running_sessions": get_running_sessions(),
            "active_containers": list(active_containers),
        })

    async def send_container_state():
        await broadcast_to_frontend({
            "type": "container_state",
            "active_containers": list(active_containers),
        })

    webui_clients.add(websocket)
    try:
        # 连接建立后，发送预设列表、历史对话列表、运行中对话列表、已启动容器列表
        await send_init_state()

        async for data in receive_from_frontend(websocket):
            msg_type = data["type"]

            if msg_type == "init_session":
                await send_init_state()

            elif msg_type == "load_session":
                session_id = data["session_id"]
                session = Session.load(session_id)
                await send_fn({
                    "type": "session_loaded",
                    "session_id": session_id,
                    "ui_messages": session.ui_messages,
                    "sessions": list_sessions(),
                })

            elif msg_type == "copy_session":
                Session.copy(data["session_id"])
                await send_fn({
                    "type": "session_copied",
                    "sessions": list_sessions(),
                })

            elif msg_type == "rename_session":
                session_id = data["session_id"]
                title = data["title"].strip()
                if is_running(session_id) or not title:
                    continue

                session = Session.load(session_id)
                session.rename(title)
                await send_fn({
                    "type": "session_renamed",
                    "sessions": list_sessions(),
                })

            elif msg_type == "delete_session":
                session_id = data["session_id"]
                if is_running(session_id):
                    continue

                if session_id in active_containers:
                    await asyncio.to_thread(stop_container, session_id)
                    await send_container_state()

                Session.delete(session_id)
                await send_fn({
                    "type": "session_deleted",
                    "session_id": session_id,
                    "sessions": list_sessions(),
                })

            elif msg_type == "update_config":
                session_id = data["session_id"]
                if is_running(session_id):
                    continue

                cfg = data["config"]
                workspace_dir = cfg["workspace_dir"].strip()
                if not workspace_dir or not Path(workspace_dir).is_dir():
                    await send_fn({
                        "type": "workspace_error",
                        "message": "文件夹不存在",
                    })
                    continue

                cfg["workspace_dir"] = workspace_dir
                session = Session.load(session_id)
                old_workspace = session.workspace_dir
                old_image = session.docker_image
                session.update_config(cfg)

                workspace_changed = Path(old_workspace).resolve() != Path(workspace_dir).resolve()
                image_changed = old_image.strip() != session.docker_image.strip()
                if (workspace_changed or image_changed) and session_id in active_containers:
                    await asyncio.to_thread(stop_container, session_id)
                    await send_container_state()

                await send_fn({
                    "type": "config_updated",
                    "session_id": session_id,
                    "ui_messages": session.ui_messages,
                })

            elif msg_type == "submit_chat":
                session_id = data.get("session_id")

                # 新对话的第一条消息：先校验工作区目录，再创建目录与初始文件并锁定 session_id
                if session_id is None:
                    workspace_dir = data["config"]["workspace_dir"].strip()
                    if not workspace_dir or not Path(workspace_dir).is_dir():
                        await send_fn({
                            "type": "workspace_error",
                            "message": "文件夹不存在",
                        })
                        continue

                    session = Session.create(data["config"])
                    await send_fn({
                        "type": "session_loaded",
                        "session_id": session.id,
                        "ui_messages": session.ui_messages,
                        "sessions": list_sessions(),
                    })
                else:
                    if is_running(session_id):
                        continue
                    session = Session.load(session_id)

                await start_chat(session, data["content"], data.get("files"), broadcast_to_frontend)

            elif msg_type == "stop_chat":
                session_id = data.get("session_id")
                if session_id:
                    stop_chat(session_id)

            elif msg_type == "continue_chat":
                session_id = data["session_id"]
                if is_running(session_id):
                    continue

                session = Session.load(session_id)
                await continue_chat(session, broadcast_to_frontend)

            elif msg_type == "rewind_session":
                session_id = data["session_id"]
                if is_running(session_id):
                    continue

                session = Session.load(session_id)
                content = session.rewind(data["ui_index"])
                await send_fn({
                    "type": "session_rewound",
                    "session_id": session_id,
                    "messages": session.ui_messages["messages"],
                    "content": content,
                    "sessions": list_sessions(),
                })

            elif msg_type == "pick_dir":
                path = await asyncio.to_thread(pick_directory)
                if path:
                    await send_fn({
                        "type": "dir_picked",
                        "path": path,
                    })

            elif msg_type == "open_settings":
                open_config()

            elif msg_type == "open_presets":
                open_presets()

            elif msg_type == "reload_presets":
                await send_fn({
                    "type": "presets_updated",
                    "presets": get_presets(),
                })

            elif msg_type == "start_container":
                session_id = data["session_id"]
                session = Session.load(session_id)
                err = await asyncio.to_thread(
                    start_container, session_id, session.workspace_dir, session.docker_image
                )
                if err:
                    print(f"[Docker] {err}")
                await send_container_state()

            elif msg_type == "stop_container":
                session_id = data["session_id"]
                await asyncio.to_thread(stop_container, session_id)
                await send_container_state()

    except ConnectionClosed:
        print("客户端已断开连接")
    except Exception:
        print(traceback.format_exc())
    finally:
        webui_clients.discard(websocket)


async def main(port: int):
    try:
        async with serve(ws_handler, "localhost", port, process_request=serve_site, max_size=None):
            print(f"服务 {port} 启动成功: http://localhost:{port}")
            await asyncio.Future()
    finally:
        stop_all_containers()


def run():
    parser = ArgumentParser()
    parser.add_argument("--port", type=int, help="指定服务启动端口（未指定时读取 harness/config.yaml 中的 port）")
    args = parser.parse_args()

    port = args.port or get_harness_config()["port"]
    asyncio.run(main(port))


if __name__ == "__main__":
    run()
