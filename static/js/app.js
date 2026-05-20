// 认知心理学记忆分类体系 — 8大类颜色 + 节点类型
const PRIMARY_COLORS = {
  autobiographical: { name: '自传体记忆', icon: '🧬', color: '#8B5CF6' },
  semantic:         { name: '语义记忆',   icon: '📚', color: '#3B82F6' },
  episodic:         { name: '情景记忆',   icon: '📖', color: '#F59E0B' },
  procedural:       { name: '程序性记忆', icon: '⚙️', color: '#10B981' },
  social:           { name: '社会认知',   icon: '👥', color: '#EC4899' },
  working:          { name: '工作记忆',   icon: '💼', color: '#F97316' },
  spatial:          { name: '空间记忆',   icon: '🗺️', color: '#06B6D4' },
  emotional:        { name: '情绪记忆',   icon: '❤️', color: '#EF4444' },
};

// 获取节点颜色：优先用 primary 分类色，回退到节点类型色
function getNodeColor(d) {
  if (d.category === 'center') return '#FFD700';
  // Wiki 视图的节点颜色
  if (currentView === 'wiki') {
    if (d.category === 'wiki_center') return WIKI_COLORS.wiki_center.color;
    if (WIKI_COLORS[d.category]) return WIKI_COLORS[d.category].color;
    return '#78909c';
  }
  // Memory nodes: blend importance into color (warm = important, cool = routine)
  if (d.category === 'memory' && d.importance !== undefined) {
    const imp = d.importance || 0;
    const baseColor = (d.primary && PRIMARY_COLORS[d.primary]) ? PRIMARY_COLORS[d.primary].color : '#78909c';
    // High importance → more saturated/brighter; low → more muted
    // We darken low-importance nodes by mixing with gray
    if (imp < 0.3) {
      return d3.interpolate('#b0bec5', baseColor)(imp / 0.3 * 0.5);
    }
    return baseColor;
  }
  if (d.primary && PRIMARY_COLORS[d.primary]) return PRIMARY_COLORS[d.primary].color;
  return '#78909c';
}

// 获取节点分类名称
function getNodeCatName(d) {
  if (d.category === 'center') return '核心身份';
  // Wiki 视图
  if (currentView === 'wiki') {
    if (WIKI_COLORS[d.category]) return WIKI_COLORS[d.category].name;
    return d.category;
  }
  if (d.category === 'primary' && PRIMARY_COLORS[d.primary]) return PRIMARY_COLORS[d.primary].name;
  if (d.category === 'secondary') {
    const p = PRIMARY_COLORS[d.primary];
    return p ? p.name + ' · ' + (d.label || d.secondary) : d.secondary;
  }
  if (d.category === 'memory') {
    const p = PRIMARY_COLORS[d.primary];
    return p ? p.name : '记忆';
  }
  if (d.category === 'skill') return '技能';
  if (d.category === 'skill_category') return '技能分类';
  if (d.category === 'skill_subcategory') return '技能子分类';
  return d.category;
}

// CATEGORIES 兼容层（用于 filter bar 等）
const CATEGORIES = {};
Object.entries(PRIMARY_COLORS).forEach(([k, v]) => {
  CATEGORIES[k] = { name: v.name, color: v.color, glow: v.color + '44' };
});
CATEGORIES.center = { name: '核心身份', color: '#FFD700', glow: '#FFD70044' };
CATEGORIES.memory = { name: '记忆节点', color: '#78909c', glow: '#78909c44' };
CATEGORIES.skill = { name: '技能', color: '#10B981', glow: '#10B98144' };
CATEGORIES.skill_category = { name: '技能分类', color: '#059669', glow: '#05966944' };
CATEGORIES.skill_subcategory = { name: '技能子分类', color: '#047857', glow: '#04785744' };
CATEGORIES.primary = { name: '一级分类', color: '#888', glow: '#88888844' };
CATEGORIES.secondary = { name: '二级分类', color: '#888', glow: '#88888844' };

let graphData = null;
let currentViewData = null;
let simulation = null;
let activeFilters = new Set();
let selectedNode = null;
let timelinePoints = [];
let activeTimelineIndex = -1;
let expandedNodes = new Set(); // 已展开的可折叠节点ID
let _timelineChangeInfo = { newNodeIds: new Set(), disappearedIds: new Set() }; // 时间线变化标记

// ========== 视图切换状态 ==========
let currentView = 'memory'; // 'memory' | 'wiki' | 'health'
let wikiGraphData = null;
let wikiCurrentViewData = null;

// Wiki 分类颜色
const WIKI_COLORS = {
  wiki_center: { name: '知识中心', icon: '🌐', color: '#e67e22' },
  entity:      { name: '实体',     icon: '🏢', color: '#e74c3c' },
  concept:     { name: '概念',     icon: '💡', color: '#3498db' },
  comparison:  { name: '对比分析', icon: '⚖️', color: '#2ecc71' },
  query:       { name: '查询结果', icon: '🔍', color: '#f39c12' },
  summary:     { name: '摘要',     icon: '📝', color: '#9b59b6' },
  project:     { name: '项目',     icon: '🚀', color: '#00cec9' },
  promotion:   { name: '推广',     icon: '📣', color: '#fd79a8' },
  nous:        { name: 'Nous',     icon: '🧠', color: '#6c5ce7' },
  manifesto:   { name: '宣言',     icon: '📜', color: '#6c5ce7' },
  blackboard:  { name: '黑板',     icon: '📋', color: '#e17055' },
  daily_report: { name: '日报',    icon: '📊', color: '#55a3e8' },
  raw:         { name: '原始素材', icon: '📦', color: '#b2bec3' },
  wiki_tag:    { name: '标签',     icon: '🏷️', color: '#95a5a6' },
  uncategorized: { name: '未分类', icon: '📄', color: '#78909c' },
};

// 持久化的 D3 选择集和容器（避免重建）
let _svg = null;
let _g = null;
let _zoom = null;
let _linkGroup = null;
let _nodeGroup = null;
let _graphWidth = 0;
let _graphHeight = 0;
// 保存节点位置映射（id -> {x, y}）用于增量更新时保留位置
let _nodePositions = {};

// 判断节点是否可折叠（有子节点的中间层级）
function isCollapsible(node, allLinks) {
  const cats = ['secondary', 'skill_category', 'skill_subcategory'];
  if (!cats.includes(node.category)) return false;
  // 检查是否有出边指向更低层级
  return allLinks.some(l => {
    const sid = l.source.id || l.source;
    const tid = l.target.id || l.target;
    return sid === node.id || tid === node.id;
  });
}

// 获取节点的所有子节点ID（递归）
function getDescendantIds(nodeId, allNodes, allLinks) {
  const children = new Set();
  const childCategories = {
    'secondary': ['memory', 'skill_category'],
    'skill_category': ['skill_subcategory', 'skill'],
    'skill_subcategory': ['skill'],
  };

  function collectChildren(parentId) {
    allLinks.forEach(l => {
      const sid = l.source.id || l.source;
      const tid = l.target.id || l.target;
      if (sid === parentId && !children.has(tid)) {
        children.add(tid);
        collectChildren(tid);
      }
    });
  }
  collectChildren(nodeId);
  return children;
}

// 过滤出当前应显示的节点和连线
function getVisibleData(data) {
  if (!data) return data;
  // 先找出所有被折叠隐藏的节点
  const hiddenIds = new Set();
  data.nodes.forEach(node => {
    if (isCollapsible(node, data.links) && !expandedNodes.has(node.id)) {
      const descendants = getDescendantIds(node.id, data.nodes, data.links);
      descendants.forEach(id => {
        // 但如果后代本身也被独立展开了，不隐藏它
        // 只隐藏从折叠节点出发能到达的末端
        hiddenIds.add(id);
      });
    }
  });

  // 如果一个节点被展开了，把它从隐藏列表中移除
  expandedNodes.forEach(id => hiddenIds.delete(id));

  // center, primary 永远不隐藏
  data.nodes.forEach(n => {
    if (['center', 'primary'].includes(n.category)) hiddenIds.delete(n.id);
  });

  // 如果一个 secondary 节点被展开了，它的直接子节点不隐藏
  data.nodes.forEach(n => {
    if (expandedNodes.has(n.id)) {
      data.links.forEach(l => {
        const sid = l.source.id || l.source;
        const tid = l.target.id || l.target;
        if (sid === n.id) hiddenIds.delete(tid);
      });
    }
  });

  const visibleNodes = data.nodes.filter(n => !hiddenIds.has(n.id));
  const visibleIds = new Set(visibleNodes.map(n => n.id));
  const visibleLinks = data.links.filter(l => {
    const sid = l.source.id || l.source;
    const tid = l.target.id || l.target;
    return visibleIds.has(sid) && visibleIds.has(tid);
  });

  return {
    ...data,
    nodes: visibleNodes,
    links: visibleLinks,
  };
}

// 切换节点的展开/折叠状态
function toggleNodeExpansion(node) {
  if (expandedNodes.has(node.id)) {
    // 折叠：同时折叠所有子节点
    expandedNodes.delete(node.id);
    const data = getActiveData();
    if (data) {
      const descendants = getDescendantIds(node.id, data.nodes, data.links);
      descendants.forEach(id => expandedNodes.delete(id));
    }
  } else {
    expandedNodes.add(node.id);
  }
  // 增量更新（不重建整个图）
  updateVisibleGraph();
  updateStats();
  updateToggleAllButton();
  updateTimelineRuler();
}

// 全部展开/全部折叠
function toggleAllNodes() {
  const data = getActiveData();
  if (!data) return;
  
  // 找出所有可折叠节点
  const collapsibleNodes = data.nodes.filter(n => isCollapsible(n, data.links));
  
  // 如果有任何已展开的，就全部折叠；否则全部展开
  const anyExpanded = collapsibleNodes.some(n => expandedNodes.has(n.id));
  
  if (anyExpanded) {
    // 全部折叠
    expandedNodes.clear();
  } else {
    // 全部展开
    collapsibleNodes.forEach(n => expandedNodes.add(n.id));
  }
  
  updateVisibleGraph();
  updateStats();
  updateToggleAllButton();
  updateTimelineRuler();
}

// 更新按钮文字（btnToggleAll已从HTML移除，保留函数以防引用）
function updateToggleAllButton() {
  const data = getActiveData();
  if (!data) return;
  const icon = document.getElementById('toggleAllIcon');
  const text = document.getElementById('toggleAllText');
  if (!icon || !text) return; // 按钮已移除
  const collapsibleNodes = data.nodes.filter(n => isCollapsible(n, data.links));
  const anyExpanded = collapsibleNodes.some(n => expandedNodes.has(n.id));
  icon.textContent = anyExpanded ? '📁' : '📂';
  text.textContent = anyExpanded ? '折叠全部' : '展开全部';
}

function parseTs(ts) {
  if (!ts) return null;
  const t = new Date(ts).getTime();
  return Number.isFinite(t) ? t : null;
}

function formatDate(ts) {
  return new Date(ts).toLocaleDateString('zh-CN');
}

function formatDateTime(ts) {
  return new Date(ts).toLocaleString('zh-CN');
}

function buildTimelinePoints(data) {
  const points = [];
  const pushPoint = (ts, type, nodeId) => {
    if (!Number.isFinite(ts)) return;
    points.push({ ts, type, nodeId });
  };

  data.nodes.forEach(node => {
    const created = parseTs(node.createdAt) ?? parseTs(data.lastUpdated) ?? Date.now();
    const updated = parseTs(node.updatedAt) ?? created;
    pushPoint(created, 'created', node.id);
    pushPoint(updated, 'updated', node.id);
  });

  const lastUpdated = parseTs(data.lastUpdated);
  if (lastUpdated) pushPoint(lastUpdated, 'graph', 'graph');

  points.sort((a, b) => a.ts - b.ts);
  const dedup = [];
  let prev = null;
  points.forEach(p => {
    if (p.ts !== prev) {
      dedup.push(p);
      prev = p.ts;
    }
  });
  return dedup;
}

function renderTimelineAxis() {
  const axis = document.getElementById('timelineAxis');
  if (!axis) return;
  if (!timelinePoints.length) {
    axis.innerHTML = '';
    return;
  }

  const tickCount = Math.min(7, timelinePoints.length);
  const idxSet = new Set();
  for (let i = 0; i < tickCount; i += 1) {
    const idx = Math.round((timelinePoints.length - 1) * (i / Math.max(1, tickCount - 1)));
    idxSet.add(idx);
  }
  idxSet.add(activeTimelineIndex);
  const indices = [...idxSet].filter(i => i >= 0).sort((a, b) => a - b);

  axis.innerHTML = indices.map(idx => {
    const left = timelinePoints.length === 1 ? 0 : (idx / (timelinePoints.length - 1)) * 100;
    const active = idx === activeTimelineIndex ? 'active' : '';
    return `<div class="timeline-tick ${active}" style="left:${left}%"><div class="timeline-tick-mark"></div><div class="timeline-tick-label">${formatDate(timelinePoints[idx].ts)}</div></div>`;
  }).join('');
}

function updateTimelineRuler() {
  const slider = document.getElementById('timelineSlider');
  const startLabel = document.getElementById('timelineStart');
  const endLabel = document.getElementById('timelineEnd');
  const currentLabel = document.getElementById('timelineCurrent');
  const stats = document.getElementById('timelineStats');

  if (!slider || !startLabel || !endLabel || !currentLabel || !stats) return;

  if (!timelinePoints.length) {
    slider.min = 0;
    slider.max = 0;
    slider.value = 0;
    slider.disabled = true;
    startLabel.textContent = '起点 --';
    endLabel.textContent = '终点 --';
    currentLabel.textContent = '当前：--';
    stats.textContent = '暂无记忆时间点';
    renderTimelineAxis();
    return;
  }

  slider.disabled = timelinePoints.length <= 1;
  slider.min = 0;
  slider.max = String(timelinePoints.length - 1);
  slider.value = String(Math.max(0, activeTimelineIndex));

  const first = timelinePoints[0].ts;
  const current = timelinePoints[Math.max(0, activeTimelineIndex)].ts;
  const last = timelinePoints[timelinePoints.length - 1].ts;
  startLabel.textContent = `起点 ${formatDate(first)}`;
  endLabel.textContent = `终点 ${formatDate(last)}`;
  currentLabel.textContent = `当前：${formatDateTime(current)}`;

  const visibleData = getVisibleData(currentViewData);
  const visibleNodes = visibleData ? visibleData.nodes.length : 0;
  const visibleLinks = visibleData ? visibleData.links.length : 0;
  const totalNodes = (currentViewData?.nodes || []).length;

  // ── 变化摘要 ──
  let changeHtml = '';
  const newCount = _timelineChangeInfo.newNodeIds.size;
  const disCount = _timelineChangeInfo.disappearedIds.size;
  if (newCount > 0) {
    // 找出新增节点的名称
    const newNames = (currentViewData?.nodes || [])
      .filter(n => _timelineChangeInfo.newNodeIds.has(n.id))
      .map(n => n.label || n.id)
      .slice(0, 5);
    changeHtml += ` · <span style="color:#34d399;font-weight:600">+${newCount}</span>`;
    if (newNames.length > 0) {
      changeHtml += `<span style="font-size:9px;color:#34d399;margin-left:2px">${newNames.join(', ')}</span>`;
    }
  }
  if (disCount > 0) {
    changeHtml += ` · <span style="color:#ef4444;font-weight:600">-${disCount}</span>`;
  }

  stats.innerHTML = `节点 ${visibleNodes}<span style="font-size:10px;color:#999">/${totalNodes}</span> · 连线 ${visibleLinks}${changeHtml}`;
  renderTimelineAxis();
}

function applyTimepoint(index) {
  if (!timelinePoints.length || !graphData) return;
  const bounded = Math.max(0, Math.min(timelinePoints.length - 1, Number(index) || 0));
  activeTimelineIndex = bounded;
  const ts = timelinePoints[bounded].ts;

  // ── 计算当前帧与前一帧的差异 ──
  const prevTs = bounded > 0 ? timelinePoints[bounded - 1].ts : null;
  const prevNodeIds = prevTs ? new Set(
    graphData.nodes
      .filter(n => {
        const created = parseTs(n.createdAt) ?? parseTs(graphData.lastUpdated) ?? Date.now();
        return created <= prevTs;
      })
      .map(n => n.id)
  ) : new Set();

  const visibleNodes = graphData.nodes
    .filter(n => {
      const created = parseTs(n.createdAt) ?? parseTs(graphData.lastUpdated) ?? Date.now();
      return created <= ts;
    })
    .map(n => {
      const copy = { ...n };
      // 标记新增节点
      if (!prevNodeIds.has(n.id)) {
        copy._isNew = true;
      }
      return copy;
    });

  // ── 自动展开有变化的分类节点 ──
  const newNodeIds = new Set(visibleNodes.filter(n => n._isNew).map(n => n.id));
  // 找出消失的节点：上一帧存在但当前帧不存在
  const disappearedIds = prevTs ? new Set(
    [...prevNodeIds].filter(id => !new Set(visibleNodes.map(n => n.id)).has(id))
  ) : new Set();

  const nodeIds = new Set(visibleNodes.map(n => n.id));
  const visibleLinks = graphData.links
    .map(l => ({
      source: l.source?.id || l.source,
      target: l.target?.id || l.target,
      label: l.label || '',
    }))
    .filter(l => nodeIds.has(l.source) && nodeIds.has(l.target));

  // 如果有新增或消失的节点，找到其所属的可折叠分类并自动展开
  if (newNodeIds.size > 0 || disappearedIds.size > 0) {
    const allChangedIds = new Set([...newNodeIds, ...disappearedIds]);
    visibleNodes.forEach(n => {
      if (isCollapsible(n, visibleLinks)) {
        // 检查这个分类的子节点是否有变化
        const descendants = getDescendantIds(n.id, visibleNodes, visibleLinks);
        for (const did of descendants) {
          if (allChangedIds.has(did)) {
            expandedNodes.add(n.id);
            break;
          }
        }
      }
    });
  }

  currentViewData = {
    lastUpdated: new Date(ts).toISOString(),
    source: graphData.source,
    nodes: visibleNodes,
    links: visibleLinks,
  };

  // ── 保存变化信息供渲染使用 ──
  _timelineChangeInfo = { newNodeIds, disappearedIds };

  hideDetail();
  updateTimelineRuler();
  updateStats(currentViewData);

  // 增量更新：如果已初始化过 SVG，用增量模式避免整页重建
  if (_svg) {
    updateVisibleGraph();
  } else {
    renderGraph(currentViewData);
  }

  const q = document.getElementById('searchInput')?.value?.trim();
  if (q) handleSearch(q);
}

function handleTimelineInput(value) {
  applyTimepoint(Number(value));
}

function jumpToLatest() {
  if (!timelinePoints.length) return;
  // 跳到最新时清除变化标记
  _timelineChangeInfo = { newNodeIds: new Set(), disappearedIds: new Set() };
  applyTimepoint(timelinePoints.length - 1);
}

// ── 时间轴播放 ──
let _playTimer = null;
let _isPlaying = false;
let _playSpeed = 2000; // 每帧间隔 ms

function toggleTimelinePlay() {
  if (_isPlaying) {
    stopTimelinePlay();
  } else {
    startTimelinePlay();
  }
}

function startTimelinePlay() {
  if (!timelinePoints.length) return;

  const slider = document.getElementById('timelineSlider');
  let current = Number(slider.value);
  const max = timelinePoints.length - 1;

  // 如果已在最新，从头开始播放
  if (current >= max) {
    current = 0;
    applyTimepoint(current);
    slider.value = current;
  }

  _isPlaying = true;
  const btn = document.getElementById('btnTimelinePlay');
  btn.classList.add('playing');
  btn.querySelector('.play-icon').textContent = '⏸';
  document.getElementById('playLabel').textContent = '暂停';

  _playTimer = setInterval(() => {
    current++;
    if (current > max) {
      stopTimelinePlay();
      return;
    }
    slider.value = current;
    applyTimepoint(current);

    // 更新进度条
    const pct = max > 0 ? (current / max) * 100 : 100;
    document.getElementById('timelineProgress').style.width = pct + '%';
  }, _playSpeed);
}

function stopTimelinePlay() {
  _isPlaying = false;
  if (_playTimer) {
    clearInterval(_playTimer);
    _playTimer = null;
  }

  const btn = document.getElementById('btnTimelinePlay');
  btn.classList.remove('playing');
  btn.querySelector('.play-icon').textContent = '▶';
  document.getElementById('playLabel').textContent = '播放';

  // 播放结束后，镜头平滑回到全局视角
  if (_zoom) {
    _svg.transition().duration(1200).ease(d3.easeCubicInOut)
      .call(_zoom.transform,
        d3.zoomIdentity.translate(_graphWidth / 2, _graphHeight / 2).scale(0.85).translate(-_graphWidth / 2, -_graphHeight / 2)
      );
  }

  // 进度条渐隐
  setTimeout(() => {
    if (!_isPlaying) {
      document.getElementById('timelineProgress').style.width = '0%';
    }
  }, 1500);
}

// 手动拖动滑块时停止播放
function handleTimelineInputWithStop(value) {
  if (_isPlaying) stopTimelinePlay();
  handleTimelineInput(value);
}

// 显示 Toast
function showToast(msg, type = 'info') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `toast ${type} show`;
  setTimeout(() => t.classList.remove('show'), 2500);
}

// 刷新 — 调用后端 API
async function handleRefresh() {
  if (currentView === 'wiki') return handleWikiRefresh();
  const btn = document.getElementById('btnRefresh');
  btn.classList.add('loading');
  try {
    const res = await fetch('/api/refresh', { method: 'POST' });
    const json = await res.json();
    if (json.status === 'ok') {
      showToast(`✅ 记忆已刷新 — ${json.nodes}个节点, ${json.links}条连线`, 'success');
      await loadData();
      loadIQ();
    } else {
      showToast(`❌ ${json.message}`, 'error');
    }
  } catch (e) {
    showToast(`❌ 网络错误: ${e.message}`, 'error');
  }
  btn.classList.remove('loading');
}

// 保存 — 调用后端 API
async function handleSave() {
  const btn = document.getElementById('btnSave');
  if (!btn) { showToast('保存功能已移至快照管理', 'info'); return; }
  btn.classList.add('loading');
  try {
    const res = await fetch('/api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentView === 'wiki' ? (wikiCurrentViewData || wikiGraphData) : (currentViewData || graphData)),
    });
    const json = await res.json();
    if (json.status === 'ok') {
      showToast(`💾 已保存到 ${json.path}`, 'success');
    } else {
      showToast(`❌ ${json.message}`, 'error');
    }
  } catch (e) {
    showToast(`❌ 网络错误: ${e.message}`, 'error');
  }
  if (btn) btn.classList.remove('loading');
}

// 搜索
function handleSearch(query) {
  const data = getActiveData();
  if (!data) return;
  const q = query.trim().toLowerCase();
  d3.selectAll('.node-group')
    .classed('dimmed', d => q && !d.label.toLowerCase().includes(q) && !(d.description || '').toLowerCase().includes(q))
    .classed('highlighted', d => q && (d.label.toLowerCase().includes(q) || (d.description || '').toLowerCase().includes(q)));
  d3.selectAll('.link-group').classed('dimmed', q ? true : false);
  if (q) {
    const matched = data.nodes.filter(n => n.label.toLowerCase().includes(q) || (n.description || '').toLowerCase().includes(q));
    const ids = new Set(matched.map(n => n.id));
    d3.selectAll('.link-group').classed('dimmed', d => !ids.has(d.source.id) && !ids.has(d.target.id));
  }
}

// 筛选栏
function buildFilterBar() {
  const bar = document.getElementById('filterBar');
  bar.innerHTML = '';
  // 全部
  const allChip = document.createElement('div');
  allChip.className = 'filter-chip active';
  allChip.textContent = '全部';
  allChip.style.borderColor = 'rgba(255,255,255,0.2)';
  allChip.onclick = () => {
    activeFilters.clear();
    document.querySelectorAll('.filter-chip').forEach(c => {
      c.classList.remove('active');
      c.style.background = '';
      c.style.borderColor = c.dataset.color ? c.dataset.color + '44' : 'rgba(255,255,255,0.2)';
    });
    allChip.classList.add('active');
    applyFilters();
  };
  bar.appendChild(allChip);

  // 只按 8 大一级分类过滤
  Object.entries(PRIMARY_COLORS).forEach(([key, cat]) => {
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
        chip.style.borderColor = cat.color + '88';
      }
      allChip.classList.toggle('active', activeFilters.size === 0);
      applyFilters();
    };
    bar.appendChild(chip);
  });
}

function applyFilters() {
  if (activeFilters.size === 0) {
    d3.selectAll('.node-group').classed('dimmed', false);
    d3.selectAll('.link-group').classed('dimmed', false);
    return;
  }
  const isWiki = currentView === 'wiki';
  // 记忆视图按 primary，Wiki 视图按 category
  d3.selectAll('.node-group').classed('dimmed', d => {
    if (d.category === 'center' || d.category === 'wiki_center') return false;
    return !activeFilters.has(isWiki ? d.category : d.primary);
  });
  d3.selectAll('.link-group').classed('dimmed', d => {
    const sField = isWiki ? d.source.category : d.source.primary;
    const tField = isWiki ? d.target.category : d.target.primary;
    return !activeFilters.has(sField) && !activeFilters.has(tField);
  });
}

// 统计面板
function updateStats(data = getActiveData()) {
  if (!data) return;
  // 获取折叠后的可见数据
  const visible = getVisibleData(data);
  const totalNodes = data.nodes.length;
  const visibleNodeCount = visible.nodes.length;
  const totalLinks = data.links.length;
  const visibleLinkCount = visible.links.length;

  let categoryHtml = '';
  if (currentView === 'wiki') {
    // Wiki 视图：按 category 统计
    const catCounts = {};
    data.nodes.forEach(n => {
      if (n.category && n.category !== 'wiki_center') catCounts[n.category] = (catCounts[n.category] || 0) + 1;
    });
    categoryHtml = Object.entries(catCounts).map(([k, v]) => {
      const w = WIKI_COLORS[k];
      return w ? `<div class="stat-row"><span class="stat-label" style="color:${w.color}">${w.icon} ${w.name}</span><span class="stat-value">${v}</span></div>` : '';
    }).join('');
  } else {
    // 记忆视图：按 primary 一级分类统计
    const primCounts = {};
    data.nodes.forEach(n => {
      if (n.primary) primCounts[n.primary] = (primCounts[n.primary] || 0) + 1;
    });
    const skillCount = data.nodes.filter(n => n.category === 'skill').length;
    const memCount = data.nodes.filter(n => n.category === 'memory').length;
    categoryHtml = `
      <div class="stat-row"><span class="stat-label">记忆</span><span class="stat-value">${memCount}</span></div>
      <div class="stat-row"><span class="stat-label">技能</span><span class="stat-value">${skillCount}</span></div>
      <div class="divider"></div>
      ${Object.entries(primCounts).map(([k, v]) => {
        const p = PRIMARY_COLORS[k];
        return p ? `<div class="stat-row"><span class="stat-label" style="color:${p.color}">${p.icon} ${p.name}</span><span class="stat-value">${v}</span></div>` : '';
      }).join('')}`;
  }

  document.getElementById('statsPanel').innerHTML = `
    <div class="stat-row"><span class="stat-label">节点</span><span class="stat-value">${visibleNodeCount}<span style="font-size:9px;color:#999">/${totalNodes}</span></span></div>
    <div class="stat-row"><span class="stat-label">连线</span><span class="stat-value">${visibleLinkCount}<span style="font-size:9px;color:#999">/${totalLinks}</span></span></div>
    ${categoryHtml}
    <div class="divider"></div>
    <div class="stat-row"><span class="stat-label">更新</span><span class="stat-value" style="font-size:10px">${data.lastUpdated ? new Date(data.lastUpdated).toLocaleString('zh-CN') : '--'}</span></div>
  `;
}

// 节点详情
function showDetail(d) {
  const data = getActiveData();
  if (!data) return;
  selectedNode = d;
  const panel = document.getElementById('detailPanel');
  const nodeColor = getNodeColor(d);
  const catName = getNodeCatName(d);
  document.getElementById('detailDot').style.background = nodeColor;
  document.getElementById('detailDot').style.boxShadow = `0 0 10px ${nodeColor}`;
  document.getElementById('detailName').textContent = d.label;
  document.getElementById('detailCategory').textContent = catName;
  document.getElementById('detailDesc').textContent = d.description || '暂无描述';
  const createdAt = d.createdAt ? new Date(d.createdAt).toLocaleString('zh-CN') : '--';
  const updatedAt = d.updatedAt ? new Date(d.updatedAt).toLocaleString('zh-CN') : '--';
  document.getElementById('detailTimeline').textContent = `创建: ${createdAt} · 更新: ${updatedAt}`;

  // 找连接
  const conns = data.links.filter(l =>
    (l.source.id || l.source) === d.id || (l.target.id || l.target) === d.id
  );
  document.getElementById('detailConn').textContent = `${conns.length} 个连接`;

  // Analytics info for memory nodes
  const analyticsEl = document.getElementById('detailAnalytics');
  if (analyticsEl) {
    if (d.category === 'memory' && (d.access_count !== undefined || d.importance !== undefined)) {
      const ac = d.access_count || 0;
      const imp = d.importance !== undefined ? Math.round(d.importance * 100) : '--';
      analyticsEl.textContent = `📊 引用次数: ${ac} · 重要性: ${imp}%`;
      analyticsEl.style.display = 'block';
    } else {
      analyticsEl.style.display = 'none';
    }
  }

  panel.classList.add('show');

  // 高亮相关
  const connIds = new Set();
  connIds.add(d.id);
  conns.forEach(l => {
    connIds.add(l.source.id || l.source);
    connIds.add(l.target.id || l.target);
  });
  d3.selectAll('.node-group').classed('dimmed', n => !connIds.has(n.id)).classed('highlighted', n => n.id === d.id);
  d3.selectAll('.link-group').classed('dimmed', l => (l.source.id || l.source) !== d.id && (l.target.id || l.target) !== d.id);

  // 点击节点时，显示被点击节点及其相连节点的隐藏标签
  d3.selectAll('.node-group').each(function(n) {
    const label = d3.select(this).select('.node-label');
    // 所有可见节点都已经显示标签了，高亮连接的即可
    if (connIds.has(n.id)) {
      label.attr('display', 'block').style('opacity', 1);
    } else {
      label.style('opacity', 0.3);
    }
  });
}

function hideDetail() {
  selectedNode = null;
  document.getElementById('detailPanel').classList.remove('show');
  d3.selectAll('.node-group').classed('dimmed', false).classed('highlighted', false);
  d3.selectAll('.link-group').classed('dimmed', false);
  // 恢复所有标签透明度
  d3.selectAll('.node-group').each(function(n) {
    d3.select(this).select('.node-label').style('opacity', null);
  });
}

// 加载数据并渲染图谱
