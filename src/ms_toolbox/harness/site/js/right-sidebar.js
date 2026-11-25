const rightSidebar = document.getElementById('right-sidebar');
const toggleBtn = rightSidebar.querySelector('.toggle-btn');
const configActions = rightSidebar.querySelector('.config-actions');
const editBtn = configActions.querySelector('.edit-btn');
const saveBtn = configActions.querySelector('.save-btn');
const cancelBtn = configActions.querySelector('.cancel-btn');
const presetSelect = rightSidebar.querySelector('.preset-select');
const applyPresetBtn = rightSidebar.querySelector('.apply-preset-btn');
const openPresetsBtn = rightSidebar.querySelector('.open-presets-btn');
const configForm = rightSidebar.querySelector('.config-form');
const workspaceInput = configForm.querySelector('[name="workspace_dir"]');
const workspaceError = configForm.querySelector('.field-error');
const pickDirBtn = configForm.querySelector('.pick-dir-btn');
const startContainerBtn = rightSidebar.querySelector('.start-container-btn');
const stopContainerBtn = rightSidebar.querySelector('.stop-container-btn');

const CONFIG_KEYS = ['workspace_dir', 'model', 'provider', 'system_prompt'];

let presets = [];
let hasSession = false;
let isEditing = false;
let isRunning = false;
let savedConfig = null;

function fillConfig(cfg) {
  for (const key of CONFIG_KEYS) {
    configForm.querySelector(`[name="${key}"]`).value = cfg[key];
  }
  for (const box of configForm.querySelectorAll('input[name="tools"]')) {
    box.checked = cfg.tools.includes(box.value);
  }
}

function syncConfigUI() {
  const formDisabled = (hasSession && !isEditing) || isRunning;
  configForm.disabled = formDisabled;
  presetSelect.disabled = formDisabled;
  applyPresetBtn.disabled = formDisabled;

  configActions.hidden = !hasSession;
  editBtn.hidden = isEditing;
  saveBtn.hidden = !isEditing;
  cancelBtn.hidden = !isEditing;
  editBtn.disabled = isRunning;
  saveBtn.disabled = isRunning;
}

export function initRightSidebar({
  onOpenPresets,
  onPickDir,
  onSaveConfig,
  onStartContainer,
  onStopContainer,
}) {
  toggleBtn.addEventListener('click', () => {
    const isCollapsed = rightSidebar.classList.toggle('collapsed');
    toggleBtn.textContent = isCollapsed ? '«' : '»';
  });

  applyPresetBtn.addEventListener('click', () => {
    const preset = presets.find((p) => p.name === presetSelect.value);
    if (preset) {
      setWorkspaceError('');
      fillConfig(preset);
    }
  });

  openPresetsBtn.addEventListener('click', onOpenPresets);

  editBtn.addEventListener('click', () => {
    isEditing = true;
    syncConfigUI();
  });

  cancelBtn.addEventListener('click', () => {
    isEditing = false;
    setWorkspaceError('');
    fillConfig(savedConfig);
    syncConfigUI();
  });

  saveBtn.addEventListener('click', () => {
    onSaveConfig(readConfig());
  });

  pickDirBtn.addEventListener('click', onPickDir);

  workspaceInput.addEventListener('input', () => {
    workspaceError.textContent = '';
  });

  startContainerBtn.addEventListener('click', () => {
    startContainerBtn.disabled = true;
    stopContainerBtn.disabled = true;
    onStartContainer();
  });

  stopContainerBtn.addEventListener('click', () => {
    startContainerBtn.disabled = true;
    stopContainerBtn.disabled = true;
    onStopContainer();
  });
}

export function renderPresets(newPresets) {
  const prev = presetSelect.value;
  presets = newPresets;
  presetSelect.innerHTML = '';

  for (const p of presets) {
    const option = document.createElement('option');
    option.value = p.name;
    option.textContent = p.name;
    presetSelect.appendChild(option);
  }

  if (presets.some((p) => p.name === prev)) {
    presetSelect.value = prev;
  } else {
    presetSelect.value = 'default';
  }
}

export function setupNewConfig() {
  hasSession = false;
  isEditing = false;
  savedConfig = null;
  presetSelect.value = 'default';
  setWorkspaceError('');
  fillConfig(presets[0]);
  syncConfigUI();
}

export function setupSavedConfig(cfg) {
  hasSession = true;
  isEditing = false;
  savedConfig = cfg;
  setWorkspaceError('');
  fillConfig(cfg);
  syncConfigUI();
}

export function setConfigRunning(running) {
  isRunning = running;
  if (isRunning && isEditing) {
    isEditing = false;
    setWorkspaceError('');
    fillConfig(savedConfig);
  }
  syncConfigUI();
}

export function readConfig() {
  const cfg = {};
  for (const key of CONFIG_KEYS) {
    cfg[key] = configForm.querySelector(`[name="${key}"]`).value;
  }
  const checkedBoxes = configForm.querySelectorAll('input[name="tools"]:checked');
  cfg.tools = Array.from(checkedBoxes, (box) => box.value);
  return cfg;
}

export function setContainerState(hasActiveSession, isActive) {
  if (!hasActiveSession) {
    startContainerBtn.disabled = true;
    stopContainerBtn.disabled = true;
  } else {
    startContainerBtn.disabled = isActive;
    stopContainerBtn.disabled = !isActive;
  }
}

export function setWorkspaceDir(path) {
  workspaceInput.value = path;
  workspaceError.textContent = '';
}

export function setWorkspaceError(message) {
  workspaceError.textContent = message;
}
