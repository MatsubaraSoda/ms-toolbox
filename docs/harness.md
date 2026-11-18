# Harness (msh)

一个用于学习与实践大模型 Agent 原理的轻量级本地 Web UI Harness Toy。基于 OpenRouter（兼容 OpenAI `chat/completions` 接口）驱动，支持多会话管理、思考过程展示与工作区文件读写工具调用。

## 快速启动

```bash
# 使用 config.yaml 中的默认端口（8000）启动
msh

# 临时指定其他端口启动
msh --port 8080
```

启动后在浏览器访问终端输出的本地地址（默认 `http://localhost:8000`）即可打开交互界面。

## 配置说明

首次运行时，程序会在用户配置目录（Windows 下为 `%LOCALAPPDATA%\ms-toolbox\config.yaml`）自动生成默认配置文件；也可以直接点击网页侧边栏的设置按钮调用系统默认编辑器打开。

`harness` 相关配置项如下：

```yaml
harness:
  port: 8000                               # 默认监听端口（可通过命令行 --port 覆盖）
  workspace_dir: D:/path/to/your/project   # 默认工作区目录（可在新建会话时通过网页修改或弹窗选择）
  api_key: sk-or-v1-xxx                    # OpenRouter API Key
  url: https://openrouter.ai/api/v1/chat/completions
  model: google/gemini-4-carbon             # 默认模型名称
  provider:
    order:
      - google-ai-studio/flex               # 指定优先上游渠道
    allow_fallbacks: false
  system_prompt: "你是一位助手..."          # 新建会话的默认 System Prompt
```

## 主要特性

- **多会话后台并发**：会话任务由后台协程托管，等待模型响应或执行工具期间可自由切换浏览其他历史会话。
- **双轨状态与完整留痕**：所有会话保存在 `config.yaml` 同级的 `sessions/{时间戳}_{uuid}/` 目录下，分别记录发给模型的 `request_body.json`、供前端渲染的 `ui_messages.json`，以及按序落盘每次原始请求与响应的 `http_logs/`，方便排查接口细节。
- **富文本与思考过程渲染**：内置本地 `markdown-it` 与 `MathJax 4`，支持折叠查看模型思考链（`reasoning`）与工具调用入参/返回值，支持离线渲染 LaTeX 数学公式。
- **工作区安全沙箱**：所有文件操作工具均绑定至当前会话的 `workspace_dir`，自动拦截越界路径访问。

## 内置工具

| 工具名 | 说明 |
| --- | --- |
| `list_files` | 列出工作区指定目录下的文件树结构（遵循 `.gitignore` 忽略规则） |
| `read_file` | 读取指定文件的完整文本内容 |
| `write_file` | 创建新文件或覆盖写入完整文件内容 |
| `edit_file` | 通过精确匹配 `old_str` 并替换为 `new_str` 对文件做局部修改 |

## 源码导读

模块位于 [`src/ms_toolbox/harness/`](../src/ms_toolbox/harness/)，适合阅读理解最小化 Agent Harness 的核心运行链路：

- **`main.py`（单端口 HTTP + WebSocket 服务）**
  利用 `websockets` 库的 `process_request` 钩子在同一个端口上同时托管 `site/` 静态前端资源与 WebSocket 实时通信；使用全局集合 `running_sessions` 追踪后台运行中的会话任务，并将状态实时同步给前端。
- **`session.py`（核心 Agent 循环与会话持久化）**
  `Session.run_agent_loop()` 实现了最直观的 ReAct / Tool-Use 循环（默认单次最多连续执行 `max_steps=5` 步，超步后在前端生成“继续”按钮交还控制权）：
  1. 发送 `request_body` 请求大模型并第一时间将原始响应写入 `http_logs/`；
  2. 将模型的 `reasoning`（含 Gemini 渠道所需的 `reasoning_details` 签名回传）与文本内容追加进历史；
  3. 若包含 `tool_calls`，逐一调用对应 Python 函数并将结果包裹为 JSON 回传给模型，随后自动进入下一轮循环；若无工具调用则结束本轮回复。
- **`tools/`（自动 Schema 解析与工具实现）**
  - `utils.py` 中的 `function_to_tool()` 使用 `docstring_parser` 解析普通 Python 函数的 Google 风格 Docstring，自动生成符合 OpenAI 规范的 JSON Schema 工具定义，无需手写冗长的字典配置。
  - `base.py` 实现了 4 个基础文件操作函数；在 `Session.register_tool()` 注册时通过 `ensure_in_workspace_dir` 装饰器统一注入工作区路径校验。
- **`site/`（零构建原生前端）**
  纯原生 `index.html` + `style.css` + `script.js` 实现，无打包构建步骤，通过简单的 JSON 消息协议与后端收发会话状态。
