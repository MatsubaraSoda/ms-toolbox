# Harness 会话存档与双轨消息契约

本文档记录 Harness 本地会话目录的文件布局、`ui_messages.json`（前端渲染轨）与 `request_body.json`（模型请求轨）的数据结构契约，以及双轨状态的对齐与回溯机制，供后续调整持久化结构、消息渲染或上游协议兼容逻辑时对齐规范。

---

## 1. 会话目录与文件布局

所有历史会话均保存在 `%LOCALAPPDATA%\ms-toolbox\harness\sessions\`（即 `config.SESSIONS_DIR`）下，每个会话独占一个子目录：

### 1.1 `session_id` 命名规范

会话目录名即 `session_id`，固定采用 **`{YYYYMMDD_HHMMSS}_{uuid4}`** 格式（例如 `20261117_205125_07f55bc3-...`）：

- `session.make_default_title()` 直接依赖该固定字符位置切片生成初始默认标题（如 `11-17 20:51 · 07f55bc3`）。
- `session.list_sessions()` 扫描所有包含 `ui_messages.json` 的会话目录，按 `ui_messages.json` 的最后修改时间（`st_mtime`）**从新到旧**排序返回。

### 1.2 目录内文件职责

| 路径 | 生成时机 | 说明 |
| --- | --- | --- |
| `ui_messages.json` | 会话创建时生成，每次状态变更覆盖保存 | **前端渲染轨**：保存会话标题、会话级配置快照与供 Web UI 展示的消息列表 |
| `request_body.json` | 会话创建时生成，每次状态变更覆盖保存 | **模型请求轨**：保存可直接发送给 `chat/completions` 接口的完整请求体快照 |
| `assets/` | 首次上传图片附件或调用生图工具时创建 | 存放用户上传图片与模型生成图片，文件统一重命名为 `{uuid4}.{ext}`，并通过 HTTP `/sessions/{session_id}/assets/{filename}` 暴露给前端访问 |
| `http_logs/` | 会话初始化时创建，每次收到大模型响应后按序追加 | 存放 `{三位序号}_{HHMMSS}.json`（如 `001_205130.json`），记录单次调用的原始 `{"request": ..., "response": ...}` 流水 |
| `error.txt` | 请求大模型或解析响应抛出异常时写入 | 覆盖保存最近一次异常的完整 Python 堆栈信息，便于排查报错现场 |

---

## 2. `ui_messages.json` 结构契约（前端渲染轨）

`ui_messages.json` 面向前端界面展示设计，顶层结构如下：

```json
{
  "title": "11-17 20:51 · 07f55bc3",
  "config": {
    "workspace_dir": "D:/path/to/project",
    "model": "google/gemini-4-carbon",
    "provider": "google-ai-studio/flex",
    "tools": ["base", "run_command"],
    "system_prompt": "你是一位助手..."
  },
  "messages": []
}
```

### 2.1 三类消息角色（`messages` 元素）

| `role` | 出现位置 | 字段结构 | 说明 |
| --- | --- | --- | --- |
| `system` | 固定位于索引 `0` | `role`, `content` (`str`) | 系统提示词；在右侧边栏修改 `system_prompt` 保存时同步更新 |
| `user` | 每轮用户提问追加一条 | `role`, `content` (`str`), `request_index` (`int`), `assets` (`list[dict]`, 可选) | `request_index` 记录追加前 `request_body["messages"]` 的长度；若有图片附件，`assets` 元素格式为 `{"saved_name": str, "orig_name": str}` |
| `assistant` | 紧跟在每条 `user` 消息之后 | `role`, `blocks` (`list[dict]`) | 不设顶层 `content`，单轮 Agent 多步循环产生的所有思考、工具调用、正文与中断状态均按序追加进同一个 `blocks` 数组 |

### 2.2 `assistant.blocks` 四类内容块契约

后端 `runtime.py` 写入与前端 `message-list.js` 渲染严格对齐以下 4 种 `block.type`：

| `type` | 必填字段 | 可选字段 | 前端渲染行为 |
| --- | --- | --- | --- |
| `thought` | `content` (`str`) | 无 | 渲染为折叠的 `<details>`（标题 `💭 思考过程`），内部按 Markdown + MathJax 渲染 |
| `text` | `content` (`str`) | 无 | 直接渲染为正文 Markdown + MathJax 块 |
| `tool` | `name` (`str`), `args` (`dict`), `result` (`str`) | `<func_name>`（与工具同名的扩展字段） | 渲染为 `<details>` 展示入参 JSON 与纯文本结果；若存在工具同名扩展字段（如 `generate_image: ["xxx.png"]`），自动附加对应的定制视图 |
| `interrupt` | `reason` (`"max_steps"` \| `"stopped"` \| `"error"`) | `detail` (`str`) | 渲染中断提示框与「继续执行 / 点击重试」按钮；始终位于末尾 `assistant` 消息的最后一项，`continue_chat` 时由 `pop_interrupt()` 弹出 |

---

## 3. `request_body.json` 结构契约（模型请求轨）

`request_body.json` 面向 OpenRouter `chat/completions` 接口设计。每次启动循环或更新会话配置时，`Session.prepare_request_body()` 会根据当前 `config` 重新组装顶层参数并挂载 `messages` 历史：

- **KV 缓存与渠道锁定**：顶层自动携带 `session_id`；当配置了 `provider` 时，固定组装 `"provider": {"order": [cfg["provider"]], "allow_fallbacks": False}` 锁定单一上游渠道，避免请求在不同提供商之间漂移导致 KV 缓存失效。

为屏蔽不同上游模型与网关的协议怪癖，`request_body["messages"]` 遵循以下四条写入约定：

1. **用户图片压缩与编码**：用户上传的本地图片经 `to_image_url()` 等比缩放至长边不超过 `1568px` 并转为 WebP 格式的 Base64 Data URL，与文本一同组装为 `content` 数组（`text` + `image_url`）。
2. **思考签名原样回传（`reasoning_details`）**：当上游响应的 `message` 中包含 `reasoning_details`（例如 Gemini `google-vertex/global` 渠道在触发工具调用时附带的加密思考签名）时，原封不动存入该条 `assistant` 消息并随后续轮次带回，防止上游校验失败断流。
3. **工具返回值 JSON 对象包裹**：`role: "tool"` 消息的 `content` 统一包裹为 `json.dumps({"result": tool_result.result})`，防止以 `[` 或 `{` 开头的纯文本内容（如 `pyproject.toml`）被 OpenRouter / Gemini 协议转换器误判为 JSON 结构强行解析而截断丢失；`ui_messages` 中的 `tool.result` 则保留原始纯文本。
4. **工具多模态结果借道 `user` 消息**：由于主流接口不支持在 `role: "tool"` 中直接回传图片，当一轮并行 `tool_calls` 全部执行并写入 `tool` 消息闭合后，若工具产出了 `pending_user_content`（如 `view_image`），统一追加一条 `role: "user"` 消息携带这些多模态块供模型下一轮查看。

---

## 4. 双轨对齐与对话回溯（`rewind`）

由于以下原因，`ui_messages["messages"]` 与 `request_body["messages"]` 的列表长度在运行过程中**并非 1:1 对应**：

- 单轮问答若触发多步工具调用，`request_body` 会新增多组 `assistant` ➔ `tool`（及可选的借道 `user`）消息，而 `ui_messages` 始终只合并追加在末尾同一条 `assistant` 消息的 `blocks` 内。
- `interrupt` 中断提示块仅记录在 `ui_messages` 中，不污染发给大模型的 `request_body`。

### 锚点截断机制

1. **打锚点**：每次调用 `Session.add_user_message()` 时，先读取当前 `len(self.request_body["messages"])` 存入该条 UI `user` 消息的 `"request_index"` 字段，随后再向双轨追加新消息。
2. **双轨同步截断**：当用户在前端点击第 `ui_index` 条消息旁的 `↩` 按钮触发 `Session.rewind(ui_index)` 时，后端取出该条消息记录的 `request_index`，同步执行切片：
   - `ui_messages["messages"] = ui_messages["messages"][:ui_index]`
   - `request_body["messages"] = request_body["messages"][:request_index]`

由此，该轮提问及之后产生的所有模型回复、工具调用与借道消息在两条轨道上被精确清空，同时原提问文本返回前端回填至输入框。
