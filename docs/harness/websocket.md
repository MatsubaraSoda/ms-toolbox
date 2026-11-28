# Harness WebSocket 通信协议

本文档记录 Harness 前后端之间的 WebSocket 通信函数约定、消息命名规范与已定义的全部消息类型（`type`），供后续迭代新增或修改通信逻辑时对齐风格。

---

## 1. 收发入口约定

前后端统一通过封装好的收发函数进行通信，将 JSON 字符串的序列化与反序列化隐藏在函数内部，使外层业务逻辑只读写原生的 Python `dict` 或 JavaScript `Object`。后端通过 `webui_clients` 集合维护所有在线的 Web UI 连接，按场景区分**单发（私聊）**与**广播（群发）**：

| 端 | 所在文件 | 发送函数 | 接收函数 | 业务层数据类型 |
| --- | --- | --- | --- | --- |
| **后端 (Python)** | `src/ms_toolbox/harness/main.py` | `send_to_frontend(websocket, data)`（单发）<br>`broadcast_to_frontend(data)`（向 `webui_clients` 广播） | `receive_from_frontend(websocket)` | `dict` |
| **前端 (JS)** | `src/ms_toolbox/harness/site/js/main.js` | `sendToBackend(data)` | `receiveFromBackend(event)` | `Object` |

---

## 2. 命名规范

所有 WebSocket 消息均通过顶层 `"type"` 字段标识类型，且消息体内的所有字段名统一使用 **`snake_case`**（全小写下划线分隔）。

### 2.1 `type` 三类语法格式

按通信方向与语义，`"type"` 严格遵循以下三类命名格式：

1. **动作请求（前端 ➔ 后端）**：采用 **`<动词原形>_<目标名词>`** 格式（如 `load_session`），表示请求后端对指定对象执行某项操作。
2. **完成回执（后端 ➔ 前端）**：采用 **`<目标名词>_<动词过去分词>`** 格式（如 `session_loaded`），表示前端发起的某项操作已处理完毕并返回结果。
3. **状态同步（后端 ➔ 前端）**：采用 **`<状态名词>`** 格式（如 `running_state`），表示后端向前端推送最新状态快照、流式增量或错误提示。

> 注：并非每个「动作请求」都必须返回「完成回执」。部分指令仅触发本地操作（如 `open_settings`），或直接触发「状态同步」广播（如 `start_container` 触发 `container_state`）。

### 2.2 核心对象词边界：`session` vs `chat`

为避免“对话”在英文命名中产生混淆，按静态存档与动态运行划分如下：

- **`session`（会话存档）**：指代持久化的会话档案与历史记录本身。用于新建准备、读取切换、复制、重命名、删除、历史回溯截断（`init_session`、`load_session`、`copy_session`、`rename_session`、`delete_session`、`rewind_session`）。
- **`chat`（问答运行）**：指代会话内部单轮对话的动态执行流。用于提交提问、中断生成、继续执行（`submit_chat`、`stop_chat`、`continue_chat`）。

---

## 3. 消息类型清单

### 3.1 前端 ➔ 后端：动作请求（`<动词原形>_<目标名词>`）

| `type` | 触发时机 | 附带字段（除 `type` 外） | 对应后端响应 |
| --- | --- | --- | --- |
| `init_session` | 点击左侧「+ 新建对话」重置界面 | 无 | `init_state` |
| `load_session` | 点击左侧历史会话，或断线重连后恢复当前会话 | `session_id` | `session_loaded` |
| `copy_session` | 点击左侧会话菜单中的「复制」 | `session_id` | `session_copied` |
| `rename_session` | 点击左侧会话菜单中的「重命名」并确认新标题 | `session_id`, `title` | `session_renamed` |
| `delete_session` | 点击左侧会话菜单中的「删除」并确认 | `session_id` | `session_deleted`（若已启动容器则额外推送 `container_state`） |
| `rewind_session` | 点击用户消息旁的 `↩` 撤销此条及之后的对话 | `session_id`, `ui_index` | `session_rewound` |
| `submit_chat` | 在输入框发送消息（含文本或图片附件） | `session_id`, `content`, `files`, `config`（仅新会话首条携带） | 新会话首条先回 `session_loaded`（校验失败回 `workspace_error`），随后推送 `running_state`、`stream_delta`、`messages` |
| `stop_chat` | 运行中点击 `⏹` 停止按钮 | `session_id` | 取消后台任务，触发 `messages` 与 `running_state` |
| `continue_chat` | 点击中断提示框的「继续执行 / 点击重试」 | `session_id` | 推送 `running_state`、`stream_delta`、`messages` |
| `update_config` | 右侧边栏编辑当前会话配置后点击保存 | `session_id`, `config` | `config_updated`（目录不存在回 `workspace_error`；工作区目录或 `docker_image` 变更且容器已启动时额外推送 `container_state`） |
| `pick_dir` | 右侧边栏点击 `...` 选择工作区文件夹 | 无 | 选中目录后回 `dir_picked`（取消弹窗则无返回） |
| `open_settings` | 点击左侧底部 `⚙ 设置` 打开 `config.yaml` | 无 | 无（直接调用系统默认编辑器） |
| `open_presets` | 点击右侧预设栏 `⚙` 打开 `presets.yaml` | 无 | 无（直接调用系统默认编辑器） |
| `reload_presets` | 浏览器窗口重新获得焦点（`focus` 事件） | 无 | `presets_updated` |
| `start_container` | 右侧边栏手动点击 `start_container` | `session_id` | `container_state` |
| `stop_container` | 右侧边栏手动点击 `stop_container` | `session_id` | `container_state` |

---

### 3.2 后端 ➔ 前端：完成回执（`<目标名词>_<动词过去分词>`）

完成回执均通过 `send_to_frontend` **单发**给发起该请求的客户端连接：

| `type` | 发送时机 | 附带字段（除 `type` 外） |
| --- | --- | --- |
| `session_loaded` | `load_session` 读取完毕，或新会话首条 `submit_chat` 创建会话目录后 | `session_id`, `ui_messages`, `sessions` |
| `session_copied` | `copy_session` 复制会话目录并生成新标题后 | `sessions` |
| `session_renamed` | `rename_session` 更新会话标题并落盘后 | `sessions` |
| `session_deleted` | `delete_session` 清理容器与本地会话目录后 | `session_id`, `sessions` |
| `session_rewound` | `rewind_session` 截断双轨历史并落盘后 | `session_id`, `messages`, `content`（回填输入框的原文本）, `sessions` |
| `config_updated` | `update_config` 校验通过并保存配置后 | `session_id`, `ui_messages` |
| `dir_picked` | `pick_dir` 系统文件夹选择框返回有效路径后 | `path` |
| `presets_updated` | `reload_presets` 重新读取预设列表后 | `presets` |

---

### 3.3 后端 ➔ 前端：状态同步（`<状态名词>`）

| `type` | 发送方式 | 发送时机 | 附带字段（除 `type` 外） |
| --- | --- | --- | --- |
| `init_state` | 单发 | WebSocket 连接刚建立时，或收到 `init_session` 时 | `presets`, `sessions`, `running_sessions`, `active_containers` |
| `messages` | 广播 | 会话消息快照更新时（用户提问入列、模型响应完成、工具调用完成、任务中断等） | `session_id`, `data`（UI 消息列表）, `sessions`, `active_containers` |
| `stream_delta` | 广播 | 流式输出期间，每收到一段思考或正文增量时 | `session_id`, `block_type`（`"thought"` \| `"text"`）, `delta` |
| `running_state` | 广播 | 后台会话任务启动或结束时 | `running_sessions` |
| `container_state` | 广播 | 容器手动启停，或修改工作区目录 / `docker_image` 导致旧容器停止时 | `active_containers` |
| `workspace_error` | 单发 | 新会话首条 `submit_chat` 或 `update_config` 校验工作区目录不存在时 | `message` |
