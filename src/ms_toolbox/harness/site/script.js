const ws = new WebSocket(`ws://${location.host}`);

// 1. 先定位页面三大顶层区域（全页仅有的 3 个 id）
const leftSidebar = document.getElementById('left-sidebar');
const mainContent = document.getElementById('main-content');
const rightSidebar = document.getElementById('right-sidebar');

// 2. 顺着三大区域向内查找常用子元素
const sessionListEl = leftSidebar.querySelector('.session-list');
const messageListEl = mainContent.querySelector('.message-list');
const chatInput = mainContent.querySelector('.chat-input');
const chatSubmit = mainContent.querySelector('.chat-submit');
const configForm = rightSidebar.querySelector('.config-form');
const workspaceInput = configForm.querySelector('[name="workspace_dir"]');
const workspaceError = configForm.querySelector('.field-error');
const pickDirBtn = configForm.querySelector('.pick-dir-btn');

const CONFIG_KEYS = ['workspace_dir', 'model', 'provider', 'system_prompt'];

// 初始化 Markdown 渲染器，并将 $ / $$ 公式原样包裹后交由 MathJax 渲染
const md = window.markdownit().use(window.texmath, { delimiters: 'dollars' });
md.renderer.rules.math_inline = (tokens, idx) =>
  `<span>$${md.utils.escapeHtml(tokens[idx].content)}$</span>`;
md.renderer.rules.math_inline_double = (tokens, idx) =>
  `<p>$$${md.utils.escapeHtml(tokens[idx].content)}$$</p>\n`;
md.renderer.rules.math_block = (tokens, idx) =>
  `<p>$$${md.utils.escapeHtml(tokens[idx].content)}$$</p>\n`;

// 前端核心状态
let currentSessionId = null;
let sessionList = [];
let runningSessions = [];

function fillConfig(cfg) {
  for (const key of CONFIG_KEYS) {
    configForm.querySelector(`[name="${key}"]`).value = cfg[key];
  }
}

function readConfig() {
  const cfg = {};
  for (const key of CONFIG_KEYS) {
    cfg[key] = configForm.querySelector(`[name="${key}"]`).value;
  }
  return cfg;
}

// 将 "20261117_205125_07f55bc3-..." 简化显示为 "11-17 20:51 · 07f55bc3"
function formatSessionId(id) {
  const timePart = `${id.slice(4, 6)}-${id.slice(6, 8)} ${id.slice(9, 11)}:${id.slice(11, 13)}`;
  const shortId = id.slice(16, 24);
  return `${timePart} · ${shortId}`;
}

// 根据当前对话是否在后台运行，锁定或解锁底部输入框
function updateInputState() {
  const isRunning = currentSessionId !== null && runningSessions.includes(currentSessionId);
  chatInput.disabled = isRunning;
  chatSubmit.disabled = isRunning;
  chatInput.placeholder = isRunning ? '⏳ AI 思考中...' : '输入内容...';
}

// 创建 DOM 元素并安全填入纯文本（避免 innerHTML 把文本误渲染成网页标签）
function makeEl(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

// 创建用于展示 Markdown 渲染结果的 DOM 元素
function makeMdEl(content) {
  const el = makeEl('div', 'message-text');
  el.innerHTML = md.render(content);
  return el;
}

function renderSessionList() {
  sessionListEl.innerHTML = '';

  for (const id of sessionList) {
    const item = document.createElement('div');
    item.className = 'session-item' + (id === currentSessionId ? ' active' : '');
    const prefix = runningSessions.includes(id) ? '⏳ ' : '';
    item.textContent = prefix + formatSessionId(id);
    item.onclick = () => {
      ws.send(JSON.stringify({ type: 'load_session', session_id: id }));
    };
    sessionListEl.appendChild(item);
  }
}

function renderMessages(messages) {
  messageListEl.innerHTML = '';

  for (const msg of messages) {
    const div = makeEl('div', 'message');
    div.appendChild(makeEl('div', `message-role role-${msg.role}`, `${msg.role}`));

    if (msg.role !== 'assistant') {
      div.appendChild(makeMdEl(msg.content));
    } else {
      for (const block of msg.blocks) {
        if (block.type === 'thought') {
          const details = makeEl('details');
          details.append(
            makeEl('summary', '', '💭 思考过程'),
            makeMdEl(block.content)
          );
          div.appendChild(details);

        } else if (block.type === 'tool') {
          const details = makeEl('details');
          const toolText = `参数: ${JSON.stringify(block.args)}\n\n结果:\n${block.result}`;
          details.append(
            makeEl('summary', '', `🔧 工具调用: ${block.name}`),
            makeEl('pre', '', toolText)
          );
          div.appendChild(details);

        } else if (block.type === 'text') {
          div.appendChild(makeMdEl(block.content));

        } else if (block.type === 'continue') {
          const btn = makeEl('button', 'continue-btn', '⚠️ 已达最大步数限制，点击继续执行');
          btn.onclick = continueLoop;
          div.appendChild(btn);

        } else if (block.type === 'error') {
          const errBox = makeEl('div', 'error-box');
          const btn = makeEl('button', 'continue-btn', '🔄 点击重试');
          btn.onclick = continueLoop;
          errBox.append(makeEl('div', '', `❌ ${block.content}`), btn);
          div.appendChild(errBox);
        }
      }
    }

    messageListEl.appendChild(div);
  }

  messageListEl.scrollTop = messageListEl.scrollHeight;
  MathJax.startup.promise = MathJax.startup.promise
    .then(() => MathJax.typesetPromise([messageListEl]));
}

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === 'init') {
    currentSessionId = null;
    sessionList = msg.sessions;
    runningSessions = msg.running_sessions;

    workspaceError.textContent = '';
    fillConfig(msg.config);
    configForm.disabled = false;
    messageListEl.innerHTML = '';

    renderSessionList();
    updateInputState();

  } else if (msg.type === 'session_loaded') {
    if (currentSessionId === null) {
      chatInput.value = '';
      chatInput.style.height = 'auto';
    }
    currentSessionId = msg.session_id;
    sessionList = msg.sessions;

    workspaceError.textContent = '';
    fillConfig(msg.ui_messages.config);
    configForm.disabled = true;
    renderMessages(msg.ui_messages.messages);

    renderSessionList();
    updateInputState();

  } else if (msg.type === 'messages') {
    sessionList = msg.sessions;
    renderSessionList();

    // 防串台：只有当收到的是“当前正在看的对话”时，才刷新中间消息区
    if (msg.session_id === currentSessionId) {
      renderMessages(msg.data);
    }

  } else if (msg.type === 'running_state') {
    runningSessions = msg.running_sessions;
    renderSessionList();
    updateInputState();

  } else if (msg.type === 'dir_picked') {
    workspaceInput.value = msg.path;
    workspaceError.textContent = '';

  } else if (msg.type === 'workspace_error') {
    workspaceError.textContent = msg.message;
  }
};

// 左右侧边栏折叠与展开
const leftToggleBtn = leftSidebar.querySelector('.toggle-btn');
leftToggleBtn.addEventListener('click', () => {
  const isCollapsed = leftSidebar.classList.toggle('collapsed');
  leftToggleBtn.textContent = isCollapsed ? '»' : '«';
});

const rightToggleBtn = rightSidebar.querySelector('.toggle-btn');
rightToggleBtn.addEventListener('click', () => {
  const isCollapsed = rightSidebar.classList.toggle('collapsed');
  rightToggleBtn.textContent = isCollapsed ? '«' : '»';
});

// 左边栏“新建对话”与“设置”按钮
leftSidebar.querySelector('.new-btn').addEventListener('click', () => {
  ws.send(JSON.stringify({ type: 'new_session' }));
});

leftSidebar.querySelector('.settings-btn').addEventListener('click', () => {
  ws.send(JSON.stringify({ type: 'open_settings' }));
});

// 右边栏“选择文件夹”按钮与清空错误提示
pickDirBtn.addEventListener('click', () => {
  ws.send(JSON.stringify({ type: 'pick_dir' }));
});

workspaceInput.addEventListener('input', () => {
  workspaceError.textContent = '';
});

// 输入框高度自适应与回车发送
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = chatInput.scrollHeight + 'px';
});

chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

function continueLoop() {
  ws.send(JSON.stringify({ type: 'continue', session_id: currentSessionId }));
}

function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;

  const payload = {
    type: 'chat',
    session_id: currentSessionId,
    content: text,
  };

  // 新建对话的第一条消息：附带右侧表单配置
  if (currentSessionId === null) {
    payload.config = readConfig();
  }

  ws.send(JSON.stringify(payload));

  // 已有对话直接清空；新建对话等后端校验目录通过（收到 session_loaded）后再清空
  if (currentSessionId !== null) {
    chatInput.value = '';
    chatInput.style.height = 'auto';
  }
}

chatSubmit.addEventListener('click', sendMessage);
