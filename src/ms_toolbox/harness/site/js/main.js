import {
  initChatBox,
  resetInput,
  setChatRunning,
  setInputText,
} from './chat-box.js';
import { initLeftSidebar, renderSessionList } from './left-sidebar.js';
import {
  appendStreamDelta,
  clearMessages,
  initMessageList,
  renderMessages,
  setMessagesRunning,
  updateMessages,
  updateSystemMessage,
} from './message-list.js';
import {
  initRightSidebar,
  readConfig,
  renderPresets,
  setConfigRunning,
  setContainerState,
  setupNewConfig,
  setupSavedConfig,
  setWorkspaceDir,
  setWorkspaceError,
} from './right-sidebar.js';

let ws = null;
let resetOnInit = true;

// 前端核心会话状态
let currentSessionId = null;
let sessionList = [];
let runningSessions = [];
let activeContainers = [];

function syncRunningState() {
  const isRunning = currentSessionId !== null && runningSessions.includes(currentSessionId);
  setMessagesRunning(isRunning);
  setChatRunning(isRunning);
  setConfigRunning(isRunning);
}

function syncContainerState() {
  const hasSession = currentSessionId !== null;
  const isActive = hasSession && activeContainers.includes(currentSessionId);
  setContainerState(hasSession, isActive);
}

function sendToBackend(data) {
  ws.send(JSON.stringify(data));
}

// 1. 初始化四大视图区域并绑定事件回调
initLeftSidebar({
  onNewSession: () => {
    resetOnInit = true;
    sendToBackend({ type: 'init_session' });
  },
  onSelectSession: (id) => sendToBackend({ type: 'load_session', session_id: id }),
  onCopySession: (id) => sendToBackend({ type: 'copy_session', session_id: id }),
  onRenameSession: (id, title) => sendToBackend({
    type: 'rename_session',
    session_id: id,
    title,
  }),
  onDeleteSession: (id) => sendToBackend({ type: 'delete_session', session_id: id }),
  onOpenSettings: () => sendToBackend({ type: 'open_settings' }),
});

initMessageList({
  onContinue: () => {
    sendToBackend({ type: 'continue_chat', session_id: currentSessionId });
  },
  onRewind: (uiIndex) => {
    sendToBackend({
      type: 'rewind_session',
      session_id: currentSessionId,
      ui_index: uiIndex,
    });
  },
});

initChatBox({
  onStop: () => {
    if (currentSessionId !== null) {
      sendToBackend({ type: 'stop_chat', session_id: currentSessionId });
    }
  },
  onSend: (text, files) => {
    const payload = {
      type: 'submit_chat',
      session_id: currentSessionId,
      content: text,
      files,
    };

    // 新建对话的第一条消息：附带右侧表单配置
    if (currentSessionId === null) {
      payload.config = readConfig();
    }

    sendToBackend(payload);

    // 已有对话直接清空；新建对话等后端校验目录通过（收到 session_loaded）后再清空
    if (currentSessionId !== null) {
      resetInput();
    }
  },
});

initRightSidebar({
  onOpenPresets: () => sendToBackend({ type: 'open_presets' }),
  onPickDir: () => sendToBackend({ type: 'pick_dir' }),
  onSaveConfig: (config) => sendToBackend({
    type: 'update_config',
    session_id: currentSessionId,
    config,
  }),
  onStartContainer: () => sendToBackend({ type: 'start_container', session_id: currentSessionId }),
  onStopContainer: () => sendToBackend({ type: 'stop_container', session_id: currentSessionId }),
});

// 从外部编辑器修改 presets.yaml 切回浏览器窗口时，自动同步预设下拉框选项
window.addEventListener('focus', () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    sendToBackend({ type: 'reload_presets' });
  }
});

// 2. 统一接收后端消息并分发给对应区域更新视图
function receiveFromBackend(event) {
  const msg = JSON.parse(event.data);

  if (msg.type === 'init_state') {
    sessionList = msg.sessions;
    runningSessions = msg.running_sessions;
    activeContainers = msg.active_containers;
    renderPresets(msg.presets);

    if (resetOnInit) {
      resetOnInit = false;
      currentSessionId = null;
      setupNewConfig();
      clearMessages();
      resetInput();
    } else if (currentSessionId !== null) {
      sendToBackend({ type: 'load_session', session_id: currentSessionId });
    }

    renderSessionList(sessionList, currentSessionId, runningSessions);
    syncRunningState();
    syncContainerState();

  } else if (msg.type === 'presets_updated') {
    renderPresets(msg.presets);

  } else if (msg.type === 'session_loaded') {
    if (currentSessionId === null || currentSessionId !== msg.session_id) {
      resetInput();
    }
    currentSessionId = msg.session_id;
    sessionList = msg.sessions;

    setupSavedConfig(msg.ui_messages.config);
    renderMessages(msg.ui_messages.messages, currentSessionId);

    renderSessionList(sessionList, currentSessionId, runningSessions);
    syncRunningState();
    syncContainerState();

  } else if (msg.type === 'session_copied' || msg.type === 'session_renamed') {
    sessionList = msg.sessions;
    renderSessionList(sessionList, currentSessionId, runningSessions);

  } else if (msg.type === 'session_deleted') {
    sessionList = msg.sessions;

    if (msg.session_id === currentSessionId) {
      currentSessionId = null;
      setupNewConfig();
      clearMessages();
      resetInput();
      syncRunningState();
      syncContainerState();
    }

    renderSessionList(sessionList, currentSessionId, runningSessions);

  } else if (msg.type === 'session_rewound') {
    sessionList = msg.sessions;
    renderSessionList(sessionList, currentSessionId, runningSessions);

    if (msg.session_id === currentSessionId) {
      updateMessages(msg.messages, currentSessionId);
      setInputText(msg.content);
    }

  } else if (msg.type === 'config_updated') {
    if (msg.session_id === currentSessionId) {
      setupSavedConfig(msg.ui_messages.config);
      updateSystemMessage(msg.ui_messages.messages[0], currentSessionId);
    }

  } else if (msg.type === 'messages') {
    sessionList = msg.sessions;
    activeContainers = msg.active_containers;
    renderSessionList(sessionList, currentSessionId, runningSessions);
    syncContainerState();

    // 防串台：只有当收到的是“当前正在看的对话”时，才增量同步中间消息区
    if (msg.session_id === currentSessionId) {
      updateMessages(msg.data, currentSessionId);
    }

  } else if (msg.type === 'stream_delta') {
    if (msg.session_id === currentSessionId) {
      appendStreamDelta(msg.block_type, msg.delta);
    }

  } else if (msg.type === 'running_state') {
    runningSessions = msg.running_sessions;
    renderSessionList(sessionList, currentSessionId, runningSessions);
    syncRunningState();

  } else if (msg.type === 'container_state') {
    activeContainers = msg.active_containers;
    syncContainerState();

  } else if (msg.type === 'dir_picked') {
    setWorkspaceDir(msg.path);

  } else if (msg.type === 'workspace_error') {
    setWorkspaceError(msg.message);
  }
}

// 3. 建立 WebSocket 连接，断开后自动重连
function connect() {
  ws = new WebSocket(`ws://${location.host}`);
  ws.onmessage = receiveFromBackend;
  ws.onclose = () => {
    setTimeout(connect, 1000);
  };
}

connect();
