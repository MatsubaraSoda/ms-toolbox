import asyncio
import json
import threading

import requests

from ms_toolbox.harness.config import get_harness_config

# 流式传输开关：仅在服务启动加载模块时读取一次（未填写留空时默认为 True）
_raw_stream = get_harness_config().get("stream")
STREAM = True if _raw_stream is None else bool(_raw_stream)


def iter_sse_chunks(lines):
    """过滤空行、心跳注释与结束符，逐个产出解析后的 chunk 字典"""
    for line in lines:
        if not line or line.startswith(":"):
            continue
        if line == "data: [DONE]":
            break
        if line.startswith("data: "):
            yield json.loads(line[6:])


class StreamAssembler:
    """将流式增量 chunk 逐帧拼回与非流式结构一致的 response_body"""

    def __init__(self):
        self.id = ""
        self.model = ""
        self.content = ""
        self.reasoning = ""
        self.reasoning_details = {}  # 按 (type, index) 槽位暂存，避免流式 index 撞车
        self.tool_calls = {}         # 按 index 槽位暂存
        self.finish_reason = None
        self.usage = None
        self.error = None

    def feed(self, chunk: dict):
        if "error" in chunk:
            self.error = chunk["error"]
            return

        self.id = chunk.get("id") or self.id
        self.model = chunk.get("model") or self.model
        if chunk.get("usage"):
            self.usage = chunk["usage"]

        if not chunk.get("choices"):
            return

        choice = chunk["choices"][0]
        if choice.get("finish_reason"):
            self.finish_reason = choice["finish_reason"]

        delta = choice.get("delta") or {}

        if delta.get("content"):
            self.content += delta["content"]
        if delta.get("reasoning"):
            self.reasoning += delta["reasoning"]

        for detail in delta.get("reasoning_details") or []:
            key = (detail["type"], detail["index"])
            if key not in self.reasoning_details:
                self.reasoning_details[key] = dict(detail)
            elif detail["type"] == "reasoning.text":
                self.reasoning_details[key]["text"] += detail["text"]

        for tc in delta.get("tool_calls") or []:
            idx = tc["index"]
            if idx not in self.tool_calls:
                self.tool_calls[idx] = {
                    "index": idx,
                    "id": "",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                }
            target = self.tool_calls[idx]
            if tc.get("id"):
                target["id"] += tc["id"]
            fn = tc.get("function") or {}
            if fn.get("name"):
                target["function"]["name"] += fn["name"]
            if fn.get("arguments"):
                target["function"]["arguments"] += fn["arguments"]

    def build(self) -> dict:
        if self.error:
            return {"error": self.error}

        message = {
            "role": "assistant",
            "content": self.content or None,
        }
        if self.reasoning:
            message["reasoning"] = self.reasoning
        if self.reasoning_details:
            message["reasoning_details"] = [
                {**item, "index": i}
                for i, item in enumerate(self.reasoning_details.values())
            ]
        if self.tool_calls:
            message["tool_calls"] = [
                self.tool_calls[i] for i in sorted(self.tool_calls)
            ]

        result = {
            "id": self.id,
            "model": self.model,
            "choices": [{
                "index": 0,
                "message": message,
                "finish_reason": self.finish_reason,
            }],
        }
        if self.usage:
            result["usage"] = self.usage
        return result


async def _fetch_non_stream(url: str, headers: dict, request_body: dict) -> dict:
    """非流式请求：等待上游生成完毕后一次性返回完整 JSON"""
    response = await asyncio.to_thread(
        requests.post, url, json=request_body, headers=headers
    )
    return response.json()


async def _fetch_stream(url: str, headers: dict, request_body: dict, on_delta=None) -> dict:
    """流式请求：边读 SSE 帧边通过回调推送增量，结束后拼回完整 response_body"""
    body = {
        **request_body,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    assembler = StreamAssembler()
    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    stop_event = threading.Event()

    def pump_sse():
        try:
            with requests.post(url, json=body, headers=headers, stream=True) as response:
                response.encoding = "utf-8"
                if not response.ok:
                    loop.call_soon_threadsafe(queue.put_nowait, response.json())
                else:
                    for chunk in iter_sse_chunks(response.iter_lines(decode_unicode=True)):
                        if stop_event.is_set():
                            break
                        loop.call_soon_threadsafe(queue.put_nowait, chunk)
            loop.call_soon_threadsafe(queue.put_nowait, None)
        except Exception as e:
            loop.call_soon_threadsafe(queue.put_nowait, e)

    threading.Thread(target=pump_sse, daemon=True).start()

    try:
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            if isinstance(chunk, Exception):
                raise chunk

            assembler.feed(chunk)

            if on_delta and chunk.get("choices"):
                delta = chunk["choices"][0].get("delta") or {}
                if delta.get("reasoning"):
                    await on_delta("thought", delta["reasoning"])
                if delta.get("content"):
                    await on_delta("text", delta["content"])
    finally:
        stop_event.set()

    return assembler.build()


async def fetch_llm(request_body: dict, on_delta=None) -> dict:
    """统一发送大模型请求（自动根据启动时的 STREAM 配置选择流式或非流式），返回完整 response_body"""
    cfg = get_harness_config()
    url = cfg["url"]
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "HTTP-Referer": "https://github.com/MatsubaraSoda/ms-toolbox",
        "X-OpenRouter-Title": "ms-toolbox",
        "Content-Type": "application/json",
    }

    if STREAM:
        return await _fetch_stream(url, headers, request_body, on_delta)
    return await _fetch_non_stream(url, headers, request_body)
