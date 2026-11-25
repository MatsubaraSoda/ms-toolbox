const leftSidebar = document.getElementById('left-sidebar');
const toggleBtn = leftSidebar.querySelector('.toggle-btn');
const newBtn = leftSidebar.querySelector('.new-btn');
const settingsBtn = leftSidebar.querySelector('.settings-btn');
const sessionListEl = leftSidebar.querySelector('.session-list');

let handleSelectSession = null;
let handleCopySession = null;
let handleRenameSession = null;
let handleDeleteSession = null;

function closeAllMenus(exceptMenu = null) {
  for (const d of sessionListEl.querySelectorAll('details[open]')) {
    if (d !== exceptMenu) {
      d.open = false;
    }
  }
}

export function initLeftSidebar({
  onNewSession,
  onSelectSession,
  onCopySession,
  onRenameSession,
  onDeleteSession,
  onOpenSettings,
}) {
  handleSelectSession = onSelectSession;
  handleCopySession = onCopySession;
  handleRenameSession = onRenameSession;
  handleDeleteSession = onDeleteSession;

  toggleBtn.addEventListener('click', () => {
    const isCollapsed = leftSidebar.classList.toggle('collapsed');
    toggleBtn.textContent = isCollapsed ? '»' : '«';
  });

  newBtn.addEventListener('click', onNewSession);
  settingsBtn.addEventListener('click', onOpenSettings);

  document.addEventListener('click', () => closeAllMenus());
}

export function renderSessionList(sessionList, currentSessionId, runningSessions) {
  sessionListEl.innerHTML = '';

  for (const session of sessionList) {
    const { id, title } = session;
    const isRunning = runningSessions.includes(id);

    const item = document.createElement('div');
    item.className = 'session-item' + (id === currentSessionId ? ' active' : '');
    item.onclick = () => handleSelectSession(id);

    const titleEl = document.createElement('span');
    titleEl.className = 'session-title';
    titleEl.textContent = (isRunning ? '⏳ ' : '') + title;
    titleEl.title = title;

    const menu = document.createElement('details');
    menu.className = 'session-menu';
    menu.onclick = (e) => e.stopPropagation();
    menu.ontoggle = () => {
      if (menu.open) {
        closeAllMenus(menu);
      }
    };

    const summary = document.createElement('summary');
    summary.className = 'icon-btn session-menu-btn';
    summary.textContent = '⋯';
    summary.title = '更多操作';

    const popup = document.createElement('div');
    popup.className = 'session-menu-popup';

    const copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.textContent = '复制';
    copyBtn.onclick = () => {
      menu.open = false;
      handleCopySession(id);
    };

    const renameBtn = document.createElement('button');
    renameBtn.type = 'button';
    renameBtn.textContent = '重命名';
    renameBtn.disabled = isRunning;
    renameBtn.onclick = () => {
      menu.open = false;
      const newTitle = prompt('重命名对话', title);
      if (newTitle !== null && newTitle.trim()) {
        handleRenameSession(id, newTitle.trim());
      }
    };

    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.textContent = '删除';
    deleteBtn.disabled = isRunning;
    deleteBtn.onclick = () => {
      menu.open = false;
      if (confirm(`确定删除对话「${title}」吗？`)) {
        handleDeleteSession(id);
      }
    };

    popup.append(copyBtn, renameBtn, deleteBtn);
    menu.append(summary, popup);
    item.append(titleEl, menu);
    sessionListEl.appendChild(item);
  }
}
