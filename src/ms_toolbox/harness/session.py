import asyncio
import json
import traceback
import uuid
from datetime import datetime
from pathlib import Path

import requests

from ms_toolbox.harness.config import CONFIG_YAML, get_harness_config
from ms_toolbox.harness.tools.base import edit_file, list_files, read_file, write_file
from ms_toolbox.harness.tools.utils import function_to_tool, to_image_url

# 所有对话持久化目录：与 config.yaml 同级的 sessions/ 文件夹
SESSIONS_DIR = CONFIG_YAML.parent / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

TOOLS = [list_files, read_file, write_file, edit_file]


def list_sessions() -> list[str]:
    """扫描本地 sessions/ 文件夹，按最后编辑时间从新到旧排序"""
    dirs = [d for d in SESSIONS_DIR.iterdir() if (d / "ui_messages.json").exists()]
    dirs.sort(key=lambda d: (d / "ui_messages.json").stat().st_mtime, reverse=True)
    return [d.name for d in dirs]


class Session:
    def __init__(self, session_id: str, request_body: dict, ui_messages: dict, on_update=None):
        self.id = session_id
        self.on_update = on_update

        self.session_dir = SESSIONS_DIR / session_id
        self.http_dir = self.session_dir / "http_logs"
        self.http_dir.mkdir(parents=True, exist_ok=True)
        self.http_count = len(list(self.http_dir.glob("*.json")))

        raw = get_harness_config()
        self.url = raw["url"]
        self.headers = {
            "Authorization": f"Bearer {raw['api_key']}",
            "HTTP-Referer": "https://github.com/MatsubaraSoda/ms-toolbox",
            "X-OpenRouter-Title": "ms-toolbox",
            "Content-Type": "application/json",
        }

        self.request_body = request_body
        self.ui_messages = ui_messages
        self.workspace_dir = ui_messages["config"]["workspace_dir"]

        self.tools = []
        self.tool_map = {}
        for func in TOOLS:
            self.register_tool(func)
        self.request_body["tools"] = self.tools

    @classmethod
    def create(cls, cfg: dict, on_update=None):
        """新建对话：生成 {创建时间戳}_{uuid4} 目录并写入初始文件"""
        time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"{time_str}_{uuid.uuid4()}"

        request_body = {
            "messages": [{"role": "system", "content": cfg["system_prompt"]}],
            "tools": [],
            "model": cfg["model"],
            "provider": {
                "order": [cfg["provider"]],
                "allow_fallbacks": False,
            },
        }
        ui_messages = {
            "config": cfg,
            "messages": [{"role": "system", "content": cfg["system_prompt"]}],
        }

        session = cls(session_id, request_body, ui_messages, on_update)
        session.save_state()
        return session

    @classmethod
    def load(cls, session_id: str, on_update=None):
        """按需读档：从本地 sessions/{session_id}/ 还原对话实例"""
        session_dir = SESSIONS_DIR / session_id
        request_body = json.loads((session_dir / "request_body.json").read_text(encoding="utf-8"))
        ui_messages = json.loads((session_dir / "ui_messages.json").read_text(encoding="utf-8"))
        return cls(session_id, request_body, ui_messages, on_update)

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

    def save_http(self, response_body):
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

    async def notify(self):
        self.save_state()
        if self.on_update:
            await self.on_update(self.id, self.ui_messages["messages"])

    def register_tool(self, func):
        """自动将函数注册到 tool_map 和 tools 中"""
        self.tools.append(function_to_tool(func))
        self.tool_map[func.__name__] = self.ensure_in_workspace_dir(func)

    def ensure_in_workspace_dir(self, func):
        """限制路径必须在 self.workspace_dir 内"""
        def wrapper(**kwargs):
            if "path" in kwargs:
                path = kwargs["path"]
                base_dir = Path(self.workspace_dir).resolve()
                target_path = (base_dir / path).resolve()

                if not target_path.is_relative_to(base_dir):
                    return f"访问被拒绝：路径 '{path}' 位于工作区之外。"

                kwargs["path"] = target_path.as_posix()
            return func(**kwargs)
        return wrapper

    async def chat(self, prompt: str, images: list[str] = None) -> str:
        user_content = [{"type": "text", "text": prompt}]
        if images:
            for img in images:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": to_image_url(img), "detail": "auto"},
                })

        self.request_body["messages"].append({"role": "user", "content": user_content})

        self.ui_messages["messages"].append({"role": "user", "content": prompt})
        self.ui_messages["messages"].append({"role": "assistant", "blocks": []})
        await self.notify()

        return await self.run_agent_loop()

    async def continue_chat(self) -> str:
        """移除末尾的 continue 占位块并继续执行 Agent 循环"""
        self.ui_messages["messages"][-1]["blocks"].pop()
        await self.notify()
        return await self.run_agent_loop()

    async def run_agent_loop(self, max_steps: int = 5) -> str:
        ui_assistant = self.ui_messages["messages"][-1]

        for _ in range(max_steps):
            try:
                response = await asyncio.to_thread(
                    requests.post, self.url, json=self.request_body, headers=self.headers
                )
                response_body = response.json()

                # 拿到响应后第一时间落盘，防止后续解析字段报错导致丢失现场
                self.save_http(response_body)

                # 针对 Google AI Studio 共享池偶发的 HTTP 429 限流错误给出明确提示
                if "error" in response_body and response_body["error"].get("code") == 429:
                    raise Exception("429 触发上游限流（Rate Limit），请稍等几秒后点击重试")

                msg = response_body["choices"][0]["message"]
            except Exception as e:
                err = traceback.format_exc()
                print(err)
                (self.session_dir / "error.txt").write_text(err, encoding="utf-8")

                ui_assistant["blocks"].append({
                    "type": "error",
                    "content": f"请求中断: {e}",
                })
                await self.notify()
                return ""

            assistant_message = {
                "role": "assistant",
                "content": msg["content"],
            }
            if msg.get("tool_calls"):
                assistant_message["tool_calls"] = msg["tool_calls"]
            # google-vertex/global 渠道的特殊要求：
            # 当 Gemini 思考模型发起工具调用（tool_calls）时，响应里会附带加密的思考签名 reasoning_details。
            # google-ai-studio/flex 对此校验较宽松，但 google-vertex/global 强制要求下一轮回传消息历史时
            # 必须原封不动带回该字段，否则上游服务器会拒绝响应甚至直接断开连接。
            if msg.get("reasoning_details"):
                assistant_message["reasoning_details"] = msg["reasoning_details"]

            self.request_body["messages"].append(assistant_message)

            if msg.get("reasoning"):
                ui_assistant["blocks"].append({
                    "type": "thought",
                    "content": msg["reasoning"],
                })

            if msg.get("content"):
                ui_assistant["blocks"].append({
                    "type": "text",
                    "content": msg["content"],
                })

            await self.notify()

            if "tool_calls" in assistant_message:
                for tool_call in assistant_message["tool_calls"]:
                    id = tool_call["id"]
                    func_name = tool_call["function"]["name"]
                    func_args = json.loads(tool_call["function"]["arguments"])

                    tool_func = self.tool_map[func_name]
                    try:
                        result = tool_func(**func_args)
                    except Exception:
                        error_detail = traceback.format_exc()
                        result = (
                            f"工具执行报错了！详细堆栈如下：\n{error_detail}\n"
                            "请分析原因：\n"
                            "1. 如果是你的参数传错了，请修正参数后重试。\n"
                            "2. 如果看起来是工具本身的 Python 代码写错了（即 Harness 存在 Bug），"
                            "请不要重试，直接停止并向我汇报这个 Bug！"
                        )

                    # 避免 OpenRouter 协议转换器误解析纯文本内容：
                    # Gemini 原生接口强制要求工具返回值必须是 JSON 对象（字典）。当直接传入纯字符串且恰好以
                    # "[" 或 "{" 开头（例如读取首行为 [project] 的 pyproject.toml）时，OpenRouter 会误将其
                    # 当作 JSON 数组/对象强行解析，导致文件内容残缺丢失。
                    # 因此在发给模型时统一包裹为合法的 JSON 对象字符串（同时对 OpenAI/Claude 等模型也完全兼容），
                    # 而下方的 ui_assistant 则继续保留原始纯文本以保证前端阅读体验。
                    self.request_body["messages"].append({
                        "role": "tool",
                        "tool_call_id": id,
                        "content": json.dumps({"result": str(result)}, ensure_ascii=False),
                    })

                    ui_assistant["blocks"].append({
                        "type": "tool",
                        "name": func_name,
                        "args": func_args,
                        "result": str(result),
                    })
                    await self.notify()
            else:
                return assistant_message["content"]
        else:
            ui_assistant["blocks"].append({"type": "continue"})
            await self.notify()
            return ""
