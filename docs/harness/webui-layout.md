# Harness Web UI 布局与视图模块契约

本文档记录 Harness 前端（`src/ms_toolbox/harness/site/`）在零打包构建（Zero-Build）前提下的四大区域划分、CSS 原生嵌套隔离规范、JS 单向数据流调度模式，以及消息区增量渲染与流式草稿转正机制，供后续迭代界面交互时保持代码边界清晰。

---

## 1. 四大视图区域与文件映射

前端不引入任何打包器或第三方 UI 框架，直接按页面顶层业务区域将 HTML 顶层 ID、CSS 样式文件与 ES Module 脚本（`type="module"`）做 **1:1 同名拆分**：

| 区域职责 | `index.html` 顶层选择器 | 样式文件（`site/css/`） | 视图模块（`site/js/`） |
| --- | --- | --- | --- |
| **全局骨架与总控入口** | `body` / `.main-content` | `base.css` | `main.js` |
| **左边栏：对话管理** | `#left-sidebar` | `left-sidebar.css` | `left-sidebar.js` |
| **中间上部：消息展示流** | `#message-list` | `message-list.css` | `message-list.js` |
| **中间下部：输入与附件栏** | `#chat-box` | `chat-box.css` | `chat-box.js` |
| **右边栏：当前对话设置** | `#right-sidebar` | `right-sidebar.css` | `right-sidebar.js` |

> 注：第三方离线渲染库（`markdown-it`、`texmath`、`mathjax4`）独立存放于 `site/assets/` 下，由 `index.html` 通过 `<script defer>` 全局加载。

---

## 2. CSS 样式分层与作用域隔离约定

### 2.1 `base.css`：页面骨架与跨区原子组件

仅存放跨区域复用的全局规则，不掺杂具体区域的内部业务样式：

- **视口三栏骨架**：`body`（`100vh` 横向 Flex 布局）、左右侧边栏共用结构（`.sidebar`、`.sidebar-header`、`.sidebar-body` 及其折叠态 `.sidebar.collapsed`）、中间主区域骨架（`.main-content`）。
- **通用原子组件**：全页面统一尺寸的正方形图标按钮 `.icon-btn`（`24×24px`）、图片缩略图容器 `.asset-item`（`64×64px`，复用于 `#chat-box` 待发送预览与 `#message-list` 历史附件展示），以及 `[hidden]` 强制隐藏规则。

### 2.2 区域 CSS：原生嵌套隔离

四个区域样式文件（`left-sidebar.css`、`message-list.css`、`chat-box.css`、`right-sidebar.css`）的所有规则均包裹在各自唯一的顶层 ID 选择器内部，利用现代浏览器原生 CSS Nesting 限定作用域：

```css
#left-sidebar {
  .sidebar-header { ... }
  .session-list { ... }
}
```

借由此约定，各区域内部可使用简短直观的类名（如 `.field`、`.toggle-btn`），不会发生跨区域样式污染。

---

## 3. JS 单向数据流与总控模式（Coordinator）

前端脚本严格划分为 **1 个总控协调者（`main.js`）** 与 **4 个纯视图模块**：

### 3.1 模块边界禁令

- **唯一通信与状态源**：只有 `main.js` 持有 WebSocket 实例（`ws`）以及跨区域共享的核心会话状态（`currentSessionId`、`sessionList`、`runningSessions`、`activeContainers`）。
- **视图模块解耦**：4 个视图模块仅通过 `document.getElementById('<区域ID>')` 查找并操作自身容器内的 DOM，**严禁直接调用 WebSocket，也严禁视图模块之间相互 `import`**。

### 3.2 「事件向上，数据向下」交互契约

| 方向 | 调用方式 | 具体规范 |
| --- | --- | --- |
| **事件向上（View ➔ Main）** | `initXxx({ onAction... })` | 每个视图模块对外暴露唯一的初始化函数（如 `initChatBox({ onSend, onStop })`），在 `main.js` 启动时注入回调函数，将用户交互意图向上汇报给总控 |
| **数据向下（Main ➔ View）** | `renderXxx` / `updateXxx` / `setXxx` | `main.js` 收到后端 WebSocket 消息后更新核心状态，经防串台校验（`msg.session_id === currentSessionId`）后单向调用各视图模块暴露的渲染与状态切换函数 |

运行态与容器态由 `main.js` 中的 `syncRunningState()` 和 `syncContainerState()` 集中派生计算为布尔值，统一分发给各子视图控制按钮禁用（`disabled`）与显隐（`hidden`）。

---

## 4. `#message-list` 增量渲染与流式转正机制

为兼顾流式输出的实时性、用户自由滚动阅读体验与公式排版性能，`message-list.js` 遵循以下三条 DOM 更新契约：

1. **全量重绘与增量同步分离**：
   - **`renderMessages()`（全量重置）**：仅在新建、加载或切换会话（收到 `session_loaded`）时调用，清空列表重新构建全部 DOM 并自动定位到底部。
   - **`updateMessages()`（增量同步）**：在同一会话运行期间收到 `messages` 快照或执行 `rewind` 回溯时调用，仅移除多余尾部节点、追加新增节点与新增 `block`，**绝不重建已有消息 DOM**。配合 CSS `#message-list { overflow-anchor: none; }`，保证已展开的 `<details>` 折叠框与用户当前的滚动条位置不被打断。
2. **流式草稿（`.is-streaming`）原地转正**：
   - 收到 `stream_delta` 期间，`appendStreamDelta(blockType, delta)` 在末尾 `assistant` 的 `.message-blocks` 内创建带 `.is-streaming` 类与 `data-type` 属性的草稿节点，并在 `streamingTexts` Map 中累加原始 Markdown 文本实时渲染。
   - 当本轮生成结束、收到后端落盘后的 `messages` 完整快照时，`updateMessages()` 按序匹配草稿节点，直接剥离 `.is-streaming` 标记将其**原地转正**为正式节点（仅当缓存文本与最终文本不一致时才重绘 HTML），避免销毁重建导致的画面闪烁。
3. **MathJax 异步排版清理与合并**：
   - 每次覆盖节点 `innerHTML` 或移除节点前，先调用 `MathJax.typesetClear([el])` 清理旧公式缓存。
   - `typesetMath(el)` 通过 `typesetting` 锁与 `nextTarget` 单槽位缓存实现忙时合并：若上一轮 MathJax 异步排版尚未完成，高频到达的新流式帧只更新最新的待排版目标，待空闲后合并触发一次排版，避免 Promise 队列堆积阻塞主线程。
