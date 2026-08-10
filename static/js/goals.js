/**
 * 目标/计划视图 — 展示 wiki goals/ 目录下的 goal 类型页面
 * 数据源: /api/wiki/pages (与 wiki.js 共用)
 * 依赖: wiki.js 的 openWikiDetail / escapeHtml, app.js 的 showToast
 */

// 状态元信息
const GOAL_STATUS_META = {
  '进行中': { color: '#10b981', icon: '🔄' },
  '已完成': { color: '#3b82f6', icon: '✅' },
  '已关闭': { color: '#3b82f6', icon: '✅' },
  '已取消': { color: '#9ca3af', icon: '⏹️' },
  '已搁置': { color: '#f59e0b', icon: '⏸️' },
};
const GOAL_DEFAULT_STATUS = { color: '#10b981', icon: '🔄' };

// 从 checklist 统计进度: [x] 完成 / [ ] 待办 / [~] 进行中
function parseGoalProgress(content) {
  const text = content || '';
  const done = (text.match(/\[x\]/gi) || []).length;
  const todo = (text.match(/\[ \]/g) || []).length;
  const doing = (text.match(/\[~\]/g) || []).length;
  const total = done + todo + doing;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return { done, todo, doing, total, pct };
}

// 主入口：加载并渲染目标视图
async function loadGoalsView() {
  const container = document.getElementById('goalsList');
  if (!container) return;
  container.innerHTML = '<div class="goals-loading">⏳ 加载目标中...</div>';
  try {
    const res = await fetch('/api/wiki/pages?t=' + Date.now());
    const data = await res.json();
    renderGoalsView(data);
  } catch (e) {
    container.innerHTML = '<div class="goals-empty">❌ 无法加载目标数据</div>';
    if (typeof showToast === 'function') showToast('❌ 无法加载目标数据', 'error');
  }
}

function renderGoalsView(data) {
  const container = document.getElementById('goalsList');
  if (!container) return;
  const pages = ((data && data.pages) || [])
    .filter(p => p.type === 'goal')
    // 跳过 INDEX.md 总览文件（无目标语义）
    .filter(p => !(p.path || '').toLowerCase().endsWith('index.md'));
  if (pages.length === 0) {
    container.innerHTML = '<div class="goals-empty">🎯 暂无目标/计划</div>';
    return;
  }
  container.innerHTML = '';
  pages.forEach(page => container.appendChild(buildGoalCard(page)));
}

function buildGoalCard(page) {
  const card = document.createElement('div');
  card.className = 'goal-card';
  card.onclick = () => openWikiDetail(page);

  const title = page.title || page.name || 'Untitled';
  const prog = parseGoalProgress(page.content || page.content_preview || '');
  const statusKey = (page.status || '进行中').trim() || '进行中';
  const status = GOAL_STATUS_META[statusKey] || GOAL_DEFAULT_STATUS;

  const createdHtml = page.created
    ? `<span class="goal-meta-item">📅 创建 ${page.created}</span>` : '';
  const targetHtml = page.target
    ? `<span class="goal-meta-item">🎯 目标 ${page.target}</span>` : '';
  const overdue = page.target && prog.total > 0 && prog.done < prog.total
    ? new Date(page.target).getTime() < Date.now() : false;

  card.innerHTML = `
    <div class="goal-card-header">
      <span class="goal-status" style="background:${status.color}18;color:${status.color}">${status.icon} ${escapeHtml(statusKey)}</span>
      ${overdue ? '<span class="goal-overdue">⚠️ 已过目标日</span>' : ''}
    </div>
    <div class="goal-card-title">${escapeHtml(title)}</div>
    <div class="goal-card-meta">${createdHtml}${targetHtml}</div>
    <div class="goal-progress">
      <div class="goal-progress-bar">
        <div class="goal-progress-fill" style="width:${prog.pct}%;background:${status.color}"></div>
      </div>
      <div class="goal-progress-label">${prog.done}/${prog.total} · ${prog.pct}%</div>
    </div>
    <div class="goal-card-footer">
      ${prog.doing > 0 ? `<span class="goal-chip goal-chip-doing">🔄 ${prog.doing} 进行中</span>` : ''}
      ${prog.todo > 0 ? `<span class="goal-chip goal-chip-todo">☐ ${prog.todo} 待办</span>` : ''}
    </div>
  `;
  return card;
}
