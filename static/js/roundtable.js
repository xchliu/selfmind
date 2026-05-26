// ========== 圆桌议事 Dashboard v3 ==========
// 浅色主题 + 圆桌设计 + 信号气泡 + 看板墙

// Agent 配置
const RT_AGENTS = [
  { id: 'socrates', name: '苏格拉底', role: '首席架构师', emoji: '🧠', color: '#8B5CF6' },
  { id: 'aris',     name: '小亚',     role: '开发助手',   emoji: '🤖', color: '#3B82F6' },
  { id: 'plato',    name: '柏拉图',   role: '评审专家',   emoji: '📐', color: '#10B981' },
  { id: 'grace',    name: 'Grace',    role: '对话助手',   emoji: '💎', color: '#EC4899' },
  { id: 'gateway',  name: 'Gateway',  role: '消息网关',   emoji: '🔗', color: '#F59E0B' },
];

const RT_COLUMN_ORDER = ['ready', 'running', 'blocked', 'done'];
const RT_COLUMN_LABELS = {
  ready:   '待领取',
  running: '进行中',
  blocked: '已阻塞',
  done:    '已完成',
  todo:    '待处理',
};

let rtData = { agents: {}, blackboard: [], kanban: [] };

// ===== 加载数据 =====
async function loadRoundTableData() {
  const refreshBtn = document.getElementById('rtRefreshBtn');
  if (refreshBtn) refreshBtn.classList.add('loading');

  try {
    const [agentsRes, blackboardRes, kanbanRes] = await Promise.all([
      fetch('/api/proxy/agents?t=' + Date.now()),
      fetch('/api/blackboard?t=' + Date.now()),
      fetch('/api/kanban/tasks?t=' + Date.now()),
    ]);

    rtData.agents = await agentsRes.json();
    rtData.blackboard = await blackboardRes.json();
    rtData.kanban = await kanbanRes.json();

    renderRoundTable();
    renderBoardWall();
    renderSignalBubbles();
    updateRTLastUpdate();

    // 更新看板统计
    const tasks = rtData.kanban.tasks || [];
    const totalEl = document.getElementById('rtBoardTotal');
    if (totalEl) totalEl.textContent = tasks.length;
    const runningCount = tasks.filter(t => t.status === 'running').length;
    const runningEl = document.getElementById('rtBoardRunning');
    if (runningEl) runningEl.textContent = runningCount;
  } catch (e) {
    showToast('❌ 圆桌数据加载失败: ' + e.message, 'error');
    renderEmptyState();
  }

  if (refreshBtn) refreshBtn.classList.remove('loading');
}

function updateRTLastUpdate() {
  const el = document.getElementById('rtLastUpdate');
  if (el) el.textContent = '更新于 ' + new Date().toLocaleTimeString('zh-CN');
}

// ===== 渲染圆桌 =====
function renderRoundTable() {
  const svgWrap = document.getElementById('rtTableSvg');
  const agents = rtData.agents || {};

  let html = '';
  RT_AGENTS.forEach((agent, i) => {
    const status = agents[agent.id];
    const isOnline = status && status.status === 'ok';
    const dotClass = isOnline ? 'online' : 'offline';
    const statusText = isOnline ? '在线' : '离线';

    html += `
      <div class="rt-agent-card rt-agent-pos-${i}" title="${agent.role}">
        <div class="rt-agent-avatar" style="border-color: ${agent.color}44;">
          ${agent.emoji}
          <span class="rt-agent-status-dot ${dotClass}"></span>
        </div>
        <div class="rt-agent-name">${agent.name}</div>
        <div class="rt-agent-role">${agent.role}</div>
        <div class="rt-agent-info">
          <span style="color:${isOnline ? '#2ed573' : '#ff4757'}">●</span> ${statusText}
          ${status && status.platform ? ' · ' + status.platform : ''}
        </div>
      </div>
    `;
  });

  // 圆桌SVG（渐变桌面）
  const svg = `
    <svg viewBox="0 0 360 250">
      <defs>
        <radialGradient id="tableGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#e8f0fe" stop-opacity="0.8"/>
          <stop offset="60%" stop-color="#f0f4ff" stop-opacity="0.3"/>
          <stop offset="100%" stop-color="#f5f7fa" stop-opacity="0"/>
        </radialGradient>
        <radialGradient id="tableTop" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="80%" stop-color="#f8fafc"/>
          <stop offset="100%" stop-color="#eef2f7"/>
        </radialGradient>
        <filter id="tableShadow">
          <feDropShadow dx="0" dy="2" stdDeviation="6" flood-color="rgba(0,0,0,0.06)"/>
        </filter>
      </defs>
      <!-- 背景光晕 -->
      <ellipse cx="180" cy="130" rx="160" ry="100" fill="url(#tableGlow)"/>
      <!-- 桌面椭圆 -->
      <ellipse cx="180" cy="130" rx="150" ry="85" fill="url(#tableTop)" stroke="rgba(0,0,0,0.06)" stroke-width="1.5" filter="url(#tableShadow)"/>
      <!-- 桌面内圈装饰 -->
      <ellipse cx="180" cy="130" rx="100" ry="55" fill="none" stroke="rgba(0,0,0,0.03)" stroke-width="1" stroke-dasharray="4,4"/>
      <!-- 会议标签 -->
      <text x="180" y="135" text-anchor="middle" font-size="11" fill="#bbb" font-weight="500" font-family="-apple-system,sans-serif">⚡ 圆桌会议</text>
    </svg>
  `;

  svgWrap.innerHTML = svg;
  // Agent卡片通过CSS定位在圆桌SVG之上
}

// ===== 渲染信号气泡 =====
function renderSignalBubbles() {
  const container = document.getElementById('rtSignals');
  const boards = rtData.blackboard.boards || {};
  const totalNotices = rtData.blackboard.total_notices || 0;

  const countEl = document.getElementById('rtSignalCount');
  if (countEl) countEl.textContent = totalNotices;

  let notices = [];

  // 收集所有黑板通知
  Object.entries(boards).forEach(([owner, items]) => {
    if (!Array.isArray(items)) return;
    items.forEach(item => {
      notices.push({
        owner,
        ...item,
      });
    });
  });

  // 按日期排序（最新的在前）
  notices.sort((a, b) => {
    if (a.date && b.date) return b.date.localeCompare(a.date);
    if (a.date) return -1;
    if (b.date) return 1;
    return 0;
  });

  // 取前8条
  const visible = notices.slice(0, 8);

  if (visible.length === 0) {
    container.innerHTML = `
      <div class="rt-signals-empty">
        <div class="rt-signals-empty-icon">🔇</div>
        <div>暂无信号通知</div>
      </div>
    `;
    return;
  }

  container.innerHTML = visible.map(notice => {
    const type = detectSignalType(notice);
    const emojiMap = { info: 'ℹ️', warn: '⚠️', task: '📋', alert: '🔔' };
    const agentEmoji = RT_AGENTS.find(a => a.name === notice.owner)?.emoji || '👤';
    return `
      <div class="rt-signal type-${type}" onclick="showSignalModal(${escapeJson(JSON.stringify(notice))})">
        <div class="rt-signal-avatar">${agentEmoji}</div>
        <div class="rt-signal-body">
          <div class="rt-signal-header">
            <span class="rt-signal-agent">${notice.owner ? escapeHtml(notice.owner) : '系统'}</span>
            ${notice.date ? `<span class="rt-signal-time">${formatRTDate(notice.date)}</span>` : ''}
          </div>
          <div class="rt-signal-title">${escapeHtml(notice.title || '无标题')}</div>
          ${notice.content ? `<div class="rt-signal-preview">${escapeHtml(notice.content.slice(0, 120))}</div>` : ''}
        </div>
      </div>
    `;
  }).join('');

  // 如果还有更多
  if (notices.length > 8) {
    container.innerHTML += `
      <div style="text-align:center;padding:6px 0;font-size:11px;color:#bbb;">
        +${notices.length - 8} 条更早通知
      </div>
    `;
  }
}

function detectSignalType(notice) {
  const title = (notice.title || '') + ' ' + (notice.content || '');
  if (title.includes('🔧') || title.includes('开发') || title.includes('任务')) return 'task';
  if (title.includes('⚠️') || title.includes('警告') || title.includes('风险')) return 'warn';
  if (title.includes('🔔') || title.includes('紧急') || title.includes('故障')) return 'alert';
  return 'info';
}

// ===== 信号弹窗 =====
function showSignalModal(notice) {
  if (typeof notice === 'string') notice = JSON.parse(notice);
  document.getElementById('rtModalOverlay').classList.add('open');
  document.getElementById('rtModal').classList.add('open');
  document.getElementById('rtModalTitle').textContent = notice.title || '通知详情';
  document.getElementById('rtModalBody').innerHTML = formatNoticeBody(notice.content || '');
  document.getElementById('rtModalSource').textContent = '来源: ' + (notice.owner ? escapeHtml(notice.owner) : '系统') + (notice.date ? ' · ' + notice.date : '');
}

function closeSignalModal() {
  document.getElementById('rtModalOverlay').classList.remove('open');
  document.getElementById('rtModal').classList.remove('open');
}

function formatNoticeBody(content) {
  // Simple markdown-like formatting
  return escapeHtml(content)
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code style="background:rgba(0,0,0,0.05);padding:1px 5px;border-radius:3px;font-size:12px;font-family:monospace;">$1</code>');
}

// ===== 渲染看板墙 =====
function renderBoardWall() {
  const container = document.getElementById('rtBoardColumns');
  const tasks = rtData.kanban.tasks || [];

  // 按状态分组
  const grouped = {};
  tasks.forEach(task => {
    const status = task.status || 'todo';
    if (!grouped[status]) grouped[status] = [];
    grouped[status].push(task);
  });

  // 定义要显示的列（按顺序）
  const colStatuses = ['ready', 'running', 'blocked', 'done'];

  container.innerHTML = colStatuses.map(status => {
    const cards = grouped[status] || [];
    const label = RT_COLUMN_LABELS[status] || status;

    return `
      <div class="rt-col">
        <div class="rt-col-header">
          <span class="rt-col-title">${label}</span>
          <span class="rt-col-count">${cards.length}</span>
        </div>
        <div class="rt-col-cards">
          ${cards.length > 0 ? cards.map(task => renderTaskCard(task)).join('') : `
            <div class="rt-col-empty">
              <div class="rt-col-empty-icon">📭</div>
              <div>暂无任务</div>
            </div>
          `}
        </div>
      </div>
    `;
  }).join('');
}

function renderTaskCard(task) {
  const assignee = task.assignee || '';
  const assigneeEmoji = RT_AGENTS.find(a => a.id === assignee || a.name === assignee)?.emoji || '👤';
  const priority = task.priority > 0 ? 'high' : 'medium';

  return `
    <div class="rt-task-card" title="${escapeHtml(task.title || '')}">
      <div class="rt-task-title">${escapeHtml(task.title || '无标题')}</div>
      <div class="rt-task-meta">
        ${assignee ? `<span class="rt-task-assignee">${assigneeEmoji} ${escapeHtml(assignee)}</span>` : ''}
        <span class="rt-task-priority ${priority}">${priority === 'high' ? '高' : '中'}</span>
        ${task.created_at ? `<span>${formatRTDate(task.created_at)}</span>` : ''}
      </div>
    </div>
  `;
}

// ===== 空状态 =====
function renderEmptyState() {
  const svgWrap = document.getElementById('rtTableSvg');
  if (svgWrap) {
    svgWrap.innerHTML = `
      <svg viewBox="0 0 360 250">
        <ellipse cx="180" cy="130" rx="150" ry="85" fill="#f0f2f5" stroke="rgba(0,0,0,0.06)" stroke-width="1"/>
        <text x="180" y="135" text-anchor="middle" font-size="12" fill="#bbb">⚡ 等待连接...</text>
      </svg>
    `;
  }
  document.getElementById('rtSignals').innerHTML = '';
  document.getElementById('rtBoardColumns').innerHTML = '';
}

// ===== 工具函数 =====
function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function escapeJson(obj) {
  return JSON.stringify(obj).replace(/'/g, "\\'").replace(/</g, '\\u003C');
}

function formatRTDate(dateStr) {
  if (!dateStr) return '';
  // Handle "2026-05-25" format
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  }
  // Handle timestamp strings
  const ts = parseInt(dateStr);
  if (!isNaN(ts) && ts > 1e8) {
    return new Date(ts * 1000).toLocaleDateString('zh-CN');
  }
  return dateStr;
}

// ===== Auto-refresh =====
let rtRefreshTimer = null;

function startRoundTableAutoRefresh() {
  stopRoundTableAutoRefresh();
  rtRefreshTimer = setInterval(loadRoundTableData, 30000);
}

function stopRoundTableAutoRefresh() {
  if (rtRefreshTimer) {
    clearInterval(rtRefreshTimer);
    rtRefreshTimer = null;
  }
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
  // Will be called by view switching
});