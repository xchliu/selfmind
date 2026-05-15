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

// ===== Tab 1: 文档导入 =====
function renderImportTab() {
  const area = document.getElementById('memoryContentArea');
  let html = `
    <div class="memory-input-group">
      <input type="text" id="memDocDir" placeholder="输入文档目录路径，如 /path/to/docs" value="">
      <button class="memory-btn memory-btn-primary" onclick="startAutoImport()" ${autoImporting ? 'disabled' : ''}>
        ${autoImporting ? '⏳ 导入中...' : '🚀 一键导入'}
      </button>
      <button class="memory-btn memory-btn-secondary" onclick="scanDocuments()" ${memoryScanning || autoImporting ? 'disabled' : ''} title="手动扫描并选择文件">
        ${memoryScanning ? '⏳' : '🔍'}
      </button>
    </div>`;

  // Auto import progress
  if (autoImporting && autoImportProgress) {
    const p = autoImportProgress;
    const pct = p.total > 0 ? Math.round((p.current / p.total) * 100) : 0;
    html += `<div class="auto-import-progress">
      <div class="auto-import-header">
        <span class="auto-import-status">${p.phase || '处理中...'}</span>
        <span class="auto-import-counter">${p.current || 0}/${p.total || 0} 文件</span>
      </div>
      <div class="auto-import-bar-wrap">
        <div class="auto-import-bar" style="width:${pct}%"></div>
      </div>
      <div class="auto-import-file">${p.file ? `📄 ${escapeHtml(p.file)}` : ''}</div>
      <div class="auto-import-extracted">已提取 <strong>${p.totalExtracted || 0}</strong> 条记忆</div>
      ${p.log && p.log.length > 0 ? `<div class="auto-import-log">${p.log.map(l => `<div class="auto-import-log-line ${l.type}">${escapeHtml(l.text)}</div>`).join('')}</div>` : ''}
      <button class="memory-btn memory-btn-danger" onclick="stopAutoImport()" style="margin-top:8px">
        ⏹ 停止导入
      </button>
    </div>`;
  } else if (autoImportProgress && autoImportProgress.done) {
    const p = autoImportProgress;
    html += `<div class="auto-import-result">
      <div class="auto-import-result-icon">✅</div>
      <div class="auto-import-result-text">
        导入完成！共处理 <strong>${p.processed || 0}</strong> 个文件，
        提取 <strong>${p.totalExtracted || 0}</strong> 条记忆
        ${p.skipped ? `，跳过 ${p.skipped} 个` : ''}
      </div>
      <div class="auto-import-result-actions">
        <button class="memory-btn memory-btn-primary" onclick="switchMemoryTab('list')">📋 查看记忆</button>
        <button class="memory-btn memory-btn-secondary" onclick="autoImportProgress=null;renderImportTab()">↩ 重新导入</button>
      </div>
    </div>`;
  } else if (memoryScanning) {
    html += `<div class="memory-progress">
      <div class="memory-progress-spinner"></div>
      <div class="memory-progress-text">正在扫描目录...</div>
    </div>`;
  } else if (scannedFiles.length === 0 && !autoImporting) {
    html += `<div class="memory-empty">
      <div class="memory-empty-icon">📂</div>
      <div>输入目录路径，点击「🚀 一键导入」自动扫描并提取记忆</div>
      <div style="margin-top:8px;font-size:12px;opacity:0.6">或点击 🔍 手动扫描选择文件</div>
    </div>`;
  } else if (scannedFiles.length > 0) {
    // Manual mode: file list with checkboxes
    html += `<div class="doc-select-bar">
      <label>
        <input type="checkbox" id="memSelectAllFiles"
          onchange="toggleAllFiles(this.checked)"
          ${selectedFileIndices.size === scannedFiles.length && scannedFiles.length > 0 ? 'checked' : ''}>
        全选
      </label>
      <span>共 ${scannedFiles.length} 个文件，已选 ${selectedFileIndices.size} 个</span>
    </div>
    <div class="doc-file-list">`;
    scannedFiles.forEach((f, i) => {
      const checked = selectedFileIndices.has(i) ? 'checked' : '';
      const sizeStr = f.size ? formatFileSize(f.size) : '';
      const typeStr = f.type || f.name.split('.').pop() || '';
      html += `<div class="doc-file-item">
        <input type="checkbox" ${checked} onchange="toggleFileSelect(${i}, this.checked)">
        <div class="doc-file-name" title="${escapeHtml(f.path || f.name)}">${escapeHtml(f.name)}</div>
        ${sizeStr ? `<span class="doc-file-meta">${sizeStr}</span>` : ''}
        ${typeStr ? `<span class="doc-file-type">${escapeHtml(typeStr)}</span>` : ''}
      </div>`;
    });
    html += `</div>`;

    if (memoryExtracting) {
      html += `<div class="memory-progress">
        <div class="memory-progress-spinner"></div>
        <div class="memory-progress-text">正在提取记忆... 这可能需要一些时间</div>
      </div>`;
    } else {
      html += `<button class="memory-btn memory-btn-success" onclick="extractMemories()"
        style="width:100%;padding:10px" ${selectedFileIndices.size === 0 ? 'disabled' : ''}>
        🧬 提取记忆 (${selectedFileIndices.size} 个文件)
      </button>`;
    }

    if (extractResultCount !== null) {
      html += `<div class="memory-result-count">✅ 成功提取 ${extractResultCount} 条记忆</div>`;
    }
  }

  area.innerHTML = html;
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
  const area = document.getElementById('memoryContentArea');
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
  renderSyncTab();
}

function renderSyncTab() {
  const area = document.getElementById('memoryContentArea');
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
  renderSyncTab();
}

function toggleAllSyncItems(checked) {
  selectedSyncIds.clear();
  if (checked && memoryStats && memoryStats._approvedEntries) {
    memoryStats._approvedEntries.forEach(m => selectedSyncIds.add(m.id));
  }
  renderSyncTab();
}

function toggleSyncItem(id, checked) {
  if (checked) selectedSyncIds.add(id);
  else selectedSyncIds.delete(id);
  renderSyncTab();
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
    // 衰减曲线是默认tab，自动渲染
    if (typeof renderDecayCurve === 'function') renderDecayCurve();
    showToast('健康数据已加载', 'success');
  } catch(e) { console.error('Health load error', e); showToast('加载失败: ' + e.message, 'error'); }
}

function renderHealthCards(h) {
  const active = h.total_active || 0;
  const inactive = h.total_inactive || 0;
  const avgDecay = typeof h.avg_decay === 'number' ? (h.avg_decay * 100).toFixed(1) : '0.0';
  const cards = [
    { icon:'📦', value:active, label:'活跃条目', cls:'card-active' },
    { icon:'⏸️', value:inactive, label:'历史条目', cls:'card-inactive' },
    { icon:'📉', value:avgDecay+'%', label:'平均衰减', cls:'card-decay' },
    { icon:'📌', value:h.pinned||0, label:'已固定', cls:'card-pinned' },
    { icon:'⚠️', value:h.fading_candidates||0, label:'衰减预警', cls:'card-fading' },
    { icon:'🔄', value:h.version_changes||0, label:'版本变化', cls:'card-version' },
    { icon:'💾', value:h.snapshots||0, label:'快照数', cls:'card-snap' }
  ];
  document.getElementById('healthCards').innerHTML = cards.map(c =>
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
    if (q && !(e.content_preview||'').toLowerCase().includes(q) && !(e.primary_cat||'').toLowerCase().includes(q) && !(e.secondary_cat||'').toLowerCase().includes(q)) return false;
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
    const preview = (e.content_preview||'').slice(0,50) + ((e.content_preview||'').length>50?'…':'');
    const catLabel = [e.primary_cat, e.secondary_cat].filter(Boolean).join('/');
    const statusBadge = e.status === 'inactive' ? '<span class="status-badge inactive">历史</span>' : '';
    return `<tr>
      <td><div class="preview-text" title="${(e.content_preview||'').replace(/"/g,'&quot;')}">${preview} ${statusBadge}</div></td>
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
  try {
    const [distRes, dupRes, forgetRes, impRes] = await Promise.all([
      fetch('/api/consolidate/distribution'),
      fetch('/api/consolidate/duplicates'),
      fetch('/api/forget/analyze'),
      fetch('/api/analyze/importance')
    ]);
    
    const distribution = await distRes.json();
    const duplicates = await dupRes.json();
    const forget = await forgetRes.json();
    const importance = await impRes.json();
    
    // Render cards
    const totalNodes = distribution.total_memory_nodes || 0;
    const dupCount = duplicates.duplicates ? duplicates.duplicates.length : 0;
    const forgetCount = forget.to_forget ? forget.to_forget.length : 0;
    const highImp = (importance.high_importance || 0) + (importance.importance_distribution?.['0.8-1.0'] || 0);
    
    document.getElementById('analyzeCards').innerHTML = `
      <div class="analyze-card">
        <span class="ac-value">${totalNodes}</span>
        <span class="ac-label">总记忆节点</span>
      </div>
      <div class="analyze-card ${dupCount > 0 ? 'ac-highlight' : ''}">
        <span class="ac-value">${dupCount}</span>
        <span class="ac-label">重复记忆</span>
        <span class="ac-sub">建议合并</span>
      </div>
      <div class="analyze-card ${forgetCount > 0 ? 'ac-highlight' : ''}">
        <span class="ac-value">${forgetCount}</span>
        <span class="ac-label">可遗忘项</span>
        <span class="ac-sub">低价值记忆</span>
      </div>
      <div class="analyze-card">
        <span class="ac-value">${highImp}</span>
        <span class="ac-label">高重要性</span>
        <span class="ac-sub">核心记忆</span>
      </div>
    `;
    
    // Render overview
    document.getElementById('analyzeOverview').innerHTML = `
      <div class="analyze-stat-grid">
        <div class="analyze-stat-item">
          <div class="analyze-stat-label">记忆分类分布</div>
          <div class="analyze-bar-chart">
            ${Object.entries(distribution.by_primary_category || {}).map(([cat, count]) => `
              <div class="analyze-bar-row">
                <span class="analyze-bar-label">${cat}</span>
                <div class="analyze-bar-track"><div class="analyze-bar-fill" style="width:${totalNodes ? (count/totalNodes*100) : 0}%"></div></div>
                <span class="analyze-bar-value">${count}</span>
              </div>
            `).join('')}
          </div>
        </div>
        <div class="analyze-stat-item">
          <div class="analyze-stat-label">平均重要性</div>
          <div class="analyze-stat-value">${(distribution.avg_importance || 0).toFixed(2)}</div>
          <div style="font-size:12px;color:#888">满分 1.0</div>
        </div>
      </div>
    `;
    
    // Render duplicates
    const dupHtml = duplicates.duplicates && duplicates.duplicates.length > 0 
      ? duplicates.duplicates.map(g => `
        <div class="cr-group">
          <div class="cr-group-title">🔄 相似记忆 (${g.length})</div>
          <ul class="cr-group-list">
            ${g.map(m => `<li>${m.content_preview || m.label || '未命名'}</li>`).join('')}
          </ul>
        </div>
      `).join('')
      : '<div style="color:#ccc;text-align:center;padding:30px">未发现重复记忆 ✓</div>';
    document.getElementById('analyzeDuplicates').innerHTML = dupHtml;
    
    // Render forget
    document.getElementById('analyzeForget').innerHTML = `
      <div class="analyze-stat-grid">
        <div class="analyze-stat-item">
          <div class="analyze-stat-label">高风险遗忘</div>
          <div class="analyze-stat-value" style="color:#ef4444">${forget.score_distribution?.high_risk || 0}</div>
        </div>
        <div class="analyze-stat-item">
          <div class="analyze-stat-label">中风险遗忘</div>
          <div class="analyze-stat-value" style="color:#f59e0b">${forget.score_distribution?.medium_risk || 0}</div>
        </div>
        <div class="analyze-stat-item">
          <div class="analyze-stat-label">低风险遗忘</div>
          <div class="analyze-stat-value" style="color:#10b981">${forget.score_distribution?.low_risk || 0}</div>
        </div>
      </div>
    `;
    
    // Render importance
    const impDist = importance.importance_distribution || {};
    const highImpCount = (impDist['0.8-1.0'] || 0);
    const medImpCount = (impDist['0.4-0.6'] || 0) + (impDist['0.6-0.8'] || 0);
    const lowImpCount = (impDist['0-0.2'] || 0) + (impDist['0.2-0.4'] || 0);
    document.getElementById('analyzeImportance').innerHTML = `
      <div class="analyze-stat-grid">
        <div class="analyze-stat-item">
          <div class="analyze-stat-label">高重要性 (0.8-1.0)</div>
          <div class="analyze-stat-value" style="color:#8b5cf6">${highImpCount}</div>
        </div>
        <div class="analyze-stat-item">
          <div class="analyze-stat-label">中重要性 (0.4-0.8)</div>
          <div class="analyze-stat-value" style="color:#3b82f6">${medImpCount}</div>
        </div>
        <div class="analyze-stat-item">
          <div class="analyze-stat-label">低重要性 (0-0.4)</div>
          <div class="analyze-stat-value" style="color:#9ca3af">${lowImpCount}</div>
        </div>
      </div>
    `;
    
    // Render insights placeholder
    document.getElementById('analyzeInsights').innerHTML = `
      <div style="color:#666;line-height:1.8">
        <h3 style="margin-top:0">💡 分析洞察</h3>
        <ul style="padding-left:20px">
          <li>您的记忆库目前有 <strong>${totalNodes}</strong> 个节点</li>
          <li>其中 <strong>${highImp}</strong> 个是高重要性记忆，值得重点巩固</li>
          ${dupCount > 0 ? `<li>发现 <strong>${dupCount}</strong> 组相似记忆，建议合并以减少冗余</li>` : ''}
          ${forgetCount > 0 ? `<li>有 <strong>${forgetCount}</strong> 个记忆衰减严重，可以考虑归档或遗忘</li>` : ''}
        </ul>
      </div>
    `;
    
    showToast('分析完成', 'success');
  } catch(e) {
    console.error(e);
    showToast('分析加载失败', 'error');
  }
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
          <div class="cr-entry"><div class="cr-id">${d.pair[0]}</div>${(e1.content_preview||'').slice(0,80)}</div>
          <div class="cr-entry"><div class="cr-id">${d.pair[1]}</div>${(e2.content_preview||'').slice(0,80)}</div>
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
          <div class="cr-entry"><div class="cr-id">${c.pair[0]}</div>${(e1.content_preview||'').slice(0,80)}</div>
          <div class="cr-entry"><div class="cr-id">${c.pair[1]}</div>${(e2.content_preview||'').slice(0,80)}</div>
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

