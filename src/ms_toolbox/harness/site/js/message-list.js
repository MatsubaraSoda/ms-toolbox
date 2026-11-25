const messageList = document.getElementById('message-list');

// 初始化 Markdown 渲染器，并将 $ / $$ 公式原样包裹后交由 MathJax 渲染
const md = window.markdownit().use(window.texmath, { delimiters: 'dollars' });
md.renderer.rules.math_inline = (tokens, idx) =>
  `<span>$${md.utils.escapeHtml(tokens[idx].content)}$</span>`;
md.renderer.rules.math_inline_double = (tokens, idx) =>
  `<p>$$${md.utils.escapeHtml(tokens[idx].content)}$$</p>\n`;
md.renderer.rules.math_block = (tokens, idx) =>
  `<p>$$${md.utils.escapeHtml(tokens[idx].content)}$$</p>\n`;

let isSessionRunning = false;
let handleContinue = null;
let handleRewind = null;

// 流式草稿原始文本缓存（key: 草稿 DOM 元素, value: 已拼接的 Markdown 文本）与 MathJax 忙时合并锁
const streamingTexts = new Map();
let typesetting = false;
let nextTarget = null;

function typesetMath(el) {
  if (typesetting) {
    nextTarget = el;
    return;
  }
  typesetting = true;
  MathJax.startup.promise
    .then(() => MathJax.typesetPromise([el]))
    .finally(() => {
      typesetting = false;
      if (nextTarget) {
        const target = nextTarget;
        nextTarget = null;
        typesetMath(target);
      }
    });
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

// 创建 assistant 消息内部的单个内容块（thought / tool / text / interrupt）
function createBlockEl(block, sessionId) {
  if (block.type === 'thought') {
    const details = makeEl('details');
    details.append(
      makeEl('summary', '', '💭 思考过程'),
      makeMdEl(block.content)
    );
    return details;
  }

  if (block.type === 'tool') {
    const toolIcons = {
      web_search: '🌐',
      web_fetch: '🌐',
      run_command: '💻',
      generate_image: '🖼️',
      view_image: '🖼️',
    };
    const icon = toolIcons[block.name] || '🔧';
    const result = (block.name === 'web_search' && block.result.startsWith('['))
      ? JSON.stringify(JSON.parse(block.result), null, 2)
      : block.result;

    const details = makeEl('details');
    const toolText = `参数: ${JSON.stringify(block.args)}\n\n结果:\n${result}`;
    details.append(
      makeEl('summary', '', `${icon} 工具调用: ${block.name}`),
      makeEl('pre', '', toolText)
    );

    if (block.generate_image && block.generate_image.length > 0) {
      details.open = true;
      const gallery = makeEl('div', 'tool-images');
      for (const name of block.generate_image) {
        const url = `/sessions/${sessionId}/assets/${name}`;
        const link = makeEl('a');
        link.href = url;
        link.target = '_blank';

        const img = makeEl('img');
        img.src = url;
        link.appendChild(img);
        gallery.appendChild(link);
      }
      details.appendChild(gallery);
    }

    return details;
  }

  if (block.type === 'text') {
    return makeMdEl(block.content);
  }

  if (block.type === 'interrupt') {
    const configs = {
      max_steps: { title: '⚠️ 已达最大步数限制', btn: '▶ 继续执行', isError: false },
      stopped:   { title: '⏹ 已手动停止',       btn: '▶ 继续执行', isError: false },
      error:     { title: '❌ 请求中断',         btn: '🔄 点击重试', isError: true },
    };
    const cfg = configs[block.reason];

    const box = makeEl('div', cfg.isError ? 'interrupt-box is-error' : 'interrupt-box');
    box.appendChild(makeEl('div', 'interrupt-title', cfg.title));

    if (block.detail) {
      box.appendChild(makeEl('div', 'interrupt-detail', block.detail));
    }

    const btn = makeEl('button', 'continue-btn', cfg.btn);
    btn.disabled = isSessionRunning;
    btn.onclick = handleContinue;
    box.appendChild(btn);

    return box;
  }
}

// 创建单条消息元素（system / user / assistant）
function createMessageEl(msg, index, sessionId) {
  const div = makeEl('div', 'message');
  const roleEl = makeEl('div', `message-role role-${msg.role}`, `${msg.role}`);

  if (msg.role === 'user' && 'request_index' in msg) {
    const rewindBtn = makeEl('button', 'rewind-btn', '↩');
    rewindBtn.type = 'button';
    rewindBtn.title = '撤销此条及之后的对话';
    rewindBtn.disabled = isSessionRunning;
    rewindBtn.onclick = () => {
      if (confirm('确定撤销此条及之后的所有对话吗？')) {
        handleRewind(index);
      }
    };
    roleEl.appendChild(rewindBtn);
  }

  div.appendChild(roleEl);

  if (msg.assets && msg.assets.length > 0) {
    const assetsEl = makeEl('div', 'message-assets');
    for (const asset of msg.assets) {
      const url = `/sessions/${sessionId}/assets/${asset.saved_name}`;
      const link = makeEl('a', 'asset-item');
      link.href = url;
      link.target = '_blank';
      link.title = asset.orig_name;

      const img = makeEl('img');
      img.src = url;
      link.appendChild(img);
      assetsEl.appendChild(link);
    }
    div.appendChild(assetsEl);
  }

  if (msg.role !== 'assistant') {
    if (msg.content) {
      div.appendChild(makeMdEl(msg.content));
    }
  } else {
    const blocksEl = makeEl('div', 'message-blocks');
    for (const block of msg.blocks) {
      blocksEl.appendChild(createBlockEl(block, sessionId));
    }
    div.appendChild(blocksEl);
  }

  return div;
}

export function initMessageList({ onContinue, onRewind }) {
  handleContinue = onContinue;
  handleRewind = onRewind;
}

// 全量重置渲染：仅用于加载/切换对话时，初始化列表并定位到底部
export function renderMessages(messages, sessionId) {
  clearMessages();
  messages.forEach((msg, index) => {
    messageList.appendChild(createMessageEl(msg, index, sessionId));
  });
  messageList.scrollTop = messageList.scrollHeight;
  typesetMath(messageList);
}

// 增量同步渲染：用于同一对话内的增删更新，不触碰已有消息 DOM 与滚动位置
export function updateMessages(messages, sessionId) {
  while (messageList.children.length > messages.length) {
    const lastEl = messageList.lastElementChild;
    MathJax.typesetClear?.([lastEl]);
    lastEl.remove();
  }

  const prevCount = messageList.children.length;
  for (let i = prevCount; i < messages.length; i++) {
    const msgEl = createMessageEl(messages[i], i, sessionId);
    messageList.appendChild(msgEl);
    if (messages[i].content) {
      typesetMath(msgEl);
    }
  }

  const lastMsg = messages[messages.length - 1];
  if (!lastMsg || lastMsg.role !== 'assistant') return;

  const assistantEl = messageList.lastElementChild;
  const blocksEl = assistantEl.querySelector('.message-blocks');

  // 若点击了“继续执行”，后端已移除旧的 interrupt 块，同步移除末尾提示框
  if (
    blocksEl.lastElementChild?.classList.contains('interrupt-box') &&
    lastMsg.blocks[lastMsg.blocks.length - 1]?.type !== 'interrupt'
  ) {
    blocksEl.lastElementChild.remove();
  }

  const drafts = [...blocksEl.querySelectorAll('.is-streaming')];
  const prevBlockCount = blocksEl.children.length - drafts.length;
  let needsTypeset = false;

  for (let i = prevBlockCount; i < lastMsg.blocks.length; i++) {
    const block = lastMsg.blocks[i];
    const draftEl = drafts[0];

    if (draftEl && draftEl.dataset.type === block.type) {
      drafts.shift();
      draftEl.classList.remove('is-streaming');
      delete draftEl.dataset.type;

      if (streamingTexts.get(draftEl) !== block.content) {
        const target = block.type === 'thought' ? draftEl.querySelector('.message-text') : draftEl;
        MathJax.typesetClear?.([target]);
        target.innerHTML = md.render(block.content);
        needsTypeset = true;
      }
    } else {
      const blockEl = createBlockEl(block, sessionId);
      blocksEl.insertBefore(blockEl, draftEl || null);
      needsTypeset = true;
    }
  }

  for (const draftEl of drafts) {
    MathJax.typesetClear?.([draftEl]);
    draftEl.remove();
  }
  streamingTexts.clear();

  if (needsTypeset) {
    typesetMath(blocksEl);
  }
}

// 仅原地更新第 0 条 system 消息（右侧保存配置时调用，不影响下方消息与折叠状态）
export function updateSystemMessage(systemMsg, sessionId) {
  const firstEl = messageList.firstElementChild;
  if (!firstEl) return;
  MathJax.typesetClear?.([firstEl]);
  const newEl = createMessageEl(systemMsg, 0, sessionId);
  firstEl.replaceWith(newEl);
  typesetMath(newEl);
}

export function appendStreamDelta(blockType, delta) {
  const blocksEl = messageList.lastElementChild?.querySelector('.message-blocks');
  if (!blocksEl) return;

  let draftEl = blocksEl.lastElementChild;
  if (!draftEl?.classList.contains('is-streaming') || draftEl.dataset.type !== blockType) {
    draftEl = createBlockEl({ type: blockType, content: '' });
    draftEl.classList.add('is-streaming');
    draftEl.dataset.type = blockType;
    streamingTexts.set(draftEl, '');
    blocksEl.appendChild(draftEl);
  }

  const rawText = streamingTexts.get(draftEl) + delta;
  streamingTexts.set(draftEl, rawText);

  const target = blockType === 'thought' ? draftEl.querySelector('.message-text') : draftEl;
  MathJax.typesetClear?.([target]);
  target.innerHTML = md.render(rawText);
  typesetMath(target);
}

export function clearMessages() {
  MathJax.typesetClear?.([messageList]);
  messageList.innerHTML = '';
  streamingTexts.clear();
  nextTarget = null;
}

export function setMessagesRunning(isRunning) {
  isSessionRunning = isRunning;
  for (const btn of messageList.querySelectorAll('.rewind-btn, .continue-btn')) {
    btn.disabled = isRunning;
  }
}
