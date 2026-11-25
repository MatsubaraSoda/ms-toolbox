import base64
import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from ms_toolbox.harness.config import SESSIONS_DIR, get_harness_config
from ms_toolbox.harness.tools import build_tools
from ms_toolbox.harness.tools.utils import to_image_url


def make_default_title(session_id: str) -> str:
    """将 '20261117_205125_07f55bc3-...' 格式化为默认标题 '11-17 20:51 · 07f55bc3'"""
    return f"{session_id[4:6]}-{session_id[6:8]} {session_id[9:11]}:{session_id[11:13]} · {session_id[16:24]}"


def list_sessions() -> list[dict]:
    """扫描本地 sessions/ 文件夹，按最后编辑时间从新到旧排序，返回会话 id 与标题列表"""
    dirs = [d for d in SESSIONS_DIR.iterdir() if (d / "ui_messages.json").exists()]
    dirs.sort(key=lambda d: (d / "ui_messages.json").stat().st_mtime, reverse=True)

    sessions = []
    for d in dirs:
        ui_messages = json.loads((d / "ui_messages.json").read_text(encoding="utf-8"))
        title = ui_messages.get("title") or make_default_title(d.name)
        sessions.append({"id": d.name, "title": title})
    return sessions


class Session:
    def __init__(self, session_id: str, request_body: dict, ui_messages: dict):
        self.id = session_id

        self.session_dir = SESSIONS_DIR / session_id
        self.assets_dir = self.session_dir / "assets"
        self.http_dir = self.session_dir / "http_logs"
        self.http_dir.mkdir(parents=True, exist_ok=True)
        self.http_count = len(list(self.http_dir.glob("*.json")))

        self.request_body = request_body
        self.ui_messages = ui_messages
        self.workspace_dir = ui_messages["config"]["workspace_dir"]
        self.tool_map = {}

    def prepare_request_body(self):
        """根据当前会话 ID 与配置，组装并覆盖完整的 request_body 与工具映射表"""
        cfg = self.ui_messages["config"]
        self.request_body["messages"][0]["content"] = cfg["system_prompt"]

        body = {"model": cfg["model"]}

        if "openrouter.ai" in get_harness_config()["url"]:
            body["session_id"] = self.id
            if cfg["provider"]:
                body["provider"] = {
                    "order": [cfg["provider"]],
                    "allow_fallbacks": False,
                }

        tools, self.tool_map = build_tools(cfg["tools"], self.id, self.workspace_dir)
        if tools:
            body["tools"] = tools

        body["messages"] = self.request_body["messages"]
        self.request_body = body

    def update_config(self, cfg: dict):
        """更新当前对话设置并落盘保存"""
        self.ui_messages["config"] = cfg
        self.ui_messages["messages"][0]["content"] = cfg["system_prompt"]
        self.workspace_dir = cfg["workspace_dir"]
        self.prepare_request_body()
        self.save_state()

    @classmethod
    def create(cls, cfg: dict):
        """新建对话：生成 {创建时间戳}_{uuid4} 目录并写入初始文件"""
        time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"{time_str}_{uuid.uuid4()}"

        request_body = {
            "messages": [{"role": "system", "content": cfg["system_prompt"]}],
        }
        ui_messages = {
            "title": make_default_title(session_id),
            "config": cfg,
            "messages": [{"role": "system", "content": cfg["system_prompt"]}],
        }

        session = cls(session_id, request_body, ui_messages)
        session.prepare_request_body()
        session.save_state()
        return session

    @classmethod
    def copy(cls, source_id: str) -> str:
        """复制指定对话到新的 {时间戳}_{uuid4} 目录，并按最大序号自增标题后缀"""
        source_dir = SESSIONS_DIR / source_id
        source_ui = json.loads((source_dir / "ui_messages.json").read_text(encoding="utf-8"))
        source_title = source_ui.get("title") or make_default_title(source_id)

        base = re.sub(r" \(\d+\)$", "", source_title)
        max_num = 0
        for s in list_sessions():
            m = re.fullmatch(rf"{re.escape(base)} \((\d+)\)", s["title"])
            if m:
                max_num = max(max_num, int(m.group(1)))

        time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_id = f"{time_str}_{uuid.uuid4()}"
        new_dir = SESSIONS_DIR / new_id

        shutil.copytree(source_dir, new_dir)

        source_ui["title"] = f"{base} ({max_num + 1})"
        (new_dir / "ui_messages.json").write_text(
            json.dumps(source_ui, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return new_id

    @classmethod
    def delete(cls, session_id: str):
        """删除指定对话的本地目录"""
        shutil.rmtree(SESSIONS_DIR / session_id)

    def rename(self, title: str):
        """修改当前对话标题并落盘保存"""
        self.ui_messages["title"] = title
        self.save_state()

    @classmethod
    def load(cls, session_id: str):
        """按需读档：从本地 sessions/{session_id}/ 还原对话实例"""
        session_dir = SESSIONS_DIR / session_id
        request_body = json.loads((session_dir / "request_body.json").read_text(encoding="utf-8"))
        ui_messages = json.loads((session_dir / "ui_messages.json").read_text(encoding="utf-8"))
        return cls(session_id, request_body, ui_messages)

    def save_state(self):
        """覆盖保存最新的 request_body 和 ui_messages 快照"""
        (self.session_dir / "request_body.json").write_text(
            json.dumps(self.request_body, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (self.session_dir / "ui_messages.json").write_text(
            json.dumps(self.ui_messages, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save_http(self, response_body: dict):
        """按序号和时间戳保存单次 HTTP 请求与响应流水"""
        self.http_count += 1
        time_str = datetime.now().strftime("%H%M%S")
        filename = f"{self.http_count:03d}_{time_str}.json"
        data = {
            "request": self.request_body,
            "response": response_body,
        }
        (self.http_dir / filename).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save_error(self, err_text: str):
        """保存最近一次异常堆栈到 error.txt"""
        (self.session_dir / "error.txt").write_text(err_text, encoding="utf-8")

    def save_assets(self, files: list[dict]) -> list[dict]:
        """将前端传来的 Base64 文件落盘到 assets/ 目录，返回文件元数据"""
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        saved = []
        for f in files:
            suffix = Path(f["name"]).suffix or ".png"
            saved_name = f"{uuid.uuid4()}{suffix}"
            _, b64_data = f["data_url"].split(",", 1)
            (self.assets_dir / saved_name).write_bytes(base64.b64decode(b64_data))
            saved.append({
                "saved_name": saved_name,
                "orig_name": f["name"],
            })
        return saved

    def add_user_message(self, prompt: str, files: list[dict] = None):
        """保存附件并向双轨消息列表追加用户提问与空 assistant 占位，随后落盘"""
        user_content = []
        if prompt:
            user_content.append({"type": "text", "text": prompt})

        user_ui_msg = {
            "role": "user",
            "content": prompt,
            "request_index": len(self.request_body["messages"]),
        }

        if files:
            saved_assets = self.save_assets(files)
            user_ui_msg["assets"] = saved_assets
            for asset in saved_assets:
                img_path = (self.assets_dir / asset["saved_name"]).as_posix()
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": to_image_url(img_path), "detail": "auto"},
                })

        self.request_body["messages"].append({"role": "user", "content": user_content})
        self.ui_messages["messages"].append(user_ui_msg)
        self.ui_messages["messages"].append({"role": "assistant", "blocks": []})
        self.save_state()

    def pop_interrupt(self):
        """移除末尾 assistant 消息的 interrupt 块并落盘"""
        self.ui_messages["messages"][-1]["blocks"].pop()
        self.save_state()

    def rewind(self, ui_index: int) -> str:
        """撤回到指定 user 消息之前，并返回该条 user 消息的文本内容"""
        target_msg = self.ui_messages["messages"][ui_index]
        request_index = target_msg["request_index"]
        content = target_msg["content"]

        self.ui_messages["messages"] = self.ui_messages["messages"][:ui_index]
        self.request_body["messages"] = self.request_body["messages"][:request_index]
        self.save_state()
        return content
