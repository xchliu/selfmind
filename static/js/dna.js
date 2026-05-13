/* ─── Agent DNA 页面逻辑 ─── */

let dnaData = null;

async function loadDnaData() {
  try {
    const resp = await fetch('/api/dna/timeline');
    if (!resp.ok) throw new Error('API failed: ' + resp.status);
    dnaData = await resp.json();
    renderDnaPage();
  } catch (e) {
    console.error('DNA load error:', e);
    const summary = document.getElementById('dnaSummary');
    if (summary) summary.innerHTML = '<p style="color:#ef4444;">⚠️ 加载失败，请刷新重试</p>';
  }
}

function renderDnaPage() {
  if (!dnaData) return;
  renderDnaSummary();
  renderDnaHelix();
  renderDnaCategories();
  renderDnaTimeline();
  renderDnaEvents();
}

// ─── 概览 ───
function renderDnaSummary() {
  const s = dnaData.summary;
  if (!s) return;
  const container = document.getElementById('dnaSummary');
  container.innerHTML = `
    <div class="dna-summary-card">
      <div class="label">总记忆条目</div>
      <div class="value">${s.total_entries}</div>
      <div class="sub">${s.active} 活跃 / ${s.inactive} 历史</div>
    </div>
    <div class="dna-summary-card decay">
      <div class="label">平均记忆强度</div>
      <div class="value">${(s.avg_decay * 100).toFixed(0)}%</div>
      <div class="sub">decay_score 平均值</div>
    </div>
    <div class="dna-summary-card version">
      <div class="label">平均版本</div>
      <div class="value">${s.avg_version.toFixed(1)}</div>
      <div class="sub">每次内容变化版本+1</div>
    </div>
    <div class="dna-summary-card evolution">
      <div class="label">演变事件</div>
      <div class="value">${s.total_evolutions}</div>
      <div class="sub">版本变化 + 状态变化</div>
    </div>
  `;
}

// ─── 双螺旋可视化 ───
function renderDnaHelix() {
  const entries = dnaData.dna_entries;
  if (!entries || !entries.length) return;

  const svg = document.getElementById('dnaHelixSvg');
  const container = document.getElementById('dnaHelixContainer');
  if (!svg || !container) return;

  // 分类颜色映射
  const catColors = {
    'autobiographical': '#e74c3c',
    'semantic': '#3498db',
    'episodic': '#e67e22',
    'procedural': '#2ecc71',
    'social': '#9b59b6',
    'emotional': '#f1c40f',
    'strategic': '#1abc9c',
    'creative': '#e84393',
    'security': '#d63031',
    'failure': '#d35400',
    'working': '#00cec9',
    'spatial': '#636e72',
    'concept': '#00b894',
    'entity': '#6c5ce7',
    'project': '#fd79a8',
    'summary': '#0984e3',
    'comparison': '#fdcb6e',
  };

  function getColor(entry) {
    return catColors[entry.primary_cat] || '#74b9ff';
  }

  function getDecayColor(decay) {
    if (decay >= 0.6) return '#10b981';
    if (decay >= 0.3) return '#f59e0b';
    return '#ef4444';
  }

  // 只展示memory类型条目（核心DNA）
  const memoryEntries = entries.filter(e => e.type === 'memory');
  const activeMemories = memoryEntries.filter(e => e.status === 'active');

  if (!activeMemories.length) {
    svg.setAttribute('width', 800);
    svg.setAttribute('height', 100);
    svg.innerHTML = '<text x="400" y="50" text-anchor="middle" fill="#aaa" font-size="16">暂无记忆数据</text>';
    return;
  }

  // 按分类分组
  const byCategory = {};
  activeMemories.forEach(e => {
    const cat = e.primary_cat || 'unknown';
    if (!byCategory[cat]) byCategory[cat] = [];
    byCategory[cat].push(e);
  });

  const categories = Object.keys(byCategory).sort();
  const width = container.clientWidth - 40;
  const height = Math.max(categories.length * 32 + 80, 250);
  const centerX = width / 2;
  const amplitude = Math.min(100, width / 5);
  const spacingY = 32;
  const startY = 50;

  svg.setAttribute('width', width);
  svg.setAttribute('height', height);
  svg.innerHTML = '';

  const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  svg.appendChild(g);

  // 构建螺旋点数据
  const helixPoints = [];
  categories.forEach((catName, i) => {
    const y = startY + i * spacingY;
    const angle = (i / categories.length) * Math.PI * 4;
    const xLeft = centerX - amplitude * Math.cos(angle);
    const xRight = centerX + amplitude * Math.cos(angle);
    helixPoints.push({
      catName,
      y,
      xLeft,
      xRight,
      angle,
      entries: byCategory[catName]
    });
  });

  // 过程态链路径（左侧）
  let processPath = helixPoints.map((p, i) =>
    i === 0 ? `M ${p.xLeft} ${p.y}` : ` L ${p.xLeft} ${p.y}`
  ).join('');

  // 关系态链路径（右侧）
  let relationPath = helixPoints.map((p, i) =>
    i === 0 ? `M ${p.xRight} ${p.y}` : ` L ${p.xRight} ${p.y}`
  ).join('');

  // 绘制两条螺旋链
  const processLine = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  processLine.setAttribute('d', processPath);
  processLine.setAttribute('stroke', '#74b9ff');
  processLine.setAttribute('stroke-width', '3');
  processLine.setAttribute('fill', 'none');
  processLine.setAttribute('stroke-dasharray', '6,4');
  g.appendChild(processLine);

  const relationLine = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  relationLine.setAttribute('d', relationPath);
  relationLine.setAttribute('stroke', '#a29bfe');
  relationLine.setAttribute('stroke-width', '3');
  relationLine.setAttribute('fill', 'none');
  relationLine.setAttribute('stroke-dasharray', '6,4');
  g.appendChild(relationLine);

  // 绘制碱基对连接线和节点
  helixPoints.forEach((point) => {
    const avgDecay = point.entries.reduce((s, e) => s + e.decay_score, 0) / point.entries.length;
    const decayColor = getDecayColor(avgDecay);
    const catColor = getColor(point.entries[0]);

    // 碱基对连接线
    const connector = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    connector.setAttribute('x1', point.xLeft);
    connector.setAttribute('y1', point.y);
    connector.setAttribute('x2', point.xRight);
    connector.setAttribute('y2', point.y);
    connector.setAttribute('stroke', decayColor);
    connector.setAttribute('stroke-width', '2');
    connector.setAttribute('opacity', '0.5');
    g.appendChild(connector);

    // 过程态节点（左侧）— decay_score
    const leftNode = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    leftNode.setAttribute('cx', point.xLeft);
    leftNode.setAttribute('cy', point.y);
    leftNode.setAttribute('r', 6 + avgDecay * 8);
    leftNode.setAttribute('fill', decayColor);
    leftNode.setAttribute('opacity', '0.85');
    leftNode.setAttribute('class', 'dna-helix-node');
    leftNode.setAttribute('cursor', 'pointer');
    leftNode.addEventListener('click', () => showDnaEntryDetail(point.entries[0]));
    g.appendChild(leftNode);

    // 关系态节点（右侧）— 分类颜色
    const rightNode = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    rightNode.setAttribute('cx', point.xRight);
    rightNode.setAttribute('cy', point.y);
    rightNode.setAttribute('r', 7);
    rightNode.setAttribute('fill', catColor);
    rightNode.setAttribute('opacity', '0.85');
    rightNode.setAttribute('class', 'dna-helix-node');
    rightNode.setAttribute('cursor', 'pointer');
    rightNode.addEventListener('click', () => showDnaEntryDetail(point.entries[0]));
    g.appendChild(rightNode);

    // 标签（中间）
    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', centerX);
    label.setAttribute('y', point.y + 4);
    label.setAttribute('text-anchor', 'middle');
    label.setAttribute('fill', '#2d3436');
    label.setAttribute('font-size', '12');
    label.setAttribute('font-weight', '600');
    label.textContent = point.catName + ' (' + point.entries.length + ')';
    g.appendChild(label);
  });

  // 标注链名称
  const leftLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  leftLabel.setAttribute('x', 20);
  leftLabel.setAttribute('y', startY - 15);
  leftLabel.setAttribute('fill', '#74b9ff');
  leftLabel.setAttribute('font-size', '12');
  leftLabel.setAttribute('font-weight', '700');
  leftLabel.textContent = '过程态链';
  g.appendChild(leftLabel);

  const rightLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  rightLabel.setAttribute('x', width - 80);
  rightLabel.setAttribute('y', startY - 15);
  rightLabel.setAttribute('fill', '#a29bfe');
  rightLabel.setAttribute('font-size', '12');
  rightLabel.setAttribute('font-weight', '700');
  rightLabel.textContent = '关系态链';
  g.appendChild(rightLabel);
}

// ─── 分类基因图 ───
function renderDnaCategories() {
  const categories = dnaData.categories;
  if (!categories) return;
  const container = document.getElementById('dnaCategories');

  const catColors = {
    'autobiographical': '#e74c3c',
    'semantic': '#3498db',
    'episodic': '#e67e22',
    'procedural': '#2ecc71',
    'social': '#9b59b6',
    'emotional': '#f1c40f',
    'strategic': '#1abc9c',
    'creative': '#e84393',
    'security': '#d63031',
    'failure': '#d35400',
    'working': '#00cec9',
    'spatial': '#636e72',
    'concept': '#00b894',
    'entity': '#6c5ce7',
    'project': '#fd79a8',
    'summary': '#0984e3',
    'comparison': '#fdcb6e',
  };

  let html = '<h3>🧬 基因分类图谱</h3><div class="dna-cat-grid">';

  Object.entries(categories).forEach(([key, val]) => {
    const parts = key.split('/');
    const primary = parts[0];
    const secondary = parts[1] || '-';
    const color = catColors[primary] || '#74b9ff';
    const decayPct = (val.avg_decay * 100).toFixed(0);

    html += `
      <div class="dna-cat-card" onclick="filterDnaByCategory('${primary}')">
        <div class="dna-cat-name" style="color:${color}">${primary}/${secondary}</div>
        <div class="dna-cat-stats">
          <span>${val.count} 条</span>
          <span>强度 ${decayPct}%</span>
          <span>重要性 ${(val.avg_importance * 100).toFixed(0)}%</span>
        </div>
        <div class="dna-cat-bar">
          <div class="dna-cat-bar-fill" style="width:${decayPct}%;background:${color}"></div>
        </div>
      </div>
    `;
  });

  html += '</div>';
  container.innerHTML = html;
}

// ─── 时间线 ───
function renderDnaTimeline() {
  const timeline = dnaData.timeline;
  if (!timeline) return;
  const container = document.getElementById('dnaTimeline');

  const typeColors = {
    'memory': '#e74c3c',
    'skill': '#2ecc71',
    'wiki': '#3498db',
    'honcho_obs': '#9b59b6',
    'honcho_conc': '#f1c40f',
  };

  const maxEntries = Math.max(...timeline.map(t => t.entries_created), 1);

  let html = '<h3>📅 DNA 时间线 — 记忆增长过程</h3>';

  timeline.forEach(t => {
    const widthPct = (t.entries_created / maxEntries * 100).toFixed(1);
    const types = Object.entries(t.by_type || {});

    html += `
      <div class="dna-timeline-row">
        <div class="dna-tl-date">${t.date}</div>
        <div class="dna-tl-bar">
          ${types.map(([type, count]) => {
            const pct = (count / t.entries_created * 100).toFixed(1);
            return '<div class="dna-tl-segment" style="width:' + pct + '%;background:' + (typeColors[type] || '#ccc') + '"></div>';
          }).join('')}
        </div>
        <div class="dna-tl-count">${t.entries_created} 条</div>
      </div>
    `;
  });

  container.innerHTML = html;
}

// ─── 演变事件 ───
function renderDnaEvents() {
  const events = dnaData.evolution_events;
  if (!events) return;
  const container = document.getElementById('dnaEvents');

  if (!events.length) {
    container.innerHTML = '<h3>🔄 演变事件</h3><p style="color:#888;font-size:13px;">暂无演变记录</p>';
    return;
  }

  const recentEvents = events.slice(-20).reverse();

  let html = '<h3>🔄 演变事件 — 最近变化</h3>';

  recentEvents.forEach(ev => {
    const dotClass = ev.operation === 'version_change' ? 'version' :
                    ev.operation === 'inactivate' ? 'inactivate' : 'activate';
    const time = ev.timestamp ? ev.timestamp.slice(0, 16) : '--';
    const desc = formatEventDesc(ev);

    html += `
      <div class="dna-event-item">
        <div class="dna-event-dot ${dotClass}"></div>
        <div class="dna-event-time">${time}</div>
        <div class="dna-event-desc">${desc}</div>
      </div>
    `;
  });

  container.innerHTML = html;
}

function formatEventDesc(ev) {
  const op = ev.operation;
  const ids = ev.target_ids || [];
  const detail = ev.detail || {};

  if (op === 'version_change') {
    const before = detail.before && detail.before.version ? detail.before.version : '?';
    const after = detail.after && detail.after.version ? detail.after.version : '?';
    return '记忆 ' + (ids[0] || '?') + ' 版本变化: v' + before + ' → v' + after;
  }
  if (op === 'inactivate') {
    const reason = detail.reason || 'disappeared_from_source';
    return '记忆 ' + (ids[0] || '?') + ' 变为inactive (' + reason + ')';
  }
  if (op === 'activate') {
    return '记忆 ' + (ids[0] || '?') + ' 重新激活';
  }
  return op + ': ' + ids.join(', ');
}

// ─── 条目详情弹窗 ───
function showDnaEntryDetail(entry) {
  if (!entry) return;

  const modal = document.getElementById('dnaModal');
  const title = document.getElementById('dnaModalTitle');
  const body = document.getElementById('dnaModalBody');
  const evolution = document.getElementById('dnaModalEvolution');

  const decayPct = (entry.decay_score * 100).toFixed(0);
  const decayColor = entry.decay_score >= 0.6 ? '#10b981' :
                     entry.decay_score >= 0.3 ? '#f59e0b' : '#ef4444';

  title.textContent = entry.label || entry.id;
  body.innerHTML = `
    <div class="dna-field-row"><span class="dna-field-label">ID</span><span class="dna-field-value">${entry.id}</span></div>
    <div class="dna-field-row"><span class="dna-field-label">类型</span><span class="dna-field-value">${entry.type}</span></div>
    <div class="dna-field-row"><span class="dna-field-label">分类</span><span class="dna-field-value">${entry.primary_cat}/${entry.secondary_cat || '-'}</span></div>
    <div class="dna-field-row"><span class="dna-field-label">产生时间</span><span class="dna-field-value">${entry.first_seen_at || '--'}</span></div>
    <div class="dna-field-row"><span class="dna-field-label">版本</span><span class="dna-field-value">v${entry.version}</span></div>
    <div class="dna-field-row"><span class="dna-field-label">更新时间</span><span class="dna-field-value">${entry.updated_at || '--'}</span></div>
    <div class="dna-field-row"><span class="dna-field-label">记忆强度</span><span class="dna-field-value" style="color:${decayColor}">${decayPct}%</span></div>
    <div class="dna-field-row"><span class="dna-field-label">重要性</span><span class="dna-field-value">${(entry.importance * 100).toFixed(0)}%</span></div>
    <div class="dna-field-row"><span class="dna-field-label">状态</span><span class="dna-field-value">${entry.status}</span></div>
    <div style="margin-top:12px;padding:12px;background:#f5f7fa;border-radius:8px;font-size:13px;line-height:1.6;color:#2d3436;">
      ${entry.content_preview || '无内容预览'}
    </div>
  `;

  // 演变历史
  const versions = dnaData.entry_versions && dnaData.entry_versions[entry.id] ? dnaData.entry_versions[entry.id] : [];
  if (versions.length > 0) {
    let evoHtml = '<h4>演变时间线</h4>';
    versions.forEach(v => {
      evoHtml += `
        <div class="dna-version-item">
          <span class="dna-version-badge">v${v.version}</span>
          <span style="color:#888;font-size:11px;">${v.timestamp ? v.timestamp.slice(0, 16) : '--'}</span>
          <span style="margin-left:8px;">${v.content_preview ? v.content_preview.slice(0, 80) : '--'}...</span>
        </div>
      `;
    });
    evolution.innerHTML = evoHtml;
  } else {
    evolution.innerHTML = '<h4>演变时间线</h4><p style="color:#888;font-size:13px;">只有1个版本，暂无变化记录</p>';
  }

  modal.style.display = 'flex';
}

function closeDnaModal() {
  document.getElementById('dnaModal').style.display = 'none';
}

function filterDnaByCategory(category) {
  const entries = dnaData.dna_entries.filter(e => e.primary_cat === category);
  if (entries.length > 0) {
    showDnaEntryDetail(entries[0]);
  }
}

// ─── 初始化 ───
function initDnaView() {
  if (!dnaData) {
    loadDnaData();
  } else {
    renderDnaHelix();
  }
}