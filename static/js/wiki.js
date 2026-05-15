/**
 * Wiki库视图 — 加载、渲染、编辑wiki页面
 */

// 分类配置
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
let currentEditPage = null;

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

  const container = document.getElementById('wikiCategories');
  container.innerHTML = '';

  const sortedCats = Object.entries(data.categories)
    .sort((a, b) => b[1].length - a[1].length);

  for (const [catType, pages] of sortedCats) {
    const config = WIKI_TYPE_CONFIG[catType] || { icon: '📄', color: '#78909c', name: catType };

    let filteredPages = pages;
    if (wikiSearchText) {
      const q = wikiSearchText.toLowerCase();
      filteredPages = pages.filter(p =>
        (p.title || p.name || '').toLowerCase().includes(q) ||
        (p.tags || []).some(t => t.toLowerCase().includes(q)) ||
        (p.content || p.content_preview || '').toLowerCase().includes(q)
      );
    }

    if (filteredPages.length === 0) continue;

    const section = document.createElement('div');
    section.className = 'wiki-category-section';

    const header = document.createElement('div');
    header.className = 'wiki-category-header';
    header.innerHTML = `
      <div class="wiki-category-dot" style="background:${config.color}"></div>
      <span class="wiki-category-icon">${config.icon}</span>
      <span class="wiki-category-name">${config.name}</span>
      <span class="wiki-category-count">${filteredPages.length}</span>
    `;
    section.appendChild(header);

    const list = document.createElement('div');
    list.className = 'wiki-page-list';

    for (const page of filteredPages) {
      const card = document.createElement('div');
      card.className = 'wiki-page-card';
      card.onclick = () => openWikiDetail(page);

      const title = page.title || page.name || 'Untitled';
      // Use full content for preview, display up to 300 chars in card
      const fullContent = page.content || page.content_preview || '';
      const preview = fullContent.substring(0, 300);
      const tags = (page.tags || []).slice(0, 4);
      const updated = page.updated || page.created || '';

      // Simple markdown-to-HTML for card preview (bold, headers, links)
      const previewHtml = simpleMarkdown(preview, page.path);

      card.innerHTML = `
        <div class="wiki-page-card-title">${title}</div>
        <div class="wiki-page-card-preview">${previewHtml}</div>
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
  currentEditPage = page;
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

  // Render full markdown content
  const fullContent = page.content || page.content_preview || '（无内容）';
  document.getElementById('wikiDetailBody').innerHTML = `
    <div class="wiki-detail-content">${renderMarkdown(fullContent, page.path)}</div>
  `;

  // Show edit button
  document.getElementById('wikiEditBtn').style.display = 'inline-flex';

  modal.style.display = 'block';
  overlay.style.display = 'block';
}

function closeWikiDetail() {
  document.getElementById('wikiDetailModal').style.display = 'none';
  document.getElementById('wikiDetailOverlay').style.display = 'none';
}

function enterEditMode() {
  if (!currentEditPage) return;

  const titleEl = document.getElementById('wikiDetailTitle');
  const metaEl = document.getElementById('wikiDetailMeta');
  const bodyEl = document.getElementById('wikiDetailBody');
  const editBtn = document.getElementById('wikiEditBtn');
  const saveBtn = document.getElementById('wikiSaveBtn');
  const cancelBtn = document.getElementById('wikiCancelBtn');

  // Switch to edit mode
  titleEl.innerHTML = `<input type="text" id="wikiEditTitle" value="${currentEditPage.title || currentEditPage.name || ''}" class="wiki-edit-title-input">`;

  // Editable tags
  const tagsStr = (currentEditPage.tags || []).join(', ');
  metaEl.innerHTML = `
    <span class="wiki-edit-label">标签:</span>
    <input type="text" id="wikiEditTags" value="${tagsStr}" class="wiki-edit-tags-input" placeholder="用逗号分隔标签">
    <span class="wiki-detail-path">${currentEditPage.path || ''}</span>
  `;

  // Editable content textarea
  const fullContent = currentEditPage.content || currentEditPage.content_preview || '';
  bodyEl.innerHTML = `
    <textarea id="wikiEditContent" class="wiki-edit-textarea">${escapeHtml(fullContent)}</textarea>
  `;

  editBtn.style.display = 'none';
  saveBtn.style.display = 'inline-flex';
  cancelBtn.style.display = 'inline-flex';
}

function cancelEditMode() {
  // Restore view mode
  openWikiDetail(currentEditPage);
}

async function saveWikiPage() {
  if (!currentEditPage) return;

  const title = document.getElementById('wikiEditTitle').value.trim();
  const tagsStr = document.getElementById('wikiEditTags').value.trim();
  const content = document.getElementById('wikiEditContent').value;

  const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(t => t) : [];

  try {
    const res = await fetch('/api/wiki/page', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        path: currentEditPage.path,
        title: title,
        tags: tags,
        content: content,
      }),
    });

    const result = await res.json();
    if (result.error) {
      showToast('❌ 保存失败: ' + result.error, 'error');
      return;
    }

    showToast('✅ Wiki页面已保存', 'success');

    // Refresh data and reopen
    await loadWikiPages();
    // Find updated page in new data
    const updatedPages = wikiPagesData.pages.filter(p => p.path === currentEditPage.path);
    if (updatedPages.length > 0) {
      currentEditPage = updatedPages[0];
      openWikiDetail(currentEditPage);
    }
  } catch (e) {
    showToast('❌ 保存失败: ' + e.message, 'error');
  }
}

// ---- Markdown rendering ----

function simpleMarkdown(text, pagePath) {
  // Minimal renderer for card preview
  // pagePath: e.g. "projects/marketization-kpi-2026.md" — used to resolve local file links
  const pageDir = pagePath ? pagePath.replace(/[^/]*$/, '') : '';
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/## (.+)/g, '<span class="wiki-md-h2">$1</span>')
    .replace(/### (.+)/g, '<span class="wiki-md-h3">$1</span>')
    .replace(/\[\[([^\]]+)\]\]/g, '<a class="wiki-md-link" onclick="openWikiLink(\'$1\')">⟶$1</a>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
      // Local file link (not http/https) → rewrite to /api/wiki/file/
      if (!url.match(/^https?:\/\//i)) {
        const resolvedUrl = '/api/wiki/file/' + (pageDir + url);
        return '<a class="wiki-md-external" href="' + resolvedUrl + '" target="_blank">' + linkText + '</a>';
      }
      return '<a class="wiki-md-external" href="' + url + '" target="_blank">' + linkText + '</a>';
    })
    .replace(/\n/g, '<br>');
}

function renderMarkdown(text, pagePath) {
  // Full markdown renderer for detail view
  // pagePath: e.g. "projects/marketization-kpi-2026.md" — used to resolve local file links
  const pageDir = pagePath ? pagePath.replace(/[^/]*$/, '') : '';
  let html = escapeHtml(text);

  // Headers (### first to avoid ## matching inside ###)
  html = html.replace(/^### (.+)$/gm, '<h4 class="wiki-md-h4">$1</h4>');
  html = html.replace(/^## (.+)$/gm, '<h3 class="wiki-md-h3">$1</h3>');
  html = html.replace(/^# (.+)$/gm, '<h2 class="wiki-md-h2">$1</h2>');

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  // Italic
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Wikilinks [[name]] — clickable, opens matching wiki page
  html = html.replace(/\[\[([^\]]+)\]\]/g, (match, name) => {
    return '<a class="wiki-md-link" onclick="openWikiLink(\'' + name.replace(/'/g, "\\'") + '\')">⟶ ' + name + '</a>';
  });

  // Standard markdown links [text](url) — rewrite local file links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
    if (!url.match(/^https?:\/\//i)) {
      const resolvedUrl = '/api/wiki/file/' + (pageDir + url);
      return '<a class="wiki-md-external" href="' + resolvedUrl + '" target="_blank">' + linkText + '</a>';
    }
    return '<a class="wiki-md-external" href="' + url + '" target="_blank">' + linkText + '</a>';
  });

  // Lists (- item)
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
  // Wrap consecutive <li> in <ul>
  html = html.replace(/(<li>.*<\/li>\n?)+/g, (match) => `<ul class="wiki-md-list">${match}</ul>`);

  // Numbered lists (1. item)
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

  // Horizontal rule
  html = html.replace(/^---$/gm, '<hr class="wiki-md-hr">');

  // Paragraphs: double newline → paragraph break
  html = html.replace(/\n\n+/g, '</p><p>');
  // Single newline within paragraph
  html = html.replace(/\n/g, '<br>');

  // Wrap in paragraph
  html = '<p>' + html + '</p>';

  // Clean up empty paragraphs
  html = html.replace(/<p><\/p>/g, '');
  html = html.replace(/<p><br>/g, '<p>');
  html = html.replace(/<br><\/p>/g, '</p>');

  return html;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ---- Wiki link navigation ----

function openWikiLink(linkName) {
  if (!wikiPagesData || !wikiPagesData.pages) {
    showToast('❌ Wiki数据未加载', 'error');
    return;
  }

  const q = linkName.toLowerCase();
  const pages = wikiPagesData.pages;

  // 1. Exact title/name match
  let match = pages.find(p =>
    (p.title || p.name || '').toLowerCase() === q
  );

  // 2. Path-based exact match (slug → filename)
  if (!match) {
    match = pages.find(p =>
      (p.path || '').toLowerCase() === q + '.md' ||
      (p.path || '').toLowerCase() === q
    );
  }

  // 3. Path contains slug as whole segment
  if (!match) {
    match = pages.find(p =>
      (p.path || '').toLowerCase().split('/').some(seg => seg === q || seg === q + '.md')
    );
  }

  // 4. Title/name contains linkName as substring
  if (!match) {
    match = pages.find(p =>
      (p.title || p.name || '').toLowerCase().includes(q)
    );
  }

  // 5. linkName contains title/name as substring (reverse)
  if (!match) {
    match = pages.find(p =>
      q.includes((p.title || p.name || '').toLowerCase())
    );
  }

  // 6. Path loosely contains linkName
  if (!match) {
    match = pages.find(p =>
      (p.path || '').toLowerCase().includes(q)
    );
  }

  if (match) {
    openWikiDetail(match);
  } else {
    showToast('⚠️ 页面 "' + linkName + '" 不存在或未索引', 'warning');
  }
}