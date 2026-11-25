# Harness 工具开发与接入契约

本文档记录 Harness 工具函数的签名与 Docstring 解析规则、返回值封装契约（`str` 与 `ToolResult`）、安全与外部服务适配约定，以及新增工具组时的完整修改清单，供后续扩展新工具或接入新服务商时参考。

---

## 1. 函数定义与 Schema 自动解析约定

Harness 不要求工具继承特定基类。所有工具均为普通的同步 Python 函数（在 `runtime.py` 中统一通过 `asyncio.to_thread()` 放入工作线程调用，避免阻塞主事件循环）。

### 1.1 上下文闭包注入

大模型无需感知的会话级上下文（如 `session_id`、`workspace_dir`），统一通过外层工厂函数（如 `create_base_tools(workspace_dir)`）以闭包形式绑定，**不出现在工具函数的形参列表中**，确保最终暴露给模型的参数列表最小化。

### 1.2 Google 风格 Docstring 契约

`tools/utils.py` 中的 `function_to_tool(func)` 使用 `docstring_parser` 直接解析函数的 `__doc__` 生成 OpenAI Function Calling JSON Schema。编写工具函数时需严格遵循以下格式：

```python
def run_command(command: str, timeout: int = 30, background: bool = False) -> str:
    """在当前工作区对应的 Linux (python:3.12-slim) 容器中执行 Shell 命令。

    Args:
        command (str): 要执行的 Shell 命令（例如 "ls -la" 或 "python3 main.py"）。
        timeout (int, optional): 超时时间（秒），默认为 30。
        background (bool, optional): 是否在后台常驻运行，默认为 False。
    """
```

解析映射规则如下：

| Python / Docstring 元素 | 生成的 Schema 字段 | 约束说明 |
| --- | --- | --- |
| `func.__name__` | `function.name` | 工具唯一标识，同时作为 `session.tool_map` 的路由键 |
| Docstring 首段简述 | `function.description` | 告知模型该工具的用途与适用时机 |
| `Args:` 中的参数名与描述 | `parameters.properties[name]` | 每个形参均需在 `Args:` 中声明括号类型与说明 |
| 括号内的类型名 | `properties[name].type` | 仅支持 6 种基础类型名：`str` ➔ `string`、`int` ➔ `integer`、`float` ➔ `number`、`bool` ➔ `boolean`、`list` ➔ `array`、`dict` ➔ `object` |
| 类型后是否带 `, optional` | `parameters.required` | 未标注 `optional` 的参数自动列入 `required` 必填数组 |

---

## 2. 返回值与错误处理契约

工具函数支持返回普通字符串 `str` 或结构化的 `ToolResult` 实例（定义于 `tools/utils.py`）。

### 2.1 错误反馈原则：返回提示字符串 vs 抛出异常

- **预期内的业务错误（直接返回 `str`）**：如路径越界、文件不存在、`edit_file` 的 `old_str` 未找到或出现多次、命令执行超时、外部 API 返回错误码等，应直接返回清晰的中文错误说明字符串，引导大模型自行修正参数重试。
- **非预期的代码异常（`runtime.py` 兜底捕获）**：若工具函数内部抛出未捕获异常，`runtime.py` 会捕获完整 Traceback 回传给模型，并附带明确指令：若属传参问题则修正重试，若属工具自身 Python 代码 Bug 则立即停止并向用户汇报。

### 2.2 `ToolResult` 三字段契约

当工具除基础文本外还需要触发**前端富媒体渲染**或**向大模型回传图片**时，返回 `ToolResult(result, details_extra, pending_user_content)`：

| 字段 | 类型 | 作用范围 | 契约说明 |
| --- | --- | --- | --- |
| `result` | `str` | 模型轨 + 前端轨 | 基础文本结果：在 `request_body` 中包裹为 `{"result": ...}` 发给模型，在 `ui_messages` 中写入 `tool` 块的 `result` 字段展示于 `<pre>` 内 |
| `details_extra` | `Any`（默认 `None`） | 仅前端轨 | 非 `None` 时，`runtime.py` 会以**工具函数同名键** `tool_block[func_name] = details_extra` 挂载到 UI 的 `tool` 块上，供 `message-list.js` 识别并追加定制 DOM（例如 `generate_image` 挂载文件名数组以展开渲染图片画廊） |
| `pending_user_content` | `list[dict]`（默认 `[]`） | 仅模型轨 | 存放 `chat/completions` 格式的多模态内容块（如 `image_url`）。待当前轮次所有 `tool_calls` 闭合后，由 `runtime.py` 统一借道追加一条 `role: "user"` 消息传给模型查看（例如 `view_image`） |

---

## 3. 安全边界与底层服务适配约定

### 3.1 工作区路径限制

所有读写本地工作区文件的工具，必须先经过路径边界校验：

- `base.py` 使用 `resolve_workspace_path(workspace_dir, path)` 将目标路径 `resolve()` 后校验 `target.is_relative_to(base_dir)`；越界访问直接拦截拒绝，成功解析后统一使用 POSIX 风格的**工作区相对路径**拼装返回提示，不泄露宿主机绝对路径前缀。
- `image.py` 的 `view_image` 使用 `resolve_image_path()` 依次在当前会话的 `assets/`（仅限单层文件名）与 `workspace_dir/`（校验工作区边界）中安全查找目标图片。

### 3.2 外部提供商（Provider）内部契约

涉及第三方网络服务的工具模块，将具体厂商的 HTTP 请求细节隔离在底层适配函数中，向上层工具函数提供固定格式的数据结构，便于后续扩展新厂商：

| 模块 | 内部适配函数 | 统一返回格式契约 |
| --- | --- | --- |
| `tools/web.py` | `search(provider, api_key, query)` | `[{"title": str, "url": str, "snippet": str}, ...]` |
| `tools/web.py` | `fetch(provider, api_key, url)` | Markdown 格式的网页正文 `str`（失败时返回 `"错误：..."`） |
| `tools/image.py` | `generate(api_key, model, prompt, aspect_ratio, n)` | `[{"bytes": bytes, "media_type": str}, ...]`（失败时返回 `"错误：..."`） |

---

## 4. 新增工具组接入清单（Checklist）

在 Harness 中新增一组工具（设为 `<group>`）时，按序对齐以下位置即可完成端到端接入：

1. **实现工具模块（`src/ms_toolbox/harness/tools/<group>.py`）**：编写带规范 Google Docstring 的工具函数，并提供返回函数列表（或单个函数）的 `create_<group>_tools(...)` 工厂函数。
2. **注册工具组装（`src/ms_toolbox/harness/tools/__init__.py`）**：在 `build_tools()` 中新增 `elif name == "<group>":` 分支，将工具函数加入 `funcs` 列表。
3. **添加前端勾选项（`src/ms_toolbox/harness/site/index.html`）**：在 `#right-sidebar` 的 `tools` 字段区域新增 `<input type="checkbox" name="tools" value="<group>">`（如需默认启用，同步更新 `config.py` 的 `DEFAULT_HARNESS_CONFIG_YAML`）。
4. **（可选）前端图标与定制预览（`src/ms_toolbox/harness/site/js/message-list.js`）**：在 `createBlockEl()` 的 `toolIcons` 字典中配置专属图标（未配置默认显示 `🔧`）；若使用了 `ToolResult.details_extra`，在同一分支内读取 `block.<func_name>` 渲染附加视图。
