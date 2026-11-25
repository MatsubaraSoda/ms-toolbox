import asyncio
import json
import traceback

from ms_toolbox.harness.config import get_harness_config
from ms_toolbox.harness.llm import fetch_llm
from ms_toolbox.harness.session import Session, list_sessions
from ms_toolbox.harness.tools.run_command import active_containers
from ms_toolbox.harness.tools.utils import ToolResult

# 记录当前正在后台等待大模型响应或执行工具的会话任务
running_tasks: dict[str, asyncio.Task] = {}


def get_running_sessions() -> list[str]:
    """返回当前正在后台运行的会话 ID 列表"""
    return list(running_tasks)


def is_running(session_id: str) -> bool:
    """判断指定会话当前是否正在后台运行"""
    return session_id in running_tasks


def stop_chat(session_id: str):
    """取消指定会话正在运行的后台任务"""
    task = running_tasks.get(session_id)
    if task:
        task.cancel()


async def _send_running_state(send_fn):
    await send_fn({
        "type": "running_state",
        "running_sessions": list(running_tasks),
    })


async def _save_and_notify(session: Session, send_fn):
    session.save_state()
    await send_fn({
        "type": "messages",
        "session_id": session.id,
        "data": session.ui_messages["messages"],
        "sessions": list_sessions(),
        "active_containers": list(active_containers),
    })


async def _start_task(session: Session, send_fn):
    """将耗时 Agent 循环放入 running_tasks 托管，启动和结束时自动同步运行状态"""
    async def runner():
        try:
            await run_agent_loop(session, send_fn)
        except asyncio.CancelledError:
            pass
        finally:
            running_tasks.pop(session.id, None)
            await _send_running_state(send_fn)

    running_tasks[session.id] = asyncio.create_task(runner())
    await _send_running_state(send_fn)


async def start_chat(session: Session, prompt: str, files: list[dict] | None, send_fn):
    """记录用户提问与附件，并启动后台 Agent 循环"""
    session.add_user_message(prompt, files)
    await _start_task(session, send_fn)


async def continue_chat(session: Session, send_fn):
    """移除末尾中断块，并继续后台 Agent 循环"""
    session.pop_interrupt()
    await _start_task(session, send_fn)


async def run_agent_loop(session: Session, send_fn):
    raw_steps = get_harness_config().get("max_steps")
    max_steps = 5 if raw_steps in (None, "") else int(raw_steps)

    ui_assistant = session.ui_messages["messages"][-1]
    pending_tool_calls: list[tuple[dict, dict]] = []
    pending_user_content: list[dict] = []

    async def handle_delta(block_type: str, delta: str):
        await send_fn({
            "type": "stream_delta",
            "session_id": session.id,
            "block_type": block_type,
            "delta": delta,
        })

    step = 0
    try:
        session.prepare_request_body()
        await _save_and_notify(session, send_fn)

        while True:
            step += 1

            try:
                response_body = await fetch_llm(session.request_body, on_delta=handle_delta)

                # 拿到响应后第一时间落盘，防止后续解析字段报错导致丢失现场
                session.save_http(response_body)

                # 1. 拦截最外层错误（如 429 限流、401 鉴权失败等）
                if "error" in response_body:
                    err = response_body["error"]
                    if err.get("code") == 429:
                        raise Exception("429 触发上游限流（Rate Limit），请稍等几秒后点击重试")
                    raise Exception(err.get("message") or err)

                # 2. 拦截生成中途错误（如上游 502 断流，错误藏在 choices[0] 里）
                choice = response_body["choices"][0]
                if "error" in choice or choice.get("finish_reason") == "error":
                    err = choice.get("error") or {}
                    raise Exception(err.get("message") or "上游生成中途异常中断")

                msg = choice["message"]

                # 3. 先验货：提前解析所有工具参数，防止半截坏 JSON 混入后续的 request_body 和 UI
                parsed_args_list = [
                    json.loads(tc["function"]["arguments"])
                    for tc in msg.get("tool_calls") or []
                ]
            except Exception as e:
                err = traceback.format_exc()
                print(err)
                session.save_error(err)

                # reason="error": 网络连接中断、上游接口报错（429/5XX 等）或工具参数 JSON 解析失败
                ui_assistant["blocks"].append({
                    "type": "interrupt",
                    "reason": "error",
                    "detail": str(e),
                })
                break

            assistant_message = {
                "role": "assistant",
                "content": msg["content"],
            }
            if msg.get("tool_calls"):
                assistant_message["tool_calls"] = msg["tool_calls"]
                pending_tool_calls = list(zip(assistant_message["tool_calls"], parsed_args_list))
            # google-vertex/global 渠道的特殊要求：
            # 当 Gemini 思考模型发起工具调用（tool_calls）时，响应里会附带加密的思考签名 reasoning_details。
            # google-ai-studio/flex 对此校验较宽松，但 google-vertex/global 强制要求下一轮回传消息历史时
            # 必须原封不动带回该字段，否则上游服务器会拒绝响应甚至直接断开连接。
            if msg.get("reasoning_details"):
                assistant_message["reasoning_details"] = msg["reasoning_details"]

            session.request_body["messages"].append(assistant_message)

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

            if "tool_calls" not in assistant_message:
                break

            await _save_and_notify(session, send_fn)

            while pending_tool_calls:
                tool_call, func_args = pending_tool_calls[0]
                call_id = tool_call["id"]
                func_name = tool_call["function"]["name"]

                tool_func = session.tool_map[func_name]
                try:
                    tool_result = await asyncio.to_thread(tool_func, **func_args)
                except Exception:
                    error_detail = traceback.format_exc()
                    tool_result = (
                        f"工具执行报错了！详细堆栈如下：\n{error_detail}\n"
                        "请分析原因：\n"
                        "1. 如果是你的参数传错了，请修正参数后重试。\n"
                        "2. 如果看起来是工具本身的 Python 代码写错了（即 Harness 存在 Bug），"
                        "请不要重试，直接停止并向我汇报这个 Bug！"
                    )

                if not isinstance(tool_result, ToolResult):
                    tool_result = ToolResult(str(tool_result))

                tool_block = {
                    "type": "tool",
                    "name": func_name,
                    "args": func_args,
                    "result": tool_result.result,
                }
                if tool_result.details_extra is not None:
                    tool_block[func_name] = tool_result.details_extra

                pending_tool_calls.pop(0)
                pending_user_content.extend(tool_result.pending_user_content)

                # 避免 OpenRouter 协议转换器误解析纯文本内容：
                # Gemini 原生接口强制要求工具返回值必须是 JSON 对象（字典）。当直接传入纯字符串且恰好以
                # "[" 或 "{" 开头（例如读取首行为 [project] 的 pyproject.toml）时，OpenRouter 会误将其
                # 当作 JSON 数组/对象强行解析，导致文件内容残缺丢失。
                # 因此在发给模型时统一包裹为合法的 JSON 对象字符串（同时对 OpenAI/Claude 等模型也完全兼容），
                # 而下方的 ui_assistant 则继续保留原始纯文本以保证前端阅读体验。
                session.request_body["messages"].append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps({"result": tool_result.result}, ensure_ascii=False),
                })

                # 所有 tool 消息闭合后，若本轮有工具请求借道传递多模态内容，统一追加一条 user 消息
                if not pending_tool_calls and pending_user_content:
                    session.request_body["messages"].append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "以下是工具加载的多模态附件内容："},
                            *pending_user_content,
                        ],
                    })
                    pending_user_content.clear()

                ui_assistant["blocks"].append(tool_block)
                await _save_and_notify(session, send_fn)

            if max_steps > 0 and step >= max_steps:
                # reason="max_steps": 本轮工具已执行完毕，但连续循环步数达到 max_steps 上限
                ui_assistant["blocks"].append({
                    "type": "interrupt",
                    "reason": "max_steps",
                })
                break

    except asyncio.CancelledError:
        for tool_call, func_args in pending_tool_calls:
            stop_msg = "用户手动停止了工具执行"
            session.request_body["messages"].append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": json.dumps({"result": stop_msg}, ensure_ascii=False),
            })
            ui_assistant["blocks"].append({
                "type": "tool",
                "name": tool_call["function"]["name"],
                "args": func_args,
                "result": stop_msg,
            })

        if pending_user_content:
            session.request_body["messages"].append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "以下是工具加载的多模态附件内容："},
                    *pending_user_content,
                ],
            })

        # reason="stopped": 用户手动点击停止按钮取消了正在运行的请求或工具任务
        ui_assistant["blocks"].append({
            "type": "interrupt",
            "reason": "stopped",
        })

    await _save_and_notify(session, send_fn)
