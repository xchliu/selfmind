async function loadWikiData() {
  try {
    const res = await fetch('/api/wiki/data?t=' + Date.now());
    wikiGraphData = await res.json();
  } catch (e) {
    showToast('❌ 无法加载知识图谱数据', 'error');
    return;
  }
  wikiCurrentViewData = { ...wikiGraphData };
  updateStats(wikiCurrentViewData);
  renderGraph(wikiCurrentViewData);
}

async function handleWikiRefresh() {
  const btn = document.getElementById('btnRefresh');
  btn.classList.add('loading');
  try {
    const res = await fetch('/api/wiki/refresh', { method: 'POST' });
    const json = await res.json();
    if (json.status === 'ok') {
      showToast(`✅ 知识图谱已刷新 — ${json.nodes}个节点, ${json.links}条连线`, 'success');
      await loadWikiData();
    } else {
      showToast(`❌ ${json.message}`, 'error');
    }
  } catch (e) {
    showToast(`❌ 网络错误: ${e.message}`, 'error');
  }
  btn.classList.remove('loading');
}

function buildWikiFilterBar() {
  const bar = document.getElementById('filterBar');
  bar.innerHTML = '';

  // 全部
  const allChip = document.createElement('div');
  allChip.className = 'filter-chip active';
  allChip.textContent = '全部';
  allChip.style.borderColor = 'rgba(0,0,0,0.12)';
  allChip.onclick = () => {
    activeFilters.clear();
    document.querySelectorAll('.filter-chip').forEach(c => {
      c.classList.remove('active');
      c.style.background = '';
      c.style.borderColor = c.dataset.color ? c.dataset.color + '44' : 'rgba(0,0,0,0.12)';
    });
    allChip.classList.add('active');
    applyFilters();
  };
  bar.appendChild(allChip);

  // Wiki 分类
  const wikiFilterCats = ['entity', 'concept', 'comparison', 'query', 'summary', 'wiki_tag'];
  wikiFilterCats.forEach(key => {
    const cat = WIKI_COLORS[key];
    if (!cat) return;
    const chip = document.createElement('div');
    chip.className = 'filter-chip';
    chip.textContent = cat.icon + ' ' + cat.name;
    chip.dataset.cat = key;
    chip.dataset.color = cat.color;
    chip.style.borderColor = cat.color + '44';
    chip.onclick = () => {
      if (activeFilters.has(key)) {
        activeFilters.delete(key);
        chip.classList.remove('active');
        chip.style.background = '';
        chip.style.borderColor = cat.color + '44';
      } else {
        activeFilters.add(key);
        chip.classList.add('active');
        chip.style.background = cat.color + '22';
        chip.style.borderColor = cat.color;
      }
      // 取消"全部"高亮
      const allC = bar.querySelector('.filter-chip:first-child');
      allC.classList.toggle('active', activeFilters.size === 0);
      applyFilters();
    };
    bar.appendChild(chip);
  });
}

// 获取当前活跃的数据（根据视图）
function getActiveData() {
  if (currentView === 'wiki') return wikiCurrentViewData || wikiGraphData;
  return currentViewData || graphData;
}

// 初始化
buildFilterBar();
loadData();
loadIQ();
loadSourceStatus();

// 快捷键
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') hideDetail();
  if ((e.metaKey || e.ctrlKey) && e.key === 'f') {
    e.preventDefault();
    document.getElementById('searchInput').focus();
  }
});

// 窗口大小变化
window.addEventListener('resize', () => {
  if (getActiveData()) renderGraph(getActiveData());
});

// ========== 记忆管理模块 ==========
let memoryPanelOpen = false;
let currentMemoryTab = 'import';
let memoryEntries = [];
let scannedFiles = [];
let selectedMemoryIds = new Set();
let selectedSyncIds = new Set();
let selectedFileIndices = new Set();
let memoryFilters = { status: 'all', primary: 'all' };
let memoryStats = null;
let syncTargetAgent = 'hermes';
let memoryExtracting = false;
let memoryScanning = false;
let extractResultCount = null;
let autoImporting = false;
let autoImportProgress = null; // { current, total, file, totalExtracted, log }
let autoImportEventSource = null;

const MEMORY_PRIMARY_CATEGORIES = [
  'autobiographical', 'semantic', 'episodic', 'procedural',
  'social', 'working', 'spatial', 'emotional'
];
const MEMORY_STATUS_LABELS = {
  'all': '全部', 'pending': '待审核', 'approved': '已通过',
  'synced': '已同步', 'rejected': '已拒绝'
};
const MEMORY_PRIMARY_LABELS = {
  'autobiographical': '自传体', 'semantic': '语义', 'episodic': '情景',
  'procedural': '程序性', 'social': '社交', 'working': '工作',
  'spatial': '空间', 'emotional': '情感'
};

function toggleMemoryPanel() {
  memoryPanelOpen = !memoryPanelOpen;
  document.getElementById('memoryPanel').classList.toggle('open', memoryPanelOpen);
  document.getElementById('memoryOverlay').classList.toggle('open', memoryPanelOpen);
  if (memoryPanelOpen) {
    renderCurrentMemoryTab();
  }
}

function switchMemoryTab(tab) {
  currentMemoryTab = tab;
  document.querySelectorAll('.memory-tab').forEach(t => t.classList.remove('active'));
  const tabMap = { 'import': 'memTabImport', 'list': 'memTabList', 'sync': 'memTabSync' };
  document.getElementById(tabMap[tab]).classList.add('active');
  renderCurrentMemoryTab();
}

function renderCurrentMemoryTab() {
  if (currentMemoryTab === 'import') renderImportTab();
  else if (currentMemoryTab === 'list') { loadMemories(); }
  else if (currentMemoryTab === 'sync') { loadMemoryStats(); }
}

// ===== 文档导入 =====
function renderImportArea() {
  const area = document.getElementById('memoryImportArea');
  if (!area) return;
  renderImportContent(area);
}

function renderImportTab() {
  const area = document.getElementById('memoryImportArea') || document.getElementById('memoryContentArea');
  if (!area) return;
  renderImportContent(area);
}

function renderImportContent(area) {
  let html = '';

  // Auto import progress — expanded view
  if (autoImporting && autoImportProgress) {
    const p = autoImportProgress;
    const pct = p.total > 0 ? Math.round((p.current / p.total) * 100) : 0;
    html += `<div class="import-progress-compact">
      <div class="import-progress-bar" style="width:${pct}%"></div>
      <span>${p.phase || '处理中...'} · ${p.totalExtracted || 0} 条</span>
      <button class="import-btn-stop" onclick="stopAutoImport()">⏹</button>
    </div>`;
  } else if (autoImportProgress && autoImportProgress.done) {
    const p = autoImportProgress;
    html += `<div class="import-result-compact">
      ✅ ${p.processed || 0} 文件 → ${p.totalExtracted || 0} 条记忆
      <button class="import-btn-small" onclick="autoImportProgress=null;renderImportTab()">重新导入</button>
    </div>`;
  } else if (memoryScanning) {
    html += `<div class="import-progress-compact">
      <div class="import-progress-spinner-inline"></div>
      <span>扫描中...</span>
    </div>`;
  } else if (scannedFiles.length > 0) {
    // Manual mode: compact file list
    html += `<div class="import-file-select-compact">
      <span>${scannedFiles.length} 文件 · 已选 ${selectedFileIndices.size}</span>
      <button class="import-btn-small" onclick="selectedFileIndices.size===0?'':extractMemories()" ${selectedFileIndices.size === 0 ? 'disabled' : ''}>🧬 提取</button>
      <button class="import-btn-small" onclick="toggleImportFileList()">展开</button>
    </div>`;
    if (importFileListExpanded) {
      html += `<div class="import-file-list-mini">`;
      scannedFiles.forEach((f, i) => {
        const checked = selectedFileIndices.has(i) ? 'checked' : '';
        html += `<div class="import-file-item-mini">
          <input type="checkbox" ${checked} onchange="toggleFileSelect(${i}, this.checked)">
          <span>${escapeHtml(f.name)}</span>
        </div>`;
      });
      html += `</div>`;
    }
    if (extractResultCount !== null) {
      html += `<div class="import-result-compact">✅ 提取 ${extractResultCount} 条</div>`;
    }
  } else {
    // Default: single-line input + button
    html += `<div class="import-line">
      <input type="text" id="memDocDir" placeholder="目录路径" value="" class="import-input">
      <button class="import-btn" onclick="startAutoImport()" ${autoImporting ? 'disabled' : ''}>🚀 导入</button>
      <button class="import-btn-secondary" onclick="scanDocuments()" ${memoryScanning || autoImporting ? 'disabled' : ''} title="手动扫描">🔍</button>
    </div>`;
  }

  area.innerHTML = html;
}

// File list expand/collapse toggle
let importFileListExpanded = false;
function toggleImportFileList() {
  importFileListExpanded = !importFileListExpanded;
  renderImportTab();
}

function startAutoImport() {
  const dirInput = document.getElementById('memDocDir');
  const dir = dirInput ? dirInput.value.trim() : '';
  if (!dir) { showToast('请输入目录路径', 'error'); return; }
  if (autoImporting) return;

  autoImporting = true;
  autoImportProgress = { current: 0, total: 0, file: '', totalExtracted: 0, phase: '🔍 扫描目录...', log: [], done: false };
  renderImportTab();

  const url = `/api/documents/extract-stream?dir=${encodeURIComponent(dir)}`;
  autoImportEventSource = new EventSource(url);

  autoImportEventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      const p = autoImportProgress;

      switch (data.type) {
        case 'scanning':
          p.phase = '🔍 扫描目录...';
          break;
        case 'scan_done':
          p.total = data.total_files;
          p.phase = `📦 发现 ${data.total_files} 个文件，开始提取...`;
          p.log.push({ type: 'info', text: `发现 ${data.total_files} 个文件: ${data.files.join(', ')}` });
          break;
        case 'extracting':
          p.current = data.current;
          p.total = data.total;
          p.file = data.file;
          p.phase = `🧬 提取中 (${data.current}/${data.total})`;
          break;
        case 'file_done':
          p.current = data.current;
          p.totalExtracted = data.total_extracted;
          p.log.push({ type: 'success', text: `✅ ${data.file} → ${data.extracted} 条记忆` });
          break;
        case 'file_skipped':
          p.current = data.current;
          p.log.push({ type: 'warn', text: `⏭ ${data.file} — ${data.reason}` });
          break;
        case 'file_error':
          p.current = data.current;
          p.log.push({ type: 'error', text: `❌ ${data.file} — ${data.error}` });
          break;
        case 'error':
          p.phase = `❌ ${data.message}`;
          p.log.push({ type: 'error', text: data.message });
          stopAutoImport();
          showToast(data.message, 'error');
          return;
        case 'done':
          p.current = p.total;
          p.totalExtracted = data.total_extracted;
          p.processed = data.processed;
          p.skipped = data.skipped;
          p.done = true;
          autoImporting = false;
          if (autoImportEventSource) { autoImportEventSource.close(); autoImportEventSource = null; }
          showToast(`✅ 导入完成！提取 ${data.total_extracted} 条记忆`, 'success');
          break;
      }
      renderImportTab();

      // Auto-scroll log to bottom
      const logEl = document.querySelector('.auto-import-log');
      if (logEl) logEl.scrollTop = logEl.scrollHeight;
    } catch (e) {
      console.error('SSE parse error:', e);
    }
  };

  autoImportEventSource.onerror = () => {
    if (autoImporting) {
      autoImporting = false;
      if (autoImportProgress) autoImportProgress.phase = '连接中断';
      renderImportTab();
      showToast('导入连接中断', 'error');
    }
    if (autoImportEventSource) { autoImportEventSource.close(); autoImportEventSource = null; }
  };
}

function stopAutoImport() {
  if (autoImportEventSource) {
    autoImportEventSource.close();
    autoImportEventSource = null;
  }
  autoImporting = false;
  if (autoImportProgress) {
    autoImportProgress.phase = '⏹ 已停止';
    autoImportProgress.done = true;
  }
  renderImportTab();
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function toggleAllFiles(checked) {
  if (checked) {
    scannedFiles.forEach((_, i) => selectedFileIndices.add(i));
  } else {
    selectedFileIndices.clear();
  }
  renderImportTab();
}

function toggleFileSelect(index, checked) {
  if (checked) selectedFileIndices.add(index);
  else selectedFileIndices.delete(index);
  renderImportTab();
}

async function scanDocuments() {
  const dirInput = document.getElementById('memDocDir');
  const dir = dirInput ? dirInput.value.trim() : '';
  if (!dir) { showToast('请输入目录路径', 'error'); return; }
  memoryScanning = true;
  scannedFiles = [];
  selectedFileIndices.clear();
  extractResultCount = null;
  renderImportTab();
  try {
    const res = await fetch(`/api/documents/scan?dir=${encodeURIComponent(dir)}`);
    const json = await res.json();
    scannedFiles = json.files || json.data || [];
    if (scannedFiles.length === 0) {
      showToast('未找到可导入的文档', 'info');
    } else {
      showToast(`发现 ${scannedFiles.length} 个文档`, 'success');
    }
  } catch (e) {
    showToast(`扫描失败: ${e.message}`, 'error');
  }
  memoryScanning = false;
  renderImportTab();
}

async function extractMemories() {
  if (selectedFileIndices.size === 0) return;
  memoryExtracting = true;
  extractResultCount = null;
  renderImportTab();
  try {
    const files = Array.from(selectedFileIndices).map(i => scannedFiles[i].path || scannedFiles[i].name);
    let totalExtracted = 0;
    for (const file of files) {
      const res = await fetch('/api/documents/extract', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file })
      });
      const json = await res.json();
      totalExtracted += (json.count || json.extracted || (json.memories ? json.memories.length : 0));
    }
    extractResultCount = totalExtracted;
    showToast(`✅ 成功提取 ${totalExtracted} 条记忆`, 'success');
  } catch (e) {
    showToast(`提取失败: ${e.message}`, 'error');
  }
  memoryExtracting = false;
  renderImportTab();
}

// ===== Tab 2: 记忆列表 =====
async function loadMemories() {
  const area = document.getElementById('memoryContentArea');
  area.innerHTML = `<div class="memory-progress">
    <div class="memory-progress-spinner"></div>
    <div class="memory-progress-text">加载记忆列表...</div>
  </div>`;
  try {
    let url = '/api/memories?t=' + Date.now();
    if (memoryFilters.status !== 'all') url += `&status=${memoryFilters.status}`;
    if (memoryFilters.primary !== 'all') url += `&primary=${memoryFilters.primary}`;
    const res = await fetch(url);
    const json = await res.json();
    memoryEntries = json.entries || json.data || json.memories || json || [];
    if (Array.isArray(json)) memoryEntries = json;
  } catch (e) {
    showToast(`加载失败: ${e.message}`, 'error');
    memoryEntries = [];
  }
  renderMemoryList();
}

function renderMemoryList() {
  const area = document.getElementById('memoryContentArea');
  let html = `<div class="memory-filter">
    <select id="memFilterStatus" onchange="memoryFilters.status=this.value; loadMemories()">
      ${Object.entries(MEMORY_STATUS_LABELS).map(([k,v]) =>
        `<option value="${k}" ${memoryFilters.status===k?'selected':''}>${v}</option>`
      ).join('')}
    </select>
    <select id="memFilterPrimary" onchange="memoryFilters.primary=this.value; loadMemories()">
      <option value="all" ${memoryFilters.primary==='all'?'selected':''}>全部分类</option>
      ${MEMORY_PRIMARY_CATEGORIES.map(c =>
        `<option value="${c}" ${memoryFilters.primary===c?'selected':''}>${MEMORY_PRIMARY_LABELS[c] || c}</option>`
      ).join('')}
    </select>
  </div>`;

  html += `<div class="memory-bulk">
    <label>
      <input type="checkbox" id="memSelectAll" onchange="toggleAllMemories(this.checked)"
        ${selectedMemoryIds.size > 0 && selectedMemoryIds.size === memoryEntries.length ? 'checked' : ''}>
      全选
    </label>
    <button class="memory-btn memory-btn-success" onclick="bulkAction('approved')">✅ 通过</button>
    <button class="memory-btn memory-btn-danger" onclick="bulkAction('rejected')">❌ 拒绝</button>
    <button class="memory-btn memory-btn-secondary" onclick="bulkAction('delete')">🗑️ 删除</button>
    <span class="memory-entry-count">共 ${memoryEntries.length} 条</span>
  </div>`;

  if (memoryEntries.length === 0) {
    html += `<div class="memory-empty">
      <div class="memory-empty-icon">📭</div>
      <div>暂无记忆条目</div>
    </div>`;
  } else {
    memoryEntries.forEach(m => {
      const checked = selectedMemoryIds.has(m.id) ? 'checked' : '';
      const statusClass = `memory-badge-${m.status || 'pending'}`;
      const statusText = MEMORY_STATUS_LABELS[m.status] || m.status || '待审核';
      const primaryLabel = MEMORY_PRIMARY_LABELS[m.primary] || m.primary || '';
      const date = m.createdAt ? new Date(m.createdAt).toLocaleDateString('zh-CN') : '';
      html += `<div class="memory-card">
        <div class="memory-card-header">
          <input type="checkbox" class="memory-card-check" ${checked}
            onchange="toggleMemorySelect('${m.id}', this.checked)">
          <div class="memory-card-label">${escapeHtml(m.label || m.text || '')}</div>
          <span class="memory-badge memory-badge-status ${statusClass}">${statusText}</span>
        </div>
        <div class="memory-card-badges">
          ${primaryLabel ? `<span class="memory-badge memory-badge-primary">${primaryLabel}</span>` : ''}
          ${m.secondary ? `<span class="memory-badge memory-badge-secondary">${escapeHtml(m.secondary)}</span>` : ''}
        </div>
        ${m.description ? `<div class="memory-card-desc">${escapeHtml(m.description)}</div>` : ''}
        <div class="memory-card-meta">
          <span class="memory-card-source" title="${escapeHtml(m.source_file || '')}">📄 ${escapeHtml(m.source_file || '未知来源')}</span>
          <span>${date}</span>
        </div>
        <div class="memory-actions">
          <button class="memory-action-btn approve" onclick="approveMemory('${m.id}')">✅ 通过</button>
          <button class="memory-action-btn reject" onclick="rejectMemory('${m.id}')">❌ 拒绝</button>
          <button class="memory-action-btn delete" onclick="deleteMemory('${m.id}')">🗑️ 删除</button>
        </div>
      </div>`;
    });
  }
  area.innerHTML = html;
}

function toggleAllMemories(checked) {
  selectedMemoryIds.clear();
  if (checked) {
    memoryEntries.forEach(m => selectedMemoryIds.add(m.id));
  }
  renderMemoryList();
}

function toggleMemorySelect(id, checked) {
  if (checked) selectedMemoryIds.add(id);
  else selectedMemoryIds.delete(id);
  // Don't re-render the whole list, just let the checkbox state remain
}

async function approveMemory(id) {
  try {
    await fetch(`/api/memories/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'approved' })
    });
    showToast('✅ 已通过', 'success');
    loadMemories();
  } catch (e) {
    showToast(`操作失败: ${e.message}`, 'error');
  }
}

async function rejectMemory(id) {
  try {
    await fetch(`/api/memories/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'rejected' })
    });
    showToast('❌ 已拒绝', 'success');
    loadMemories();
  } catch (e) {
    showToast(`操作失败: ${e.message}`, 'error');
  }
}

async function deleteMemory(id) {
  if (!confirm('确定要删除这条记忆吗？')) return;
  try {
    await fetch(`/api/memories/${id}`, { method: 'DELETE' });
    showToast('🗑️ 已删除', 'success');
    selectedMemoryIds.delete(id);
    loadMemories();
  } catch (e) {
    showToast(`删除失败: ${e.message}`, 'error');
  }
}

async function bulkAction(action) {
  if (selectedMemoryIds.size === 0) {
    showToast('请先选择条目', 'info');
    return;
  }
  const ids = Array.from(selectedMemoryIds);
  if (action === 'delete') {
    if (!confirm(`确定删除 ${ids.length} 条记忆？`)) return;
    try {
      for (const id of ids) {
        await fetch(`/api/memories/${id}`, { method: 'DELETE' });
      }
      showToast(`🗑️ 已删除 ${ids.length} 条`, 'success');
    } catch (e) {
      showToast(`批量删除失败: ${e.message}`, 'error');
    }
  } else {
    try {
      await fetch('/api/memories/bulk-status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids, status: action })
      });
      showToast(`✅ 已批量${action === 'approved' ? '通过' : '拒绝'} ${ids.length} 条`, 'success');
    } catch (e) {
      showToast(`批量操作失败: ${e.message}`, 'error');
    }
  }
  selectedMemoryIds.clear();
  loadMemories();
}

// ===== Tab 3: 同步管理 =====
async function loadMemoryStats() {
  const area = document.getElementById('syncManageArea');
  if (!area) return;
  area.innerHTML = `<div class="memory-progress">
    <div class="memory-progress-spinner"></div>
    <div class="memory-progress-text">加载统计数据...</div>
  </div>`;
  try {
    const res = await fetch('/api/memories/stats?t=' + Date.now());
    memoryStats = await res.json();
  } catch (e) {
    memoryStats = { total: 0, pending: 0, approved: 0, synced: 0, rejected: 0 };
  }
  // Also load approved entries for sync list
  try {
    const res2 = await fetch('/api/memories?status=approved&t=' + Date.now());
    const json2 = await res2.json();
    const approved = json2.entries || json2.data || json2.memories || json2 || [];
    memoryStats._approvedEntries = Array.isArray(approved) ? approved : [];
  } catch (e) {
    memoryStats._approvedEntries = [];
  }
  renderSyncArea();
}

function renderSyncArea() {
  const area = document.getElementById('syncManageArea');
  if (!area) return;
  const s = memoryStats || { total: 0, pending: 0, approved: 0, synced: 0, rejected: 0 };
  const approvedEntries = s._approvedEntries || [];

  let html = `<div class="memory-section-title">📊 记忆统计</div>
  <div class="memory-stat-grid">
    <div class="memory-stat-card purple">
      <div class="memory-stat-card-number">${s.total || 0}</div>
      <div class="memory-stat-card-label">总记忆数</div>
    </div>
    <div class="memory-stat-card orange">
      <div class="memory-stat-card-number">${s.pending || 0}</div>
      <div class="memory-stat-card-label">待审核</div>
    </div>
    <div class="memory-stat-card green">
      <div class="memory-stat-card-number">${s.approved || 0}</div>
      <div class="memory-stat-card-label">已通过</div>
    </div>
    <div class="memory-stat-card blue">
      <div class="memory-stat-card-number">${s.synced || 0}</div>
      <div class="memory-stat-card-label">已同步</div>
    </div>
  </div>`;

  html += `<div class="memory-section-title">🤖 同步目标</div>
  <div class="memory-agent-grid">
    <div class="memory-agent-card ${syncTargetAgent === 'hermes' ? 'selected' : ''}" onclick="selectSyncAgent('hermes')">
      <div class="memory-agent-icon">🏛️</div>
      <div class="memory-agent-name">Hermes</div>
      <div class="memory-agent-desc">通用智能助手</div>
    </div>
    <div class="memory-agent-card ${syncTargetAgent === 'openclaw' ? 'selected' : ''}" onclick="selectSyncAgent('openclaw')">
      <div class="memory-agent-icon">🦀</div>
      <div class="memory-agent-name">OpenClaw</div>
      <div class="memory-agent-desc">专业编程助手</div>
    </div>
  </div>`;

  html += `<div class="memory-section-title">📋 待同步条目 (已通过)</div>`;
  if (approvedEntries.length === 0) {
    html += `<div class="memory-empty">
      <div class="memory-empty-icon">✨</div>
      <div>没有待同步的条目，请先审核记忆</div>
    </div>`;
  } else {
    html += `<div class="doc-select-bar">
      <label>
        <input type="checkbox" onchange="toggleAllSyncItems(this.checked)"
          ${selectedSyncIds.size === approvedEntries.length && approvedEntries.length > 0 ? 'checked' : ''}>
        全选
      </label>
      <span>已选 ${selectedSyncIds.size} / ${approvedEntries.length}</span>
    </div>
    <div class="memory-sync-list">`;
    approvedEntries.forEach(m => {
      const checked = selectedSyncIds.has(m.id) ? 'checked' : '';
      html += `<div class="memory-sync-item">
        <input type="checkbox" ${checked} onchange="toggleSyncItem('${m.id}', this.checked)">
        <span class="memory-sync-item-label">${escapeHtml(m.label || m.text || '')}</span>
        <span class="memory-badge memory-badge-primary">${MEMORY_PRIMARY_LABELS[m.primary] || m.primary || ''}</span>
      </div>`;
    });
    html += `</div>
    <button class="memory-btn memory-btn-primary" onclick="syncMemories()"
      style="width:100%;padding:10px" ${selectedSyncIds.size === 0 ? 'disabled' : ''}>
      🚀 同步到 ${syncTargetAgent === 'hermes' ? 'Hermes' : 'OpenClaw'} (${selectedSyncIds.size} 条)
    </button>`;
  }

  area.innerHTML = html;
}

function selectSyncAgent(agent) {
  syncTargetAgent = agent;
  renderSyncArea();
}

function toggleAllSyncItems(checked) {
  selectedSyncIds.clear();
  if (checked && memoryStats && memoryStats._approvedEntries) {
    memoryStats._approvedEntries.forEach(m => selectedSyncIds.add(m.id));
  }
  renderSyncArea();
}

function toggleSyncItem(id, checked) {
  if (checked) selectedSyncIds.add(id);
  else selectedSyncIds.delete(id);
  renderSyncArea();
}

async function syncMemories() {
  if (selectedSyncIds.size === 0) {
    showToast('请先选择要同步的条目', 'info');
    return;
  }
  const ids = Array.from(selectedSyncIds);
  try {
    const res = await fetch('/api/memories/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids, agent: syncTargetAgent })
    });
    const json = await res.json();
    const syncedCount = json.synced || json.count || ids.length;
    showToast(`🚀 已同步 ${syncedCount} 条记忆到 ${syncTargetAgent === 'hermes' ? 'Hermes' : 'OpenClaw'}`, 'success');
    selectedSyncIds.clear();
    loadMemoryStats();
  } catch (e) {
    showToast(`同步失败: ${e.message}`, 'error');
  }
}

// Escape key also closes memory panel
const _origKeydown = document.onkeydown;
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && memoryPanelOpen) {
    toggleMemoryPanel();
  }
});

// ========== 记忆健康仪表盘 ==========
let healthSortKey = 'decay_score', healthSortAsc = true, healthEntries = [];
let healthFilteredEntries = [];

function healthSwitchTab(tab, btn) {
  document.querySelectorAll('.health-section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.health-tab').forEach(t => t.classList.remove('active'));
  const sectionId = 'healthSection' + tab.charAt(0).toUpperCase() + tab.slice(1);
  const section = document.getElementById(sectionId);
  if (section) section.classList.add('active');
  btn.classList.add('active');
  if (tab === 'snapshots') loadHealthSnapshots();
  if (tab === 'decayCurve') renderDecayCurve();
}

// ========== 设置功能 ==========
let settingsAgentConfig = null;

async function loadSettingsData() {
  try {
    const res = await fetch('/api/agents/config');
    const data = await res.json();
    settingsAgentConfig = data;
    
    // 根据current_agent更新页面标题
    const activeAgentId = data.current_agent || 'hermes';
    const agents = data.agents || [];
    const activeAgentObj = agents.find(a => a.id === activeAgentId);
    const activeAgentName = activeAgentObj ? activeAgentObj.name : activeAgentId;
    document.title = activeAgentName + ' · SelfMind';
    const titleEl = document.querySelector('#mainTitle') || document.querySelector('.title-text');
    if (titleEl) titleEl.textContent = activeAgentName + ' · SelfMind';
    const selector = document.getElementById('agentSelector');
    if (selector && agents.length > 0) {
      selector.innerHTML = agents.map(a => `<option value="${a.id}">${a.type === 'hermes' ? '🧠' : '🤖'} ${a.name}</option>`).join('');
      selector.value = activeAgentId;
    }
    
    const listEl = document.getElementById('agentsList');
    if (!listEl) return;
    
    if (agents.length === 0) {
      listEl.innerHTML = '<p style="color:#999; font-size:13px;">暂无Agent，点击添加按钮创建</p>';
      return;
    }
    
    // 并行探测所有agent的gateway状态
    const gatewayStatuses = {};
    const discoverPromises = agents.map(async (agent) => {
      if (agent.gateway) {
        try {
          const dr = await fetch('/api/agents/discover?gateway=' + encodeURIComponent(agent.gateway));
          const dd = await dr.json();
          gatewayStatuses[agent.id] = dd.reachable ? 'online' : 'offline';
        } catch {
          gatewayStatuses[agent.id] = 'offline';
        }
      } else {
        gatewayStatuses[agent.id] = 'no_gateway';
      }
    });
    await Promise.all(discoverPromises);
    
    const currentAgentId = data.current_agent || 'hermes';
    listEl.innerHTML = agents.map((agent, idx) => {
      const isCurrent = agent.id === currentAgentId;
      const gwStatus = gatewayStatuses[agent.id] || 'no_gateway';
      const statusIcon = gwStatus === 'online' ? '🟢' : gwStatus === 'offline' ? '🔴' : '⚪';
      const icon = agent.name === '苏格拉底' ? '🧠' : agent.name === '小亚' ? '🤖' : (agent.type === 'hermes' ? '🧠' : '⚙️');
      return `
      <div class="agent-card" style="background:${isCurrent ? '#f0f4ff' : '#fff'}; border-radius:12px; border:2px solid ${isCurrent ? '#667eea' : '#e2e8f0'}; overflow:hidden; margin-bottom:12px; transition:all 0.2s;">
        <div style="padding:14px 18px; display:flex; align-items:center; justify-content:space-between;">
          <div style="display:flex; align-items:center; gap:12px;">
            <div style="width:44px; height:44px; border-radius:12px; background:${isCurrent ? '#667eea' : '#f1f5f9'}; display:flex; align-items:center; justify-content:center; font-size:22px; color:${isCurrent ? '#fff' : '#667eea'};">${icon}</div>
            <div>
              <div style="font-size:16px; font-weight:600; color:#2d3436;">${agent.name} ${isCurrent ? '<span style="color:#667eea; font-size:11px; background:#667eea18; padding:2px 8px; border-radius:4px; margin-left:6px;">正在查看</span>' : ''}</div>
              <div style="font-size:12px; color:#888; margin-top:2px;">${statusIcon} ${agent.gateway || '未配置'} · ${agent.type || 'hermes'}类型</div>
            </div>
          </div>
          <div style="display:flex; gap:8px;">
            ${isCurrent ? '<span style="padding:4px 10px; background:#667eea; color:#fff; border-radius:6px; font-size:12px; font-weight:500;">✅ 当前</span>' : ''}
          </div>
        </div>
        <div id="agentDetail_${idx}" style="display:none; padding:14px 18px; border-top:1px solid #e0e0e0; background:#fafbfc;">
          <div style="display:flex; flex-direction:column; gap:10px;">
            <div>
              <label style="display:block; font-size:12px; font-weight:500; color:#888; margin-bottom:3px;">Gateway 地址</label>
              <input type="text" class="agent-field" data-agent="${idx}" data-field="gateway" value="${agent.gateway || ''}" style="width:100%; padding:7px 11px; border:1px solid #e0e0e0; border-radius:6px; font-size:13px;">
            </div>
            <div>
              <label style="display:block; font-size:12px; font-weight:500; color:#888; margin-bottom:3px;">Memory 路径</label>
              <input type="text" class="agent-field" data-agent="${idx}" data-field="memory_path" value="${agent.memory_path || ''}" style="width:100%; padding:7px 11px; border:1px solid #e0e0e0; border-radius:6px; font-size:13px;">
            </div>
            <div>
              <label style="display:block; font-size:12px; font-weight:500; color:#888; margin-bottom:3px;">Skills 路径</label>
              <input type="text" class="agent-field" data-agent="${idx}" data-field="skills_path" value="${agent.skills_path || ''}" style="width:100%; padding:7px 11px; border:1px solid #e0e0e0; border-radius:6px; font-size:13px;">
            </div>
            <div>
              <label style="display:block; font-size:12px; font-weight:500; color:#888; margin-bottom:3px;">Honcho API</label>
              <input type="text" class="agent-field" data-agent="${idx}" data-field="honcho_url" value="${agent.honcho_url || ''}" style="width:100%; padding:7px 11px; border:1px solid #e0e0e0; border-radius:6px; font-size:13px;">
            </div>
            <div>
              <label style="display:block; font-size:12px; font-weight:500; color:#888; margin-bottom:3px;">Wiki 路径</label>
              <input type="text" class="agent-field" data-agent="${idx}" data-field="wiki_path" value="${agent.wiki_path || ''}" style="width:100%; padding:7px 11px; border:1px solid #e0e0e0; border-radius:6px; font-size:13px;">
            </div>
            <div style="display:flex; gap:8px; margin-top:4px;">
              <button onclick="saveAgentConfig(${idx})" style="padding:8px 16px; background:#10b981; color:#fff; border:none; border-radius:6px; cursor:pointer;">保存</button>
              <button onclick="toggleAgentDetail(${idx})" style="padding:8px 16px; background:#e0e0e0; color:#444; border:none; border-radius:6px; cursor:pointer;">收起</button>
            </div>
          </div>
        </div>
      </div>`;
    }).join('');
  } catch (e) {
    console.error('加载设置失败:', e);
    const listEl = document.getElementById('agentsList');
    if (listEl) listEl.innerHTML = '<p style="color:#ef4444;">加载失败</p>';
  }
}

function toggleAgentDetail(idx) {
  const el = document.getElementById('agentDetail_' + idx);
  if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

// ========== Agent切换功能 ==========
async function switchAgentView(agentId) {
  showToast('切换测序对象...', 'info');
  // 暂停autoPoll防止切换期间poll覆盖新数据
  if (pollingInterval) { clearInterval(pollingInterval); pollingInterval = null; }
  try {
    const res = await fetch('/api/agents/' + agentId + '/switch', { method: 'PUT' });
    const data = await res.json();
    if (data.status === 'ok') {
      const agentName = data.agent_name || agentId;
      document.title = agentName + ' · SelfMind';
      const titleEl = document.querySelector('#mainTitle') || document.querySelector('.title-text');
      if (titleEl) titleEl.textContent = agentName + ' · SelfMind';
      const selector = document.getElementById('agentSelector');
      if (selector) selector.value = agentId;
      const sourceName = document.querySelector('.source-bar .source-name');
      if (sourceName) sourceName.textContent = 'selfmind-' + agentId;
      if (data.graph_data && data.graph_data.nodes) {
        graphData = data.graph_data;
        timelinePoints = buildTimelinePoints(graphData);
        applyTimepoint(timelinePoints.length - 1);
      }
      try {
        const statsRes = await fetch('/api/stats');
        const statsData = await statsRes.json();
        if (statsData) sedimentLiveStats = statsData;
        const countEl = document.querySelector('.source-bar .source-count');
        if (countEl && statsData) countEl.textContent = (statsData.total_entries || graphData.nodes.length) + ' 条';
      } catch (e) { console.error('refresh stats failed:', e); }
      showToast('✅ 已切换到 ' + agentName, 'success');
      loadSettingsData();
      loadIQ();
      lastPollHash = null;
      startPolling();
    } else {
      showToast('切换失败: ' + (data.error || 'unknown'), 'error');
      startPolling();
    }
  } catch (e) {
    showToast('切换失败: ' + e.message, 'error');
    startPolling();
  }
}

async function refreshAllViews() {
  try {
    const statsRes = await fetch('/api/stats');
    const statsData = await statsRes.json();
    if (statsData) sedimentLiveStats = statsData;
  } catch (e) { console.error('refresh stats failed:', e); }
}

function showAddAgentForm() {
  document.getElementById('addAgentForm').style.display = 'block';
  document.getElementById('discoverResult').style.display = 'none';
}

function hideAddAgentForm() {
  document.getElementById('addAgentForm').style.display = 'none';
  document.getElementById('newAgentName').value = '';
  document.getElementById('newAgentGateway').value = '';
  document.getElementById('newAgentType').value = 'hermes';
  document.getElementById('discoverResult').style.display = 'none';
}

let discoveredAgentInfo = null;

async function discoverGateway() {
  const gateway = document.getElementById('newAgentGateway').value.trim();
  if (!gateway) {
    showToast('请填写Gateway地址', 'error');
    return;
  }
  
  const btn = document.getElementById('discoverBtn');
  btn.textContent = '⏳ 探测中...';
  btn.disabled = true;
  
  try {
    const res = await fetch('/api/agents/discover?gateway=' + encodeURIComponent(gateway));
    const data = await res.json();
    
    discoveredAgentInfo = data;
    const resultEl = document.getElementById('discoverResult');
    const infoEl = document.getElementById('discoverInfo');
    
    if (!data.reachable) {
      resultEl.style.display = 'block';
      resultEl.style.background = '#fef2f2';
      resultEl.style.borderColor = '#ef444430';
      infoEl.innerHTML = `<div style="color:#ef4444; font-weight:600;">❌ Gateway不可达</div>
        <div style="color:#666; margin-top:4px;">${data.error || '连接失败'}</div>`;
      btn.textContent = '🔍 探测';
      btn.disabled = false;
      return;
    }
    
    // 成功探测
    resultEl.style.display = 'block';
    resultEl.style.background = '#f0f4ff';
    resultEl.style.borderColor = '#667eea30';
    
    const ai = data.agent_info || {};
    const pathsValid = data.paths_valid || {};
    
    let infoHtml = `<div style="color:#10b981; font-weight:600; margin-bottom:6px;">✅ Gateway已连接</div>`;
    infoHtml += `<div style="margin-top:4px;"><strong>平台:</strong> ${ai.platform || 'unknown'} · <strong>类型:</strong> ${ai.type || 'unknown'}</div>`;
    if (ai.name) infoHtml += `<div><strong>名称:</strong> ${ai.name}</div>`;
    if (ai.connected_platforms && ai.connected_platforms.length > 0) {
      infoHtml += `<div><strong>已连接平台:</strong> ${ai.connected_platforms.join(', ')}</div>`;
    }
    if (pathsValid && Object.keys(pathsValid).length > 0) {
      infoHtml += `<div style="margin-top:6px;"><strong>路径验证:</strong></div>`;
      for (const [k, v] of Object.entries(pathsValid)) {
        infoHtml += `<div style="color:${v ? '#10b981' : '#ef4444'};">${v ? '✅' : '❌'} ${k}: ${ai[k + '_path'] || '未知'}</div>`;
      }
    }
    if (ai.memory_file_exists !== undefined) {
      infoHtml += `<div style="color:${ai.memory_file_exists ? '#10b981' : '#ef4444'};">${ai.memory_file_exists ? '✅' : '❌'} MEMORY.md 存在</div>`;
    }
    
    infoEl.innerHTML = infoHtml;
    
    // 自动填充表单
    if (ai.name) {
      document.getElementById('newAgentName').value = ai.name;
    }
    if (ai.type) {
      document.getElementById('newAgentType').value = ai.type;
    }
    
    showToast('✅ Gateway探测成功', 'success');
  } catch (e) {
    showToast('探测失败: ' + e.message, 'error');
    document.getElementById('discoverResult').style.display = 'block';
    document.getElementById('discoverResult').style.background = '#fef2f2';
    document.getElementById('discoverInfo').innerHTML = `<div style="color:#ef4444;">❌ 探测请求失败: ${e.message}</div>`;
  }
  
  btn.textContent = '🔍 探测';
  btn.disabled = false;
}

async function addAgent() {
  const name = document.getElementById('newAgentName').value.trim();
  const gateway = document.getElementById('newAgentGateway').value.trim();
  const type = document.getElementById('newAgentType').value;
  
  if (!gateway) {
    showToast('请填写Gateway地址', 'error');
    return;
  }
  
  try {
    const res = await fetch('/api/agents/config', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        action: 'add',
        agent: { 
          id: (name || type).toLowerCase().replace(/\s+/g, '-'), 
          name: name || type, 
          type, 
          gateway, 
          extensions: discoveredAgentInfo?.agent_info?.home_path ? {
            memory_path: discoveredAgentInfo.agent_info.memory_path || '',
            skills_path: discoveredAgentInfo.agent_info.skills_path || '',
            honcho_api: 'http://localhost:8000',
            wiki_path: discoveredAgentInfo.agent_info.wiki_path || '',
            sync_interval: 5,
            decay_threshold: 0.2
          } : {}
        }
      })
    });
    
    if (res.ok) {
      hideAddAgentForm();
      loadSettingsData();
      showToast('✅ Agent 添加成功', 'success');
    } else {
      const errData = await res.json();
      showToast('添加失败: ' + (errData.error || '未知错误'), 'error');
    }
  } catch (e) {
    showToast('添加失败: ' + e.message, 'error');
  }
}

async function deleteAgent(id) {
  if (!confirm('确定要删除这个Agent吗？')) return;
  
  try {
    const res = await fetch('/api/agents/config', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ action: 'delete', agent_id: id })
    });
    if (res.ok) {
      loadSettingsData();
      showToast('✅ Agent 已删除', 'success');
    } else {
      showToast('删除失败', 'error');
    }
  } catch (e) {
    showToast('删除失败: ' + e.message, 'error');
  }
}

async function setDefaultAgent(id) {
  try {
    const res = await fetch('/api/agents/config', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ action: 'set_default', agent_id: id })
    });
    if (res.ok) {
      loadSettingsData();
      showToast('✅ 已设为当前Agent', 'success');
    } else {
      showToast('设置失败', 'error');
    }
  } catch (e) {
    showToast('设置失败: ' + e.message, 'error');
  }
}

async function saveAgentConfig(idx) {
  const fields = document.querySelectorAll(`.agent-field[data-agent="${idx}"]`);
  const agent = settingsAgentConfig.agents[idx];
  
  fields.forEach(f => {
    const field = f.dataset.field;
    const val = f.value;
    if (field === 'gateway') agent.gateway = val;
    else agent.extensions[field] = val;
  });
  
  try {
    const res = await fetch('/api/agents/config', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ action: 'update', agent: agent })
    });
    if (res.ok) {
      loadSettingsData();
      showToast('✅ 配置已保存', 'success');
    } else {
      showToast('保存失败', 'error');
    }
  } catch (e) {
    showToast('保存失败: ' + e.message, 'error');
  }
}

async function saveGlobalSettings() {
  const syncInterval = document.getElementById('globalSyncInterval').value;
  const decayThreshold = document.getElementById('globalDecayThreshold').value;
  
  try {
    const res = await fetch('/api/agents/config', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        action: 'update_global',
        sync_interval: parseInt(syncInterval),
        decay_threshold: parseFloat(decayThreshold)
      })
    });
    if (res.ok) {
      showToast('✅ 全局设置已保存', 'success');
    } else {
      showToast('保存失败', 'error');
    }
  } catch (e) {
    showToast('保存失败: ' + e.message, 'error');
  }
}

async function loadHealthData() {
  try {
    const [hRes, eRes, oRes] = await Promise.all([
      fetch('/api/meta/health'), fetch('/api/meta/entries?status=active'), fetch('/api/meta/operations?limit=20')
    ]);
    const health = await hRes.json(), entries = await eRes.json(), ops = await oRes.json();
    healthEntries = entries;
    healthFilteredEntries = [...entries];
    renderHealthCards(health);
    populateCategoryFilter();
    healthFilter();
    renderHealthOps(ops);
    // 渲染分类衰减总览
    if (typeof renderCategoryOverview === 'function') renderCategoryOverview();
    showToast('健康数据已加载', 'success');
  } catch(e) { console.error('Health load error', e); showToast('加载失败: ' + e.message, 'error'); }
}

function renderHealthCards(h) {
  const active = h.total_active || 0;
  const avgDecay = typeof h.avg_decay === 'number' ? Math.round(h.avg_decay * 100) : 0;
  const cards = [
    { icon:'📦', value:active, label:'活跃记忆', cls:'card-active' },
    { icon:'📉', value:avgDecay+'%', label:'平均强度', cls:'card-decay' },
    { icon:'💾', value:h.snapshots||0, label:'快照数', cls:'card-snap' }
  ];
  document.getElementById('insightCards').innerHTML = cards.map(c =>
    `<div class="health-card ${c.cls}"><div class="hc-icon">${c.icon}</div><div class="hc-value">${c.value}</div><div class="hc-label">${c.label}</div></div>`
  ).join('');
}

function populateCategoryFilter() {
  const cats = [...new Set(healthEntries.map(e => e.primary_cat).filter(Boolean))].sort();
  const sel = document.getElementById('healthCatFilter');
  sel.innerHTML = '<option value="">全部分类</option>' + cats.map(c => `<option value="${c}">${c}</option>`).join('');
}

function healthFilter() {
  const q = (document.getElementById('healthSearch')?.value || '').toLowerCase();
  const cat = document.getElementById('healthCatFilter')?.value || '';
  const status = document.getElementById('healthStatusFilter')?.value || '';
  healthFilteredEntries = healthEntries.filter(e => {
    if (q && !(extractPreview(e.content_preview)).toLowerCase().includes(q) && !(e.primary_cat||'').toLowerCase().includes(q) && !(e.secondary_cat||'').toLowerCase().includes(q)) return false;
    if (cat && e.primary_cat !== cat) return false;
    if (status === 'healthy' && e.decay_score <= 0.5) return false;
    if (status === 'fading' && (e.decay_score <= 0.2 || e.decay_score > 0.5)) return false;
    if (status === 'danger' && e.decay_score > 0.2) return false;
    if (status === 'pinned' && !e.pinned) return false;
    if (status === 'inactive' && e.status !== 'inactive') return false;
    return true;
  });
  renderHealthTable();
}

function renderHealthTable() {
  const sorted = [...healthFilteredEntries].sort((a, b) => {
    let va = a[healthSortKey], vb = b[healthSortKey];
    if (typeof va === 'string') va = va.toLowerCase();
    if (typeof vb === 'string') vb = vb.toLowerCase();
    let v = va > vb ? 1 : va < vb ? -1 : 0;
    return healthSortAsc ? v : -v;
  });
  const cols = [
    ['content_preview','内容预览'],['primary_cat','分类'],['importance','重要度'],
    ['decay_score','衰减分'],['access_count','访问次数'],['version','版本'],['pinned','固定'],['created_at','创建时间']
  ];
  document.getElementById('healthTHead').innerHTML = '<tr>' + cols.map(c =>
    `<th class="${healthSortKey===c[0]?'sorted':''}" onclick="healthSort('${c[0]}')">${c[1]} ${healthSortKey===c[0]?(healthSortAsc?'↑':'↓'):''}</th>`
  ).join('') + '</tr>';

  document.getElementById('healthEntryCount').textContent = `显示 ${sorted.length} / ${healthEntries.length} 条记忆`;

  document.getElementById('healthTBody').innerHTML = sorted.map(e => {
    const ds = e.decay_score || 0;
    const dcClass = ds > 0.5 ? 'green' : ds > 0.2 ? 'yellow' : 'red';
    const preview = extractPreview(e.content_preview).slice(0,50) + (extractPreview(e.content_preview).length>50?'…':'');
    const catLabel = [e.primary_cat, e.secondary_cat].filter(Boolean).join('/');
    const statusBadge = e.status === 'inactive' ? '<span class="status-badge inactive">历史</span>' : '';
    return `<tr>
      <td><div class="preview-text" title="${extractPreview(e.content_preview).replace(/"/g,'&quot;')}">${preview} ${statusBadge}</div></td>
      <td><span class="cat-tag">${catLabel||'未分类'}</span></td>
      <td><div class="imp-bar"><div class="imp-bar-inner" style="width:${(e.importance||0)*100}%"></div></div></td>
      <td><div class="decay-bar-wrap" onclick="showEntryDecayCurve('${e.id}')" style="cursor:pointer" title="点击查看衰减曲线"><div class="decay-bar"><div class="decay-bar-inner decay-${dcClass}" style="width:${Math.max(ds*100,5)}%"></div></div><span class="decay-pct ${dcClass}">${(ds*100).toFixed(0)}%</span></div></td>
      <td style="text-align:center">${e.access_count||0}</td>
      <td style="text-align:center;font-size:12px;color:#666">v${e.version||1}</td>
      <td><button class="pin-btn ${e.pinned?'pinned':''}" onclick="healthPin('${e.id}')">${e.pinned?'📌':'○'}</button></td>
      <td style="font-size:11px;color:#999">${(e.created_at||'').slice(0,10)}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="8" style="text-align:center;color:#ccc;padding:30px">暂无数据</td></tr>';
}

function healthSort(key) {
  if (healthSortKey === key) healthSortAsc = !healthSortAsc;
  else { healthSortKey = key; healthSortAsc = true; }
  renderHealthTable();
}

function renderHealthOps(ops) {
  const list = Array.isArray(ops) ? ops : [];
  document.getElementById('healthOps').innerHTML = list.length ? list.map(o => {
    const badge = o.auto_or_manual === 'auto' ? '<span class="ops-badge auto">自动</span>' : '<span class="ops-badge manual">手动</span>';
    return `<div class="health-ops-item">
      <span class="ops-time">🕐 ${(o.timestamp||'').slice(0,19).replace('T',' ')}</span>
      <span class="ops-action">${o.operation||o.action||''}</span>
      ${badge}
      <span class="ops-detail">${o.target_ids ? '目标: '+JSON.stringify(o.target_ids) : (o.target_id||'')}</span>
    </div>`;
  }).join('') : '<div style="color:#ccc;text-align:center;padding:20px">暂无操作记录</div>';
}

async function loadHealthSnapshots() {
  try {
    const res = await fetch('/api/meta/snapshots');
    const snaps = await res.json();
    const list = Array.isArray(snaps) ? snaps : [];
    document.getElementById('healthSnapList').innerHTML = list.length ? list.map(s =>
      `<div class="snap-item">
        <div class="snap-info">
          <span class="snap-time">💾 ${(s.timestamp||'').slice(0,19).replace('T',' ')}</span>
          <span class="snap-meta">触发: ${s.trigger||'unknown'} · 记忆: ${s.memory_size||'?'} · 用户: ${s.user_size||'?'}</span>
        </div>
        <button class="snap-restore-btn" onclick="healthRestoreSnapshot('${s.id}')">恢复此快照</button>
      </div>`
    ).join('') : '<div style="color:#ccc;text-align:center;padding:20px">暂无快照</div>';
  } catch(e) { console.error(e); }
}

async function healthCreateSnapshot() {
  try {
    await fetch('/api/meta/snapshot', {method:'POST'});
    showToast('快照创建成功', 'success');
    loadHealthSnapshots();
    loadHealthData();
  } catch(e) { showToast('创建失败', 'error'); }
}

async function healthRestoreSnapshot(id) {
  if (!confirm('确定要恢复此快照？当前数据将被覆盖。')) return;
  try {
    await fetch('/api/meta/snapshot/restore', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id})});
    showToast('快照恢复成功', 'success');
    loadHealthData();
  } catch(e) { showToast('恢复失败', 'error'); }
}

async function healthSync() {
  try { await fetch('/api/meta/sync',{method:'POST'}); showToast('同步完成','success'); loadHealthData(); } catch(e){ showToast('同步失败','error'); }
}
async function healthDecay() {
  try { await fetch('/api/meta/decay',{method:'POST'}); showToast('衰减重算完成','success'); loadHealthData(); } catch(e){ showToast('重算失败','error'); }
}
async function healthPin(id) {
  try { await fetch('/api/meta/pin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})}); loadHealthData(); } catch(e){ showToast('操作失败','error'); }
}

// ========== AI分析引擎 ==========

function analyzeSwitchTab(tab, btn) {
  document.querySelectorAll('.analyze-section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.analyze-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('analyzeSection' + tab.charAt(0).toUpperCase() + tab.slice(1)).classList.add('active');
  btn.classList.add('active');
}

async function loadAnalyzeData() {
  // 已废弃——分类衰减总览已替代分析模块
  // 数据现在由 renderCategoryOverview 直接从 healthEntries 计算
}

// ========== 巩固引擎 ==========

async function runConsolidateScan() {
  const results = document.getElementById('consolidateResults');
  const summary = document.getElementById('consolidateSummary');
  results.innerHTML = '<div class="cr-loading">🔍 正在扫描记忆...</div>';
  summary.innerHTML = '';
  try {
    const res = await fetch('/api/consolidate/scan');
    const data = await res.json();
    renderConsolidateSummary(data.summary);
    renderConsolidateResults(data);
    showToast('扫描完成', 'success');
  } catch(e) { results.innerHTML = '<div class="cr-loading">扫描失败: '+e.message+'</div>'; }
}

async function loadConsolidateDupes() {
  const results = document.getElementById('consolidateResults');
  results.innerHTML = '<div class="cr-loading">🔗 查找重复...</div>';
  try {
    const res = await fetch('/api/consolidate/duplicates');
    const dupes = await res.json();
    results.innerHTML = renderDuplicates(dupes);
  } catch(e) { results.innerHTML = '<div class="cr-loading">查找失败</div>'; }
}

async function loadConsolidateConflicts() {
  const results = document.getElementById('consolidateResults');
  results.innerHTML = '<div class="cr-loading">⚡ 检测冲突...</div>';
  try {
    const res = await fetch('/api/consolidate/conflicts');
    const conflicts = await res.json();
    results.innerHTML = renderConflicts(conflicts);
  } catch(e) { results.innerHTML = '<div class="cr-loading">检测失败</div>'; }
}

async function loadConsolidateDist() {
  const results = document.getElementById('consolidateResults');
  results.innerHTML = '<div class="cr-loading">📊 分析分布...</div>';
  try {
    const res = await fetch('/api/consolidate/distribution');
    const dist = await res.json();
    results.innerHTML = renderDistribution(dist);
  } catch(e) { results.innerHTML = '<div class="cr-loading">分析失败</div>'; }
}

function renderConsolidateSummary(s) {
  if (!s) return;
  const el = document.getElementById('consolidateSummary');
  const cls = s.health.includes('🟢') ? 'cs-healthy' : s.health.includes('🟡') ? 'cs-warning' : 'cs-danger';
  let html = `<span class="cs-card ${cls}">${s.health}</span>`;
  if (s.actions && s.actions.length) {
    html += s.actions.map(a => `<span class="cs-card cs-warning">${a}</span>`).join('');
  }
  el.innerHTML = html;
}

function renderConsolidateResults(data) {
  let html = '';
  if (data.duplicates && data.duplicates.length) html += renderDuplicates(data.duplicates);
  if (data.conflicts && data.conflicts.length) html += renderConflicts(data.conflicts);
  if (data.distribution) html += renderDistribution(data.distribution);
  if (!html) html = '<div class="cr-loading">✨ 记忆状态良好，暂无需要整理的内容</div>';
  document.getElementById('consolidateResults').innerHTML = html;
}

function renderDuplicates(dupes) {
  if (!dupes || !dupes.length) return '<div class="cr-section"><h4>🔗 重复检测</h4><div class="cr-loading">未发现重复</div></div>';
  return `<div class="cr-section"><h4>🔗 疑似重复 (${dupes.length} 对)</h4>` +
    dupes.map(d => {
      const simCls = d.similarity >= 0.8 ? 'high' : 'medium';
      const e1 = d.entries?.[0] || {}, e2 = d.entries?.[1] || {};
      return `<div class="cr-item">
        <div class="cr-pair">
          <div class="cr-entry"><div class="cr-id">${d.pair[0]}</div>${extractPreview(e1.content_preview).slice(0,80)}</div>
          <div class="cr-entry"><div class="cr-id">${d.pair[1]}</div>${extractPreview(e2.content_preview).slice(0,80)}</div>
        </div>
        <span class="cr-sim ${simCls}">相似度 ${(d.similarity*100).toFixed(0)}%</span>
        <div class="cr-suggestion">💡 ${d.suggestion}</div>
        <div class="cr-actions">
          <button class="cr-action-btn primary" onclick="llmMerge('${d.pair[0]}','${d.pair[1]}')">🤖 AI合并建议</button>
        </div>
      </div>`;
    }).join('') + '</div>';
}

function renderConflicts(conflicts) {
  if (!conflicts || !conflicts.length) return '<div class="cr-section"><h4>⚡ 冲突检测</h4><div class="cr-loading">未发现冲突</div></div>';
  return `<div class="cr-section"><h4>⚡ 可能冲突 (${conflicts.length} 对)</h4>` +
    conflicts.map(c => {
      const e1 = c.entries?.[0] || {}, e2 = c.entries?.[1] || {};
      return `<div class="cr-item">
        <div class="cr-pair">
          <div class="cr-entry"><div class="cr-id">${c.pair[0]}</div>${extractPreview(e1.content_preview).slice(0,80)}</div>
          <div class="cr-entry"><div class="cr-id">${c.pair[1]}</div>${extractPreview(e2.content_preview).slice(0,80)}</div>
        </div>
        <div class="cr-suggestion">💡 ${c.suggestion}</div>
      </div>`;
    }).join('') + '</div>';
}

function renderDistribution(dist) {
  if (!dist || !dist.categories) return '';
  const cats = dist.categories;
  const maxPct = Math.max(...Object.values(cats).map(c => c.percentage), 1);
  let html = `<div class="cr-section"><h4>📊 记忆分布 (共 ${dist.total} 条)</h4><div class="cr-dist-grid">`;
  for (const [name, info] of Object.entries(cats).sort((a,b) => b[1].count - a[1].count)) {
    html += `<div class="cr-dist-card">
      <div class="cat-name">${name}</div>
      <div class="cat-stats">${info.count} 条 · ${info.percentage}% · 📌${info.pinned} · 衰减 ${(info.avg_decay*100).toFixed(0)}%</div>
      <div class="cat-bar"><div class="cat-bar-inner" style="width:${info.percentage/maxPct*100}%"></div></div>
    </div>`;
  }
  html += '</div>';
  if (dist.warnings && dist.warnings.length) {
    html += '<ul class="cr-warning-list">' + dist.warnings.map(w => `<li>${w}</li>`).join('') + '</ul>';
  }
  return html + '</div>';
}

async function llmMerge(id1, id2) {
  const results = document.getElementById('consolidateResults');
  const orig = results.innerHTML;
  showToast('正在请求 AI 合并建议...', 'info');
  try {
    const res = await fetch('/api/consolidate/llm', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({entry_ids: [id1, id2], task: 'merge'})
    });
    const data = await res.json();
    if (data.error) { showToast('AI 合并失败: ' + data.error, 'error'); return; }
    const merged = data.merged || data.compressed || JSON.stringify(data);
    const reasoning = data.reasoning || '';
    alert(`🤖 AI 合并建议:\n\n${merged}\n\n理由: ${reasoning}`);
  } catch(e) { showToast('请求失败: ' + e.message, 'error'); }
}

// ==================== Skill 动态加载功能 ====================

let currentSkillCategory = 'all';
let skillsCache = null;
let skillPanelVisible = false;

// 切换 skill 面板显示
function toggleSkillPanel() {
  const panel = document.getElementById('skillPanel');
  const arrow = document.getElementById('skillArrow');
  skillPanelVisible = !skillPanelVisible;
  
  if (skillPanelVisible) {
    if (arrow) arrow.textContent = '▼';
    // 加载 skills
    if (!skillsCache) {
      loadSkills();
    } else {
      panel.style.display = 'flex';
    }
  } else {
    if (arrow) arrow.textContent = '▶';
    panel.style.display = 'none';
  }
}

// 从 graphData 中提取 skills
function extractSkills() {
  if (!graphData || !graphData.nodes) return [];
  
  const skillNodes = graphData.nodes.filter(n => n.category === 'skill');
  
  return skillNodes.map(skill => {
    const name = skill.label || skill.name || skill.id;
    const skillId = skill.id;
    return {
      id: skillId,
      name: name,
      // 使用 secondary 字段作为分类，如果没有则使用 primary
      category: skill.secondary || skill.primary || '未分类',
      description: skill.description || getSkillDescription(name),
      complexity: skill.complexity || 'simple',
      content: skill.content || skill.description || ''
    };
  });
}

// 获取技能的描述
function getSkillDescription(skillName) {
  const descriptions = {
    'apple-reminders': '管理 Apple 提醒事项',
    'imessage': '发送和接收 iMessage/SMS 消息',
    'findmy': '追踪 Apple 设备和 AirTags',
    'apple-notes': '管理 Apple Notes 笔记',
    'llama-cpu': '在 CPU 上运行 LLM 推理',
    'gguf-quantization': 'GGUF 量化工具',
    'huggingface-hub': 'Hugging Face CLI',
    'jupyter-live-kernel': 'Jupyter 实时内核',
    'arxiv': 'arXiv 论文搜索',
    'linear': 'Linear 问题管理',
    'notion': 'Notion API',
    'powerpoint': 'PPT 生成',
    'google-workspace': 'Google 工作区',
    'excalidraw': '手绘风格图表',
    'ascii-art': 'ASCII 艺术生成',
    'pixel-art': '像素艺术转换',
    'manim-video': '数学动画生成',
    'suno-music': 'AI 音乐生成',
    'wechat-article-publish': '微信公众号文章发布',
    'github-pr-workflow': 'GitHub PR 工作流',
    'github-issues': 'GitHub Issues 管理',
    'codebase-inspection': '代码库检查分析'
  };
  return descriptions[skillName] || '查看详情获取更多信息';
}

// 获取所有分类
function getSkillCategories(skills) {
  const categories = new Set(['all']);
  skills.forEach(s => categories.add(s.category));
  return Array.from(categories);
}

// 加载并显示 skill 面板
function loadSkills() {
  const skills = extractSkills();
  skillsCache = skills;
  renderSkillCategories(skills);
  renderSkillList(skills);
  
  const panel = document.getElementById('skillPanel');
  if (panel) {
    panel.style.display = 'flex';
  }
}

// 刷新 skills
function refreshSkills() {
  showToast('正在加载技能库...', 'info');
  // 重新从服务器获取数据
  fetch('/api/data?t=' + Date.now())
    .then(res => res.json())
    .then(data => {
      if (data.nodes) {
        graphData = data;
        loadSkills();
        showToast('技能库已刷新', 'success');
      }
    })
    .catch(err => {
      console.error('刷新技能失败:', err);
      showToast('刷新失败', 'error');
    });
}

// 渲染分类标签
function renderSkillCategories(skills) {
  const categories = getSkillCategories(skills);
  const container = document.getElementById('skillCategoryTabs');
  
  container.innerHTML = categories.map(cat => `
    <div class="skill-category-tab ${cat === currentSkillCategory ? 'active' : ''}" 
         onclick="filterSkills('${cat}')">
      ${cat === 'all' ? '全部' : cat}
    </div>
  `).join('');
}

// 渲染 skill 列表
function renderSkillList(skills) {
  const filtered = currentSkillCategory === 'all' 
    ? skills 
    : skills.filter(s => s.category === currentSkillCategory);
  
  const container = document.getElementById('skillList');
  
  if (!filtered.length) {
    container.innerHTML = '<div style="color:#888;font-size:11px;text-align:center;padding:20px;">暂无技能</div>';
    return;
  }
  
  container.innerHTML = filtered.map(skill => `
    <div class="skill-item" onclick="showSkillDetail('${skill.id}')">
      <div class="skill-icon">⚡</div>
      <div class="skill-info">
        <div class="skill-name">${skill.name}</div>
        <div class="skill-desc">${skill.description}</div>
      </div>
      <div class="skill-complexity">${skill.complexity === 'simple' ? '简单' : skill.complexity === 'medium' ? '中等' : '复杂'}</div>
    </div>
  `).join('');
}

// 过滤 skills
function filterSkills(category) {
  currentSkillCategory = category;
  if (skillsCache) {
    renderSkillCategories(skillsCache);
    renderSkillList(skillsCache);
  }
}

// 显示 skill 详情弹窗
function showSkillDetail(skillId) {
  const skill = skillsCache?.find(s => s.id === skillId);
  if (!skill) return;
  
  document.getElementById('skillDetailName').textContent = skill.name;
  
  document.getElementById('skillDetailMeta').innerHTML = `
    <span>📁 ${skill.category}</span>
    <span>📊 ${skill.complexity === 'simple' ? '简单' : skill.complexity === 'medium' ? '中等' : '复杂'}</span>
  `;
  
  // 技能内容（可以从 skill.content 或其他地方获取）
  let content = skill.content;
  if (!content) {
    // 尝试从 graphData 中获取完整内容
    const node = graphData?.nodes?.find(n => (n.id || n.name) === skillId);
    content = node?.content || node?.description || '暂无详细描述';
  }
  
  document.getElementById('skillDetailBody').innerHTML = `
    <h3>技能描述</h3>
    <p>${skill.description}</p>
    <h3>详细内容</h3>
    <pre>${content}</pre>
  `;
  
  document.getElementById('skillDetailModal').classList.remove('hidden');
}

// 关闭 skill 详情弹窗
function closeSkillDetail() {
  document.getElementById('skillDetailModal').classList.add('hidden');
}

// 点击弹窗外部关闭
document.addEventListener('DOMContentLoaded', function() {
  const modal = document.getElementById('skillDetailModal');
  if (modal) {
    modal.addEventListener('click', function(e) {
      if (e.target === modal) {
        closeSkillDetail();
      }
    });
  }
});

// --- 自动轮询（检测记忆源文件变化） ---
const POLL_INTERVAL_MS = 15000;
let pollingInterval = null;
let lastPollHash = null;
let pollTimerDisplay = Date.now();

function calcDataHash(data) {
  // 轻量 hash：基于节点数和 lastUpdated
  const nodes = (data.nodes || []).length;
  const links = (data.links || []).length;
  const updated = data.lastUpdated || '';
  return nodes + '|' + links + '|' + updated;
}

// 更新状态栏显示
function updatePollStatus(message, isOk) {
  const el = document.getElementById('pollStatus');
  if (!el) return;
  el.textContent = message;
  el.className = 'poll-status' + (isOk ? ' poll-ok' : ' poll-warn');
}

function updatePollTime() {
  const el = document.getElementById('pollTime');
  if (!el) return;
  if (!pollTimerDisplay) {
    el.textContent = '--';
    return;
  }
  const seconds = Math.floor((Date.now() - pollTimerDisplay) / 1000);
  if (seconds < 60) {
    el.textContent = seconds + '秒前';
  } else {
    el.textContent = Math.floor(seconds / 60) + '分钟前';
  }
}

async function pollCheck() {
  try {
    // 轮询 /api/poll 获取源文件 mtime hash
    const res = await fetch('/api/poll?t=' + Date.now());
    const pollData = await res.json();
    const hash = pollData.hash;
    
    if (!lastPollHash) {
      // 首次轮询，记录 hash
      lastPollHash = hash;
      pollTimerDisplay = Date.now();
      updatePollStatus('轮询中', true);
      return;
    }
    
    if (hash !== lastPollHash) {
      // 检测到源文件变化！
      updatePollStatus('🔔 检测到变化，自动刷新...', true);
      lastPollHash = hash;
      pollTimerDisplay = Date.now();
      
      // 调用后端刷新接口重建图谱
      try {
        const refreshRes = await fetch('/api/refresh', { method: 'POST' });
        const refreshJson = await refreshRes.json();
        if (refreshJson.status === 'ok') {
          await loadData();
          loadIQ();
          showToast(`🔄 记忆已自动刷新 — ${refreshJson.nodes}个节点`, 'success');
        }
      } catch (e) {
        // refresh 失败时，至少用新数据更新视图
        graphData = data;
        timelinePoints = buildTimelinePoints(graphData);
        applyTimepoint(timelinePoints.length - 1);
        showToast('🔄 视图已更新', 'info');
      }
      
      updatePollStatus('轮询中', true);
    } else {
      // 无变化，更新时间
      pollTimerDisplay = Date.now();
      updatePollStatus('轮询中', true);
    }
  } catch (e) {
    updatePollStatus('⚠️ 连接异常', false);
  }
}

// 启动轮询
function startPolling() {
  if (pollingInterval) clearInterval(pollingInterval);
  // 先做一次初始化
  pollCheck();
  // 定时轮询
  pollingInterval = setInterval(pollCheck, POLL_INTERVAL_MS);
  // 更新时间显示（每秒更新）
  setInterval(updatePollTime, 1000);
}

// ========== 记忆洞察模块（合并：生命周期+管理+DNA） ==========
let currentInsightTab = 'lifecycle';

function insightSwitchTab(tab, btnEl) {
  currentInsightTab = tab;
  // 更新按钮样式
  document.querySelectorAll('.insight-tab').forEach(t => t.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');
  // 切换section显隐
  const tabMap = {
    'lifecycle': 'insightSectionLifecycle',
    'manage': 'insightSectionManage'
  };
  document.querySelectorAll('.insight-section').forEach(s => s.classList.remove('active'));
  const targetId = tabMap[tab];
  if (targetId) document.getElementById(targetId).classList.add('active');
  
  // 触发数据加载
  if (tab === 'lifecycle') {
    loadHealthData();
  }
  if (tab === 'manage') {
    loadHealthData();
    renderImportArea();
    loadMemoryStats();
    renderSyncArea();
    loadHealthSnapshots();
  }
}

// 洞察面板操作下拉菜单
function insightActionMenu() {
  // 移除已存在的下拉菜单
  const existing = document.querySelector('.insight-action-dropdown');
  if (existing) { existing.remove(); return; }

  const toolbar = document.querySelector('.insight-toolbar');
  if (!toolbar) return;

  const dropdown = document.createElement('div');
  dropdown.className = 'insight-action-dropdown';
  dropdown.innerHTML = `
    <button onclick="healthSync(); insightActionMenuClose()">🔄 同步元数据</button>
    <button onclick="healthDecay(); insightActionMenuClose()">📉 重算衰减</button>
    <button onclick="loadHealthData(); insightActionMenuClose()">♻️ 刷新数据</button>
  `;
  toolbar.appendChild(dropdown);

  // 点击外部关闭
  setTimeout(() => {
    document.addEventListener('click', insightActionMenuCloseOnce, { once: true });
  }, 10);
}

function insightActionMenuClose() {
  const dropdown = document.querySelector('.insight-action-dropdown');
  if (dropdown) dropdown.remove();
}

function insightActionMenuCloseOnce(e) {
  const dropdown = document.querySelector('.insight-action-dropdown');
  if (dropdown && !dropdown.contains(e.target)) dropdown.remove();
}

// ========== 分类衰减总览 + 钻入详情 ==========

// 从content_preview提取人类可读文字
function extractPreview(raw) {
  if (!raw) return '—';
  // YAML格式: "--- name: xxx description: xxx ..."
  if (raw.startsWith('---') || raw.indexOf('name:') < 20 && raw.indexOf('description:') > -1) {
    const descMatch = raw.match(/description:\s*"([^"]*)"|description:\s*'([^']*)'|description:\s*(.+?)(?:\n|version:|tags:|trigger:|author:|$)/);
    if (descMatch) {
      const desc = (descMatch[1] || descMatch[2] || descMatch[3] || '').trim();
      return desc.length > 0 ? desc : raw.replace(/^---\s*/, '').replace(/name:\s*\S+\s*/, '').trim().substring(0, 80);
    }
    const nameMatch = raw.match(/name:\s*(\S+)/);
    if (nameMatch) return nameMatch[1];
  }
  // 普通文本直接截断
  return raw;
}

function renderCategoryOverview() {
  if (!healthEntries || healthEntries.length === 0) {
    document.getElementById('categoryOverviewContent').innerHTML = '<div style="color:#999;text-align:center;padding:40px">请先加载健康数据</div>';
    return;
  }

  // 按分类聚合
  const catData = {};
  healthEntries.forEach(function(e) {
    const cat = e.primary_cat || 'unknown';
    const ds = e.decay_score || 0;
    const imp = e.importance || 0;
    const rc = e.recall_count || 0;
    if (!catData[cat]) catData[cat] = { count: 0, decays: [], importances: [], entries: [], totalRecall: 0 };
    catData[cat].count++;
    catData[cat].decays.push(ds);
    catData[cat].importances.push(imp);
    catData[cat].entries.push(e);
    catData[cat].totalRecall += rc;
  });

  const catList = [];
  for (const cat in catData) {
    const avgDecay = catData[cat].decays.reduce(function(a,b){return a+b;},0) / catData[cat].decays.length;
    const avgImp = catData[cat].importances.reduce(function(a,b){return a+b;},0) / catData[cat].importances.length;
    const minDecay = Math.min.apply(null, catData[cat].decays);
    const maxDecay = Math.max.apply(null, catData[cat].decays);
    const healthyCount = catData[cat].decays.filter(function(d){return d > 0.5;}).length;
    const fadingCount = catData[cat].decays.filter(function(d){return d > 0.2 && d <= 0.5;}).length;
    const dangerCount = catData[cat].decays.filter(function(d){return d <= 0.2;}).length;
    catList.push({
      cat: cat,
      count: catData[cat].count,
      avgDecay: avgDecay,
      avgImp: avgImp,
      minDecay: minDecay,
      maxDecay: maxDecay,
      healthyCount: healthyCount,
      fadingCount: fadingCount,
      dangerCount: dangerCount,
      totalRecall: catData[cat].totalRecall,
      entries: catData[cat].entries
    });
  }
  // 按平均衰减排序（强的在前）
  catList.sort(function(a,b){return b.avgDecay - a.avgDecay;});

  const color = DECAY_COLORS || {};
  const names = DECAY_NAMES || {};

  // 整体统计
  const totalEntries = healthEntries.length;
  const totalAvgDecay = healthEntries.reduce(function(a,e){return a + (e.decay_score||0);},0) / totalEntries;
  const totalRecallCount = healthEntries.reduce(function(a,e){return a + (e.recall_count||0);},0);

  let html = '';

  // 总体摘要 — 曲线图
  const overallPct = Math.round(totalAvgDecay * 100);
  const overallColor = overallPct > 50 ? '#00b894' : overallPct > 20 ? '#f0932b' : '#e74c3c';
  html += '<div class="category-overall-bar">';
  html += '<div class="category-overall-header">';
  html += '<div class="category-overall-label">整体记忆强度 <span style="font-size:20px;font-weight:700;color:' + overallColor + '">' + overallPct + '%</span></div>';
  html += '<div class="category-overall-info">' + totalEntries + ' 条活跃记忆 · <span style="color:#00b894">↑' + totalRecallCount + ' recall</span></div>';
  html += '</div>';
  html += '<div id="overallDecayChart" class="category-overall-chart" data-current="' + overallPct + '" data-color="' + overallColor + '"></div>';
  html += '</div>';

  // 分类卡片网格
  html += '<div class="category-grid">';
  catList.forEach(function(c) {
    const cColor = (color[c.cat]) || '#636e72';
    const cName = (names[c.cat]) || c.cat;
    const pct = Math.round(c.avgDecay * 100);
    const statusLabel = pct > 50 ? '强' : pct > 20 ? '中' : '弱';
    const statusColor = pct > 50 ? '#00b894' : pct > 20 ? '#f0932b' : '#e74c3c';

    html += '<div class="category-card" onclick="showCategoryDetail(\'' + c.cat + '\')" style="border-left:4px solid ' + cColor + '">';
    html += '<div class="category-card-header">';
    html += '<span class="category-card-name" style="color:' + cColor + '">' + cName + '</span>';
    html += '<span class="category-card-count">' + c.count + '条</span>';
    if (c.totalRecall > 0) {
      html += '<span class="category-card-recall" style="color:#00b894;font-size:11px;margin-left:4px">↑' + c.totalRecall + 'recall</span>';
    }
    html += '</div>';
    html += '<div class="category-card-meter">';
    html += '<div class="category-card-fill" style="width:' + pct + '%;background:' + statusColor + '"></div>';
    html += '<span class="category-card-pct">' + pct + '%</span>';
    html += '</div>';
    // 状态分布条（健康/褪色/危险）
    if (c.count > 1) {
      const hPct = Math.round(c.healthyCount / c.count * 100);
      const fPct = Math.round(c.fadingCount / c.count * 100);
      const dPct = Math.round(c.dangerCount / c.count * 100);
      html += '<div class="category-card-dist">';
      if (c.healthyCount > 0) html += '<div style="flex:' + hPct + ';background:#00b894;min-width:4px" title="强 ' + c.healthyCount + '条"></div>';
      if (c.fadingCount > 0) html += '<div style="flex:' + fPct + ';background:#f0932b;min-width:4px" title="中 ' + c.fadingCount + '条"></div>';
      if (c.dangerCount > 0) html += '<div style="flex:' + dPct + ';background:#e74c3c;min-width:4px" title="弱 ' + c.dangerCount + '条"></div>';
      html += '</div>';
    }
    html += '<div class="category-card-status" style="color:' + statusColor + '">' + statusLabel + '</div>';
    html += '</div>';
  });
  html += '</div>';

  document.getElementById('categoryOverviewContent').innerHTML = html;
  // 显示总览层，隐藏详情层
  document.getElementById('categoryOverviewPanel').style.display = 'block';
  document.getElementById('categoryDetailPanel').style.display = 'none';
  // 异步加载趋势数据绘制曲线图
  _loadOverallDecayCurve();
}

async function _loadOverallDecayCurve() {
  const chartEl = document.getElementById('overallDecayChart');
  if (!chartEl) return;
  try {
    const res = await fetch('/api/decay-trend');
    const trend = await res.json();
    if (!Array.isArray(trend) || trend.length === 0) return;
    const W = chartEl.offsetWidth || 280;
    const H = chartEl.offsetHeight || 100;
    const leftPad = 40, rightPad = 12, topPad = 10, bottomPad = 20;
    const plotW = W - leftPad - rightPad, plotH = H - topPad - bottomPad;
    const n = trend.length;
    // Dynamic Y range — auto-scale to data with 10% padding
    const vals = trend.map(function(d){ return d.avg_decay; });
    var minD = Math.min.apply(null, vals);
    var maxD = Math.max.apply(null, vals);
    var rangePad = (maxD - minD) * 0.15 || 0.05;
    minD = Math.max(0, minD - rangePad);
    maxD = Math.min(1, maxD + rangePad);
    // If range too small (flat data), expand to show meaningful scale
    if (maxD - minD < 0.1) {
      var center = (maxD + minD) / 2;
      minD = Math.max(0, center - 0.15);
      maxD = Math.min(1, center + 0.15);
    }
    // Map data to points
    const pts = trend.map(function(d, i) {
      const x = leftPad + (i / (n - 1 || 1)) * plotW;
      const y = topPad + plotH - ((d.avg_decay - minD) / (maxD - minD || 0.01)) * plotH;
      return [x, y];
    });
    // Build path — use smooth curve if >=4 points, polyline if fewer
    var pathD = '';
    if (n === 1) {
      pathD = 'M' + pts[0][0] + ',' + pts[0][1];
    } else if (n <= 3) {
      // Straight polyline for few points
      pathD = 'M' + pts[0][0] + ',' + pts[0][1];
      for (var i = 1; i < pts.length; i++) {
        pathD += ' L' + pts[i][0] + ',' + pts[i][1];
      }
    } else {
      // Catmull-Rom smooth curve
      pathD = 'M' + pts[0][0] + ',' + pts[0][1];
      for (var i = 0; i < pts.length - 1; i++) {
        var p0 = pts[Math.max(i - 1, 0)];
        var p1 = pts[i];
        var p2 = pts[i + 1];
        var p3 = pts[Math.min(i + 2, pts.length - 1)];
        var cp1x = p1[0] + (p2[0] - p0[0]) / 6;
        var cp1y = p1[1] + (p2[1] - p0[1]) / 6;
        var cp2x = p2[0] - (p3[0] - p1[0]) / 6;
        var cp2y = p2[1] - (p3[1] - p1[1]) / 6;
        pathD += ' C' + cp1x + ',' + cp1y + ' ' + cp2x + ',' + cp2y + ' ' + p2[0] + ',' + p2[1];
      }
    }
    var curveColor = chartEl.dataset.color || '#00b894';
    var svg = '<svg width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '" xmlns="http://www.w3.org/2000/svg">';
    // Y-axis line (left border)
    svg += '<line x1="' + leftPad + '" y1="' + topPad + '" x2="' + leftPad + '" y2="' + (topPad + plotH) + '" stroke="#ccc" stroke-width="1"/>';
    // X-axis line (bottom border)
    svg += '<line x1="' + leftPad + '" y1="' + (topPad + plotH) + '" x2="' + (leftPad + plotW) + '" y2="' + (topPad + plotH) + '" stroke="#ccc" stroke-width="1"/>';
    // Y grid lines + labels (auto-scale to data range)
    var ySteps = 4;
    for (var s = 0; s <= ySteps; s++) {
      var yVal = minD + (maxD - minD) * s / ySteps;
      var yy = topPad + plotH * (1 - s / ySteps);
      svg += '<line x1="' + leftPad + '" y1="' + yy + '" x2="' + (leftPad + plotW) + '" y2="' + yy + '" stroke="#e8e8e8" stroke-width="0.5" stroke-dasharray="3,3"/>';
      svg += '<text x="' + (leftPad - 4) + '" y="' + (yy + 3) + '" font-size="10" fill="#888" text-anchor="end">' + Math.round(yVal * 100) + '%</text>';
    }
    // NO area fill — pure line chart like stock ticker
    // Thin shadow line below curve for depth
    svg += '<path d="' + pathD + '" fill="none" stroke="' + curveColor + '" stroke-width="1" opacity="0.2" transform="translate(0,2)"/>';
    // Main curve stroke — thicker, crisp
    svg += '<path d="' + pathD + '" fill="none" stroke="' + curveColor + '" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>';
    // Vertical dashed lines from each data point down to X-axis
    pts.forEach(function(pt, idx) {
      svg += '<line x1="' + pt[0] + '" y1="' + pt[1] + '" x2="' + pt[0] + '" y2="' + (topPad + plotH) + '" stroke="' + curveColor + '" stroke-width="0.5" stroke-dasharray="2,3" opacity="0.3"/>';
    });
    // Data point dots — outer circle + white inner ring (clearly NOT a bar)
    pts.forEach(function(pt, idx) {
      var r = idx === pts.length - 1 ? 5 : 4;
      // Outer filled circle
      svg += '<circle cx="' + pt[0] + '" cy="' + pt[1] + '" r="' + r + '" fill="' + curveColor + '"/>';
      // White inner ring to make it a "data node" look
      svg += '<circle cx="' + pt[0] + '" cy="' + pt[1] + '" r="' + (r - 1.5) + '" fill="white"/>';
      // Tiny center dot
      svg += '<circle cx="' + pt[0] + '" cy="' + pt[1] + '" r="1" fill="' + curveColor + '"/>';
      // Value label above each point
      var pctVal = Math.round(trend[idx].avg_decay * 100);
      svg += '<text x="' + pt[0] + '" y="' + (pt[1] - 12) + '" font-size="11" fill="' + curveColor + '" text-anchor="middle" font-weight="600">' + pctVal + '%</text>';
    });
    // Current value pulse ring on last point
    var lastPt = pts[pts.length - 1];
    svg += '<circle cx="' + lastPt[0] + '" cy="' + lastPt[1] + '" r="9" fill="' + curveColor + '" opacity="0.12"/>';
    // X-axis date labels
    var firstDate = trend[0].day.slice(5);
    var lastDate = trend[trend.length - 1].day.slice(5);
    svg += '<text x="' + leftPad + '" y="' + (H - 2) + '" font-size="11" fill="#666">' + firstDate + '</text>';
    svg += '<text x="' + (leftPad + plotW) + '" y="' + (H - 2) + '" font-size="11" fill="#666" text-anchor="end">' + lastDate + '</text>';
    svg += '</svg>';
    chartEl.innerHTML = svg;
  } catch(e) { console.error('Decay trend load error', e); }
}

function showCategoryDetail(cat) {
  if (!healthEntries) return;
  const entries = healthEntries.filter(function(e){return (e.primary_cat || 'unknown') === cat;});
  if (entries.length === 0) return;

  const color = (DECAY_COLORS && DECAY_COLORS[cat]) || '#636e72';
  const name = (DECAY_NAMES && DECAY_NAMES[cat]) || cat;

  // 统计
  const decays = entries.map(function(e){return e.decay_score || 0;});
  const avgDecay = decays.reduce(function(a,b){return a+b;},0) / decays.length;
  const avgImp = entries.map(function(e){return e.importance||0;}).reduce(function(a,b){return a+b;},0) / entries.length;
  const minD = Math.min.apply(null, decays);
  const maxD = Math.max.apply(null, decays);
  const healthy = decays.filter(function(d){return d > 0.5;}).length;
  const fading = decays.filter(function(d){return d > 0.2 && d <= 0.5;}).length;
  const danger = decays.filter(function(d){return d <= 0.2;}).length;

  // 标题
  document.getElementById('categoryDetailTitle').innerHTML = '<span style="color:' + color + '">' + name + '</span> · 衰减详情';

  // 统计卡片
  const statsHtml = [
    {label:'平均强度', value:Math.round(avgDecay*100)+'%', color: avgDecay>0.5?'#00b894':avgDecay>0.2?'#f0932b':'#e74c3c'},
    {label:'最高强度', value:Math.round(maxD*100)+'%', color:'#00b894'},
    {label:'最低强度', value:Math.round(minD*100)+'%', color:'#e74c3c'},
    {label:'条目数', value:entries.length+'条', color:color},
    {label:'强(>50%)', value:healthy+'条', color:'#00b894'},
    {label:'中(20-50%)', value:fading+'条', color:'#f0932b'},
    {label:'弱(<20%)', value:danger+'条', color:'#e74c3c'}
  ].map(function(s) {
    return '<div class="detail-stat-card"><div class="detail-stat-value" style="color:' + s.color + '">' + s.value + '</div><div class="detail-stat-label">' + s.label + '</div></div>';
  }).join('');
  document.getElementById('categoryDetailStats').innerHTML = '<div class="detail-stats-row">' + statsHtml + '</div>';

  // 条目列表
  const sorted = entries.sort(function(a,b){return (b.decay_score||0) - (a.decay_score||0);});
  let listHtml = '<div class="detail-entries-list">';
  sorted.forEach(function(e) {
    const ds = e.decay_score || 0;
    const pct = Math.round(ds * 100);
    const barColor = ds > 0.5 ? '#00b894' : ds > 0.2 ? '#f0932b' : '#e74c3c';
    const preview = extractPreview(e.content_preview).substring(0, 60) + (extractPreview(e.content_preview).length > 60 ? '…' : '');
    const impPct = Math.round((e.importance || 0) * 100);
    const version = e.version || 1;
    listHtml += '<div class="detail-entry-row" onclick="showEntryDecayCurve(\'' + e.id + '\')" style="cursor:pointer">';
    listHtml += '<div class="detail-entry-bar"><div class="detail-entry-fill" style="width:' + pct + '%;background:' + barColor + '"></div><span class="detail-entry-pct">' + pct + '%</span></div>';
    listHtml += '<div class="detail-entry-preview">' + preview + '</div>';
    listHtml += '<div class="detail-entry-meta">重要度 ' + impPct + '% · v' + version + '</div>';
    listHtml += '</div>';
  });
  listHtml += '</div>';
  document.getElementById('categoryDetailEntries').innerHTML = listHtml;

  // 显示详情层，隐藏总览层
  document.getElementById('categoryOverviewPanel').style.display = 'none';
  document.getElementById('categoryDetailPanel').style.display = 'block';
}

function showCategoryOverview() {
  document.getElementById('categoryOverviewPanel').style.display = 'block';
  document.getElementById('categoryDetailPanel').style.display = 'none';
}

// 洞察面板section折叠/展开
function toggleInsightSection(h3El) {
  const section = h3El.parentElement;
  const toggle = h3El.querySelector('.section-toggle');
  const isCollapsed = section.classList.contains('collapsed-section');
  if (isCollapsed) {
    section.classList.remove('collapsed-section');
    if (toggle) toggle.textContent = '▼';
  } else {
    section.classList.add('collapsed-section');
    if (toggle) toggle.textContent = '▶';
  }
}

