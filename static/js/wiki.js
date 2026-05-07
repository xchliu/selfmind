/**
 * Wiki库视图 — 加载和渲染wiki页面列表
 */

// 分类配置：图标、颜色、中文名
const WIKI_TYPE_CONFIG = {
  entity:      { icon: '🏢', color: '#e74c3c', name: '实体' },
  concept:     { icon: '💡', color: '#3498db', name: '概念' },
  comparison:  { icon: '⚖️', color: '#2ecc71', name: '对比分析' },
  query:       { icon: '🔍', color: '#f39c12', name: '查询结果' },
  summary:     { icon: '📝', color: '#9b59b6', name: '摘要' },
  uncategorized: { icon: '📄', color: '#78909c', name: '未分类' },
  page:        { icon: '📑', color: '#607d8b', name: '页面' },
};

let wikiPagesData = null;
let wikiSearchText = '';

async function loadWikiPages() {
  try {
    const res = await fetch('/api/wiki/pages?t=' + Date.now());
    wikiPagesData = await res.json();
  } catch (e) {
    showToast('❌ 无法加载Wiki数据', 'error');
    return;
  }
  renderWikiView(wikiPagesData);
}

function renderWikiView(data) {
  if (!data || !data.categories) return;

  // 统计栏
  const statsEl = document.getElementById('wikiStats');
  const total = data.total || 0;
  const catCount = Object.keys(data.categories).length;
  statsEl.innerHTML = `
    <div class="wiki-stat-chip">
      <span class="wiki-stat-num">${total}</span>
      <span class="wiki-stat-label">页面</span>
    </div>
    <div class="wiki-stat-chip">
      <span class="wiki-stat-num">${catCount}</span>
      <span class="wiki-stat-label">分类</span>
    </div>
  `;

  // 分类卡片
  const container = document.getElementById('wikiCategories');
  container.innerHTML = '';

  // 排序：按分类中页面数量降序
  const sortedCats = Object.entries(data.categories)
    .sort((a, b) => b[1].length - a[1].length);

  for (const [catType, pages] of sortedCats) {
    const config = WIKI_TYPE_CONFIG[catType] || { icon: '📄', color: '#78909c', name: catType };

    // 搜索过滤
    let filteredPages = pages;
    if (wikiSearchText) {
      const q = wikiSearchText.toLowerCase();
      filteredPages = pages.filter(p =>
        (p.title || p.name || '').toLowerCase().includes(q) ||
        (p.tags || []).some(t => t.toLowerCase().includes(q)) ||
        (p.content_preview || '').toLowerCase().includes(q)
      );
    }

    if (filteredPages.length === 0) continue;

    const section = document.createElement('div');
    section.className = 'wiki-category-section';

    // 分类头
    const header = document.createElement('div');
    header.className = 'wiki-category-header';
    header.innerHTML = `
      <div class="wiki-category-dot" style="background:${config.color}"></div>
      <span class="wiki-category-icon">${config.icon}</span>
      <span class="wiki-category-name">${config.name}</span>
      <span class="wiki-category-count">${filteredPages.length}</span>
    `;
    section.appendChild(header);

    // 页面卡片列表
    const list = document.createElement('div');
    list.className = 'wiki-page-list';

    for (const page of filteredPages) {
      const card = document.createElement('div');
      card.className = 'wiki-page-card';
      card.onclick = () => openWikiDetail(page);

      const title = page.title || page.name || 'Untitled';
      const preview = (page.content_preview || '').substring(0, 120);
      const tags = (page.tags || []).slice(0, 4);
      const updated = page.updated || page.created || '';

      card.innerHTML = `
        <div class="wiki-page-card-title">${title}</div>
        <div class="wiki-page-card-preview">${preview}</div>
        <div class="wiki-page-card-footer">
          <div class="wiki-page-card-tags">
            ${tags.map(t => `<span class="wiki-tag" style="background:${config.color}22;color:${config.color}">${t}</span>`).join('')}
          </div>
          ${updated ? `<span class="wiki-page-card-date">${updated}</span>` : ''}
        </div>
      `;
      list.appendChild(card);
    }

    section.appendChild(list);
    container.appendChild(section);
  }

  // 无结果
  if (wikiSearchText && container.children.length === 0) {
    container.innerHTML = `<div class="wiki-empty">没有找到匹配 "${wikiSearchText}" 的Wiki页面</div>`;
  }
}

function wikiSearchFilter(value) {
  wikiSearchText = value.trim();
  if (wikiPagesData) {
    renderWikiView(wikiPagesData);
  }
}

function openWikiDetail(page) {
  const modal = document.getElementById('wikiDetailModal');
  const overlay = document.getElementById('wikiDetailOverlay');
  const config = WIKI_TYPE_CONFIG[page.type] || { icon: '📄', color: '#78909c', name: page.type };

  document.getElementById('wikiDetailTitle').textContent = page.title || page.name || 'Untitled';
  document.getElementById('wikiDetailMeta').innerHTML = `
    <span class="wiki-detail-type" style="background:${config.color}22;color:${config.color}">${config.icon} ${config.name}</span>
    ${(page.tags || []).map(t => `<span class="wiki-tag" style="background:${config.color}22;color:${config.color}">${t}</span>`).join('')}
    ${page.updated ? `<span class="wiki-detail-date">更新: ${page.updated}</span>` : ''}
    ${page.created ? `<span class="wiki-detail-date">创建: ${page.created}</span>` : ''}
    <span class="wiki-detail-path">${page.path || ''}</span>
  `;

  // 渲染Markdown内容预览
  const preview = page.content_preview || '（无内容预览）';
  document.getElementById('wikiDetailBody').innerHTML = `<div class="wiki-detail-content">${escapeHtml(preview)}</div>`;

  modal.style.display = 'block';
  overlay.style.display = 'block';
}

function closeWikiDetail() {
  document.getElementById('wikiDetailModal').style.display = 'none';
  document.getElementById('wikiDetailOverlay').style.display = 'none';
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}