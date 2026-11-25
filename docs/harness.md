# Harness (msh)

一个用于学习与实践大模型 Agent 原理的轻量级本地 Web UI Harness Toy。当前基于 OpenRouter 驱动，支持多会话管理、流式思考与正文展示，以及工作区文件读写、Docker 容器命令执行、联网检索与图片生成/查看等工具调用。

## 快速启动

```bash
# 使用 config.yaml 中的默认端口（8000）启动
msh

# 临时指定其他端口启动
msh --port 8080
```

启动后在浏览器访问终端输出的本地地址（默认 `http://localhost:8000`）即可打开交互界面。

## 配置说明

首次运行时，程序会在用户配置目录的 `harness/` 子目录（Windows 下为 `%LOCALAPPDATA%\ms-toolbox\harness\`）自动生成配置文件与会话目录：

- **`config.yaml`**：全局服务配置与 `default` 默认对话预设（可点击网页左侧边栏底部的 `⚙ 设置` 按钮打开）。
- **`presets.yaml`**：自定义多套常用对话预设（可点击右侧边栏预设栏的 `⚙` 按钮打开，切回浏览器窗口自动刷新下拉选项）。
- **`sessions/`**：所有历史对话的持久化数据目录。

`harness/config.yaml` 配置项如下：

```yaml
port: 8000                                # 默认监听端口（可通过命令行 --port 覆盖）
max_steps: 5                              # 单次最大循环步数（留空默认 5，设为 0 则无限循环）
stream: true                              # 是否启用流式输出（启动时读取一次，留空默认 true；设为 false 则等待完整响应后一次性渲染）
workspace_dir: D:/path/to/your/project    # 默认工作区目录（可在新建或编辑会话时通过网页修改或弹窗选择）
api_key: sk-or-v1-xxx                     # API Key
url: https://openrouter.ai/api/v1/chat/completions
model: google/gemini-4-carbon             # 默认模型名称
provider: google-ai-studio/flex           # 锁定单一上游渠道以保证 KV 缓存命中（非空时固定写入单元素 order 且 allow_fallbacks: false）
tools:                                    # 新建会话默认勾选的工具组（可选 base / run_command / web / image）
  - base
web_provider: tavily                      # 联网工具提供商（目前支持 tavily）
web_api_key: tvly-xxx                     # 联网工具 API Key（启用 web 时需填写）
system_prompt: '你是一位助手...'           # 新建会话的默认 System Prompt
```

`harness/presets.yaml` 支持配置多套预设（`name` 必填，未填写的字段自动继承 `config.yaml` 的默认值，显式留空则置空）：

```yaml
- name: 编程老师
  tools:
    - base
  system_prompt: '你是一位教授基础编程知识的老师...'

- name: 纯文本问答
  tools:
  system_prompt: ''
```

## 主要特性

- **多会话并发与预设管理**：会话任务由后台协程托管，等待模型响应或执行工具期间可自由切换浏览其他会话；支持历史会话复制、重命名与删除，支持多套对话预设（`presets.yaml`）导入及已存会话配置的随时编辑更新。
- **流式输出与富文本渲染**：支持模型思考链（`reasoning`）与正文的 SSE 实时流式输出（可通过 `stream` 配置切换），内置本地 `markdown-it` 与 `MathJax 4`，支持折叠查看思考过程与分类工具调用详情，支持离线渲染 LaTeX 数学公式。
- **多模态图片交互（输入 / 生图 / 看图）**：支持选择本地图片或直接从剪贴板粘贴截图发送（自动压缩编码并落盘至当前会话 `assets/` 目录回显），同时内置生图预览与按需读取图片供模型查看的多模态工具链。
- **双轨状态与完整留痕**：所有会话保存在 `harness/sessions/{时间戳}_{uuid}/` 目录下，分离维护发给模型的 `request_body.json` 与供前端渲染的 `ui_messages.json`，并按序落盘每次原始请求与响应的 `http_logs/` 及异常堆栈 `error.txt`，方便排查接口细节。
- **对话控制（停止 / 继续 / 回溯）**：运行期间支持点击 `⏹` 随时中断，遇到手动停止、达到最大步数（`max_steps`）或请求报错时统一生成提示框支持一键继续/重试；每轮 `user` 消息通过 `request_index` 锚点精确关联双轨历史，支持点击标题栏右侧 `↩` 按钮一键撤销指定轮次及之后的全部对话，并将原文本自动回填至输入框重新编辑发送。
- **工作区与容器沙箱**：文件操作工具严格限制在当前会话的 `workspace_dir` 内，自动拦截越界路径访问并返回相对路径提示；命令行工具运行在按会话隔离的 `python:3.12-slim` Docker 容器中，支持前端手动启停并在服务退出时自动清理。

## 内置工具

右侧边栏支持按会话按需勾选以下工具组：

| 工具组 | 工具名 | 说明 |
| --- | --- | --- |
| `base` | `list_files` | 列出工作区指定目录下的文件树结构（遵循 `.gitignore` 忽略规则） |
| `base` | `read_file` | 读取指定文件的完整文本内容 |
| `base` | `write_file` | 创建新文件或覆盖写入完整文件内容 |
| `base` | `edit_file` | 通过精确匹配 `old_str` 并替换为 `new_str` 对文件做局部修改 |
| `run_command` | `run_command` | 在挂载当前工作区的 `python:3.12-slim` Docker 容器中执行 Shell 命令（首次调用自动启动容器，支持自定义超时时间与后台常驻运行） |
| `web` | `web_search` | 在互联网上搜索关键词，返回相关网页的标题、链接与摘要（JSON 数组格式） |
| `web` | `web_fetch` | 提取指定 URL 网页的正文内容（Markdown 格式） |
| `image` | `generate_image` | 调用生图模型生成图片并落盘至当前会话 `assets/`，在前端直接展开预览 |
| `image` | `view_image` | 按需读取会话 `assets/` 或工作区内的图片，借道 `user` 消息回传给主 Agent 查看 |

> 环境前提：启用 `run_command` 需本机安装并运行 Docker。当前沙箱容器镜像固定写死为 `python:3.12-slim`，首次使用前建议先执行 `docker pull python:3.12-slim` 预拉取镜像，避免首次调用工具时因下载镜像导致超时。

## 源码导读

模块位于 [`src/ms_toolbox/harness/`](../src/ms_toolbox/harness/)，适合阅读理解 Harness 的核心工作流程：

- **`config.py`（配置与预设加载）**
  管理 `harness/` 子目录下的 `config.yaml`、`presets.yaml` 与 `sessions/`，将全局默认配置与自定义预设合并为统一的预设列表供前端导入。
- **`main.py`（单端口 HTTP + WebSocket 服务与指令路由）**
  利用 `websockets` 库的 `process_request` 钩子在同一个端口上同时托管 `site/` 静态前端资源、`sessions/` 会话图片资源与 WebSocket 实时通信（详细消息契约与命名规范见 [WebSocket 通信协议](./harness/websocket.md)）；将前端发来的轻量读写操作路由给 `Session`，将耗时执行任务委托给 `runtime.py` 调度。
- **`runtime.py`（后台任务托管与核心 Agent 循环）**
  集中维护后台运行中的会话任务字典 `running_tasks`（支持随时查询与取消停止），并通过 `run_agent_loop()` 驱动最直观的 ReAct / Tool-Use 循环（默认单次最多连续执行 `max_steps=5` 步，可在 `config.yaml` 中配置，设为 `0` 则无限循环）：
  1. 调用 `fetch_llm()` 请求大模型，并第一时间通过 `session.save_http()` 将原始响应写入 `http_logs/`；
  2. 将模型的 `reasoning`（含 Gemini 渠道所需的 `reasoning_details` 签名回传）与文本内容追加进历史；
  3. 若包含 `tool_calls`，通过 `pending_tool_calls` 队列逐一调用对应 Python 函数并将结果包裹为 JSON 回传给模型，随后进入下一轮循环；若无工具调用则结束本轮回复。
  当遇到请求或解析报错（`reason="error"`）、达到最大循环步数（`reason="max_steps"`）或用户手动停止（`reason="stopped"`）时，统一追加结构化的 `interrupt` 块（可选附带 `detail` 详情），由前端集中渲染提示框与“继续/重试”按钮交还控制权。
- **`llm.py`（大模型 HTTP 通信与 SSE 流式组装）**
  向上游屏蔽流式与非流式接口差异，对外统一提供 `fetch_llm(request_body, on_delta)`。当全局 `stream: true` 开启时，`iter_sse_chunks()` 负责逐行剥离 SSE 协议壳，一边通过 `on_delta` 回调实时向上层转发思考与正文增量，一边由 `StreamAssembler` 将分散的流式帧重新拼回与非流式结构完全一致的 `response_body`。
- **`session.py`（纯同步会话存档管理）**
  不依赖异步事件循环与网络通信，纯粹负责本地 `sessions/{session_id}/` 目录下的数据读写与双轨状态维护（详细目录布局与双轨消息结构见 [会话存档与双轨消息契约](./harness/session.md)）：包括会话创建、读取、复制、重命名与删除（`create` / `load` / `copy` / `rename` / `delete`）、配置同步（`update_config`）、附件落盘（`save_assets`）、原始报文与错误留痕（`save_http` / `save_error`），以及通过 `add_user_message()` 记录 `request_index` 锚点供 `rewind()` 同步截断 `ui_messages` 与 `request_body` 实现对话回溯。
- **`tools/`（自动 Schema 解析与工具实现）**
  （工具签名规范、`ToolResult` 返回值契约与新工具接入清单见 [工具开发与接入契约](./harness/tools.md)）
  - `__init__.py`：`build_tools()` 根据会话勾选的工具组名称按需组装工具 Schema 列表与函数映射表 `tool_map`。
  - `utils.py`：提供统一封装工具返回结果的 `ToolResult`（基础文本、前端 `<details>` 附加数据与借道 `user` 多模态内容），以及使用 `docstring_parser` 解析普通 Python 函数的 Google 风格 Docstring 自动生成 JSON Schema 的 `function_to_tool()`。
  - `base.py`：实现 4 个基础文件操作函数，通过 `resolve_workspace_path` 校验工作区边界并统一使用工作区相对路径反馈结果。
  - `run_command.py`：按会话管理 `msh-{session_id}` Docker 容器的启动、命令执行与销毁。
  - `web.py`：将底层提供商（当前支持 Tavily）封装为统一的 `search` 与 `fetch` 契约，向上暴露 `web_search` 与 `web_fetch` 工具。
  - `image.py`：通过模型挡位映射调用 OpenRouter 生图接口落盘至 `assets/`，并提供支持双路径查找的 `view_image` 看图工具。
- **`site/`（零构建模块化原生前端）**
  无任何打包构建步骤，直接使用现代浏览器原生能力按顶层业务 ID 实现组件化拆分（详细区域隔离与单向数据流规范见 [Web UI 布局与视图模块契约](./harness/webui-layout.md)）：
  - `index.html`：定义左栏（`#left-sidebar`）、消息区（`#message-list`）、输入区（`#chat-box`）、右栏（`#right-sidebar`）四大视图区域骨架。
  - `css/`：拆分为公共布局与通用组件样式 `base.css`，以及与四大区域一一对应的同名样式文件，通过原生 CSS 嵌套将区域样式限定在各自顶层 ID 下，避免样式污染。
  - `js/`：采用原生 ES Modules（`type="module"`），由总控入口 `main.js` 集中维护 WebSocket 连接与核心会话状态，单向调度 `left-sidebar.js`、`message-list.js`、`chat-box.js`、`right-sidebar.js` 四个视图模块完成局部 DOM 渲染与事件响应。

## 架构契约文档

针对跨模块交互的数据格式与扩展规范，`docs/harness/` 目录下提供了四份专项契约文档供迭代开发时查阅：

| 文档 | 核心内容 |
| --- | --- |
| **[WebSocket 通信协议](./harness/websocket.md)** | 前后端收发入口约定、`type` 三类命名语法格式、`session` 与 `chat` 语义边界及全量消息清单 |
| **[会话存档与双轨消息契约](./harness/session.md)** | `sessions/` 目录文件职责、`ui_messages.json`（4 类 Block）与 `request_body.json` 结构契约及 `rewind` 双轨锚点回溯机制 |
| **[工具开发与接入契约](./harness/tools.md)** | Google 风格 Docstring 自动 Schema 解析规则、`ToolResult` 三字段契约、提供商内部接口及新增工具组接入清单 |
| **[Web UI 布局与视图模块契约](./harness/webui-layout.md)** | 四大顶层区域 1:1 文件映射、原生 CSS 嵌套隔离、Coordinator 单向数据流约定及消息流式草稿转正机制 |
