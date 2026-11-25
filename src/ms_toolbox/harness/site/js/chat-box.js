const chatBox = document.getElementById('chat-box');
const attachmentList = chatBox.querySelector('.attachment-list');
const chatInput = chatBox.querySelector('.chat-input');
const fileInput = chatBox.querySelector('.file-input');
const chatAttach = chatBox.querySelector('.chat-attach');
const chatSubmit = chatBox.querySelector('.chat-submit');
const chatStop = chatBox.querySelector('.chat-stop');

let pendingFiles = [];
let isSessionRunning = false;
let handleSend = null;
let handleStop = null;

function renderAttachments() {
  attachmentList.innerHTML = '';

  pendingFiles.forEach((file, index) => {
    const item = document.createElement('div');
    item.className = 'asset-item';

    const img = document.createElement('img');
    img.src = file.data_url;
    img.title = file.name;

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'icon-btn asset-remove';
    removeBtn.textContent = '✕';
    removeBtn.onclick = () => {
      pendingFiles.splice(index, 1);
      renderAttachments();
    };

    item.append(img, removeBtn);
    attachmentList.appendChild(item);
  });
}

function addFiles(files) {
  for (const file of files) {
    if (!file.type.startsWith('image/')) continue;
    const reader = new FileReader();
    reader.onload = () => {
      pendingFiles.push({ name: file.name, data_url: reader.result });
      renderAttachments();
    };
    reader.readAsDataURL(file);
  }
}

function submitInput() {
  if (isSessionRunning) return;
  const text = chatInput.value.trim();
  if (!text && pendingFiles.length === 0) return;
  handleSend(text, pendingFiles);
}

export function initChatBox({ onSend, onStop }) {
  handleSend = onSend;
  handleStop = onStop;

  // 添加图片：按钮选择与剪贴板粘贴
  chatAttach.addEventListener('click', () => {
    fileInput.click();
  });

  fileInput.addEventListener('change', () => {
    addFiles(fileInput.files);
    fileInput.value = '';
  });

  chatInput.addEventListener('paste', (e) => {
    if (e.clipboardData.files.length > 0) {
      e.preventDefault();
      addFiles(e.clipboardData.files);
    }
  });

  // 输入框高度自适应与回车发送
  chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = chatInput.scrollHeight + 'px';
  });

  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitInput();
    }
  });

  chatSubmit.addEventListener('click', submitInput);

  chatStop.addEventListener('click', () => {
    chatStop.disabled = true;
    handleStop();
  });
}

export function resetInput() {
  chatInput.value = '';
  chatInput.style.height = 'auto';
  pendingFiles = [];
  renderAttachments();
}

export function setInputText(text) {
  chatInput.value = text;
  chatInput.style.height = 'auto';
  chatInput.style.height = chatInput.scrollHeight + 'px';
  chatInput.focus();
}

export function setChatRunning(isRunning) {
  isSessionRunning = isRunning;
  chatInput.disabled = isRunning;
  chatAttach.disabled = isRunning;
  chatSubmit.disabled = isRunning;
  chatSubmit.hidden = isRunning;
  chatStop.hidden = !isRunning;
  chatStop.disabled = false;
  chatInput.placeholder = isRunning ? '⏳ AI 思考中...' : '输入内容...';
}
