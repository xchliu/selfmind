/**
 * SelfMind 社交图谱
 * 展示苏格拉底的社交网络：AI Agent 之间 + AI 与人的关系
 */

let socialGraphData = null;
let socialSimulation = null;
let socialZoom = null;
let _lastClickedId = null; // 防止异步 fetch 覆盖

// 团队配色
const TEAM_COLORS = {
  core: { bg: '#e74c3c', border: '#c0392b', name: '核心' },
  ai: { bg: '#3498db', border: '#2980b9', name: 'AI部门' },
  lab: { bg: '#2ecc71', border: '#27ae60', name: '实验室' },
  platform: { bg: '#f39c12', border: '#d68910', name: '平台' },
  product: { bg: '#9b59b6', border: '#8e44ad', name: '产品' },
  project: { bg: '#1abc9c', border: '#16a085', name: '项目' },
  external: { bg: '#95a5a6', border: '#7f8c8d', name: '外部' },
};

// 社交等级颜色
const RANK_COLORS = {
  'A': '#e74c3c',
  'B': '#f39c12',
  'C': '#95a5a6',
  'core': '#e74c3c',
  'self': '#3498db',
  'peer': '#1abc9c',
};

// 边类型
const EDGE_TYPES = {
  ai_assistant: { color: '#3498db', opacity: 0.4, dashed: false },
  collaboration: { color: '#1abc9c', opacity: 0.5, dashed: true },
  management: { color: '#e74c3c', opacity: 0.2, dashed: false },
  social: { color: '#9b59b6', opacity: 0.3, dashed: false },
};

async function loadSocialGraph() {
  try {
    const resp = await fetch('/api/social/graph');
    const data = await resp.json();
    socialGraphData = data;
    renderSocialGraph(data);
    renderSocialLegend(data);
    updateSocialStats(data);
  } catch (err) {
    console.error('Failed to load social graph:', err);
    document.getElementById('socialStats').textContent = '❌ 加载失败';
  }
}

function renderSocialGraph(data) {
  const svg = d3.select('#socialGraphSvg');
  svg.selectAll('*').remove();

  const container = document.getElementById('socialGraphContainer');
  const width = container.clientWidth;
  const height = container.clientHeight;

  svg.attr('width', width).attr('height', height);

  // 缩放
  const g = svg.append('g');
  socialZoom = d3.zoom()
    .scaleExtent([0.2, 4])
    .on('zoom', (event) => g.attr('transform', event.transform));
  svg.call(socialZoom);

  // 力导向
  const nodes = data.nodes.map(d => ({ ...d }));
  const edges = data.edges.map(d => ({ ...d }));

  // 节点半径映射 — 最小18px(名字完整可见),最大35px
  const radiusScale = d3.scaleSqrt()
    .domain([0, d3.max(nodes, d => d.interaction_count || 1)])
    .range([18, 35]);

  socialSimulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(d => {
      if (d.type === 'ai_assistant') return 80;
      if (d.type === 'management') return 120;
      if (d.type === 'collaboration') return 100;
      if (d.type === 'social') return 80 + (1 - Math.min(d.weight, 5) / 5) * 80;
      return 100;
    }).strength(d => {
      if (d.type === 'ai_assistant') return 0.5;
      if (d.type === 'management') return 0.3;
      if (d.type === 'collaboration') return 0.4;
      if (d.type === 'social') return Math.min(d.weight, 5) / 10;
      return 0.1;
    }))
    .force('charge', d3.forceManyBody().strength(d => {
      if (d.id === 'tange') return -400;
      if (d.type === 'agent') return -300;
      return -150;
    }))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(d => {
      if (d.id === 'tange') return 55;
      if (d.type === 'agent') return 45;
      return (radiusScale(d.interaction_count || 1) + 15);
    }));

  // 边
  const link = g.append('g')
    .selectAll('line')
    .data(edges)
    .join('line')
    .attr('stroke', d => EDGE_TYPES[d.type]?.color || '#ccc')
    .attr('stroke-opacity', d => {
      if (d.type === 'social') return Math.min(d.weight, 5) / 10 * 0.6;
      return EDGE_TYPES[d.type]?.opacity || 0.2;
    })
    .attr('stroke-width', d => {
      if (d.type === 'social') return Math.max(0.5, Math.min(d.weight, 5) * 0.8);
      if (d.type === 'ai_assistant') return 2;
      if (d.type === 'collaboration') return 1.5;
      return 1;
    })
    .attr('stroke-dasharray', d => EDGE_TYPES[d.type]?.dashed ? '4,3' : 'none');

  // 节点 group
  const node = g.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .call(d3.drag()
      .on('start', (event, d) => {
        if (!event.active) socialSimulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on('end', (event, d) => {
        if (!event.active) socialSimulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      }))
    .on('click', (event, d) => showSocialDetail(d));

  // 节点圆
  node.append('circle')
    .attr('r', d => {
      if (d.id === 'tange' || d.type === 'agent') return 32;
      return radiusScale(d.interaction_count || 1);
    })
    .attr('fill', d => getNodeColor(d))
    .attr('stroke', d => {
      if (d.id === 'tange') return '#c0392b';
      if (d.type === 'agent') return '#2980b9';
      return TEAM_COLORS[d.team]?.border || '#bbb';
    })
    .attr('stroke-width', d => {
      if (d.id === 'tange' || d.type === 'agent') return 3;
      if (d.has_interacted) return 2.5;
      return 1.5;
    })
    .style('cursor', 'pointer');

  // 节点文字
  node.append('text')
    .text(d => d.name)
    .attr('text-anchor', 'middle')
    .attr('dy', '0.35em')
    .attr('fill', d => (d.id === 'tange' || d.type === 'agent' || d.has_interacted) ? '#fff' : '#555')
    .attr('font-size', d => {
      if (d.id === 'tange' || d.type === 'agent') return 14;
      return 12;
    })
    .attr('font-weight', d => (d.id === 'tange' || d.type === 'agent') ? '700' : '500')
    .style('pointer-events', 'none');

  // tick
  socialSimulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });

  // 双击放大/重置
  svg.on('dblclick.zoom', null);
  svg.on('dblclick', () => {
    svg.transition().duration(500).call(socialZoom.transform, d3.zoomIdentity);
  });
}

function getNodeColor(d) {
  if (d.id === 'tange') return '#e74c3c';
  if (d.type === 'agent') return '#3498db';
  const team = TEAM_COLORS[d.team];
  if (team) {
    if (d.has_interacted) return team.bg;
    return team.bg + '99'; // 透明度
  }
  return '#95a5a6';
}

function renderSocialLegend(data) {
  const legend = document.getElementById('socialLegend');
  let html = '<span style="font-weight:600;margin-right:4px;">🎨 团队:</span>';

  // 团队图例
  for (const [key, val] of Object.entries(data.teams || TEAM_COLORS)) {
    html += `<span style="display:inline-flex;align-items:center;gap:4px;margin-right:12px;">
      <span style="width:10px;height:10px;border-radius:50%;background:${val.color};display:inline-block;"></span>
      ${val.name}
    </span>`;
  }

  html += '<span style="margin:0 8px;color:#ddd;">|</span>';

  // 节点类型图例
  html += `<span style="display:inline-flex;align-items:center;gap:4px;margin-right:12px;">
    <span style="width:10px;height:10px;border-radius:50%;background:#e74c3c;display:inline-block;"></span>
    核心</span>`;
  html += `<span style="display:inline-flex;align-items:center;gap:4px;margin-right:12px;">
    <span style="width:10px;height:10px;border-radius:50%;background:#3498db;display:inline-block;"></span>
    AI</span>`;
  html += `<span style="display:inline-flex;align-items:center;gap:4px;margin-right:12px;">
    <span style="width:10px;height:10px;border-radius:50%;background:#2ecc71;display:inline-block;"></span>
    已互动</span>`;
  html += `<span style="display:inline-flex;align-items:center;gap:4px;margin-right:12px;">
    <span style="width:10px;height:10px;border-radius:50%;background:#2ecc7199;display:inline-block;"></span>
    未互动</span>`;

  html += '<span style="margin:0 8px;color:#ddd;">|</span>';
  html += `<span style="color:#999;">🖱️ 拖拽节点 · 🔍 滚轮缩放 · 双击重置</span>`;

  legend.innerHTML = html;
}

function updateSocialStats(data) {
  const stats = document.getElementById('socialStats');
  stats.textContent = `👤 ${data.total_people} 人 · 🤖 ${data.total_agents} 个AI · 💬 ${data.total_interacted} 已互动 · 更新 ${data.updated}`;
}

function showSocialDetail(d) {
  const panel = document.getElementById('socialDetailPanel');
  const container = document.getElementById('socialGraphContainer');
  const dot = document.getElementById('socialDetailDot');
  const name = document.getElementById('socialDetailName');
  const info = document.getElementById('socialDetailInfo');
  const body = document.getElementById('socialDetailBody');

  panel.style.display = 'block';
  container.style.marginRight = '400px';

  dot.style.background = getNodeColor(d);

  if (d.id === 'tange') {
    name.textContent = `${d.name}（${d.title}）`;
    info.textContent = `核心 · ${d.department}`;
    body.innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div style="background:#f8f9fa;padding:8px 12px;border-radius:8px;text-align:center;">
          <div style="font-size:11px;color:#888;">管理的</div>
          <div style="font-weight:600;color:#2d3436;margin-top:2px;">${socialGraphData?.total_people || 0} 人</div>
        </div>
        <div style="background:#f8f9fa;padding:8px 12px;border-radius:8px;text-align:center;">
          <div style="font-size:11px;color:#888;">AI助手</div>
          <div style="font-weight:600;color:#2d3436;margin-top:2px;">${socialGraphData?.total_agents || 0} 个</div>
        </div>
      </div>
    `;
  } else if (d.type === 'agent') {
    name.textContent = d.name;
    info.textContent = `AI助手 · 协作伙伴`;
    body.innerHTML = `<div style="color:#555;">与坦哥和团队成员协作，处理任务分发与调研</div>`;
  } else {
    // 人物节点 — 基本信息 + 从 entity wiki 加载
    name.textContent = d.name;
    const rankLabel = { A: '主动维护', B: '回应维护', C: '待建立', core: '核心', self: '自我', peer: '伙伴' };
    info.textContent = `${d.department || '未知'} · 社交等级 ${d.social_rank}（${rankLabel[d.social_rank] || '未知'}）`;

    body.innerHTML = '<div style="color:#999;text-align:center;padding:12px;">🔄 加载详情...</div>';
    _lastClickedId = d.id;

    // 异步获取 wiki entity 内容（用 _lastClickedId 防覆盖）
    zoomToNode(d);
    fetchEntityDetail(d.id);
  }

  // 非人物节点已同步渲染完
  if (d.id === 'tange' || d.type === 'agent') {
    _lastClickedId = d.id;
    zoomToNode(d);
  }
}

function hideSocialDetail() {
  document.getElementById('socialDetailPanel').style.display = 'none';
  document.getElementById('socialGraphContainer').style.marginRight = '0';
  _lastClickedId = null;
}

function zoomToNode(d) {
  if (socialZoom && socialGraphData) {
    const svg = d3.select('#socialGraphSvg');
    const container = document.getElementById('socialGraphContainer');
    const width = container.clientWidth;
    const height = container.clientHeight;
    const scale = 1.5;
    const tx = width / 2 - d.x * scale;
    const ty = height / 2 - d.y * scale;
    svg.transition().duration(500).call(
      socialZoom.transform,
      d3.zoomIdentity.translate(tx, ty).scale(scale)
    );
  }
}

async function fetchEntityDetail(entityId) {
  const body = document.getElementById('socialDetailBody');
  try {
    // 防止异步覆盖：如果用户已经点了别的节点，不执行
    if (_lastClickedId !== entityId) return;
    const resp = await fetch('/api/social/entity/' + encodeURIComponent(entityId));
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();

    // 第二次检查：API 返回期间用户可能已经点了别人
    if (_lastClickedId !== entityId) return;

    let html = '';

    // 基本信息 key-value 格子
    const basicInfo = data.basic_info || {};
    if (Object.keys(basicInfo).length > 0) {
      html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:10px;">';
      for (const [key, val] of Object.entries(basicInfo)) {
        if (key === '企微 userid') continue; // wecom_id 已在 meta 中
        html += `<div style="background:#f8f9fa;padding:6px 10px;border-radius:6px;">
          <div style="font-size:10px;color:#888;">${key}</div>
          <div style="font-size:13px;font-weight:500;color:#2d3436;margin-top:1px;">${escapeHtml(val)}</div>
        </div>`;
      }
      html += '</div>';
    }

    // 交互状态（已互动/未互动）
    const meta = data.meta || {};
    if (meta.last_interaction) {
      html += `<div style="display:flex;gap:12px;margin-bottom:10px;flex-wrap:wrap;">
        <span style="background:#d4edda;color:#155724;padding:2px 8px;border-radius:4px;font-size:11px;">✅ 已互动</span>
        <span style="color:#888;font-size:12px;">最近: ${meta.last_interaction}</span>
        ${meta.interaction_count ? `<span style="color:#888;font-size:12px;">互动 ${meta.interaction_count} 次</span>` : ''}
        ${meta.social_rank ? `<span style="background:#e8f4fd;color:#2980b9;padding:2px 8px;border-radius:4px;font-size:11px;">等级 ${meta.social_rank}</span>` : ''}
        ${meta.wecom_id ? `<span style="background:#f0f0f0;color:#666;padding:2px 8px;border-radius:4px;font-size:11px;">💬 ${meta.wecom_id}</span>` : ''}
      </div>`;
    } else {
      html += `<div style="display:flex;gap:12px;margin-bottom:10px;">
        <span style="background:#fff3cd;color:#856404;padding:2px 8px;border-radius:4px;font-size:11px;">⏳ 未互动</span>
        <span style="color:#888;font-size:12px;">档案已建，待首次联系</span>
      </div>`;
    }

    // next_action 待办
    if (meta.next_action) {
      html += `<div style="background:#fff3cd;padding:8px 12px;border-radius:8px;font-size:12px;color:#856404;margin-bottom:10px;">
        📋 <span style="font-weight:500;">待办:</span> ${escapeHtml(meta.next_action)}
      </div>`;
    }

    // tags 社交关键词
    if (meta.tags && meta.tags.length > 0) {
      html += '<div style="margin-bottom:10px;"><span style="font-size:11px;color:#888;">🏷️ </span>';
      for (const tag of meta.tags) {
        html += `<span style="display:inline-block;background:#e8f4fd;color:#2980b9;padding:2px 8px;border-radius:10px;font-size:11px;margin:2px 3px;">${escapeHtml(tag)}</span>`;
      }
      html += '</div>';
    }

    // 正文 sections（关系、背景、交互记录、待跟进等）
    const sections = data.sections || {};
    const sectionOrder = ['关系', '背景', '交互记录', '待跟进'];
    const sectionIcons = { '关系': '🤝', '背景': '📖', '交互记录': '📝', '待跟进': '✅' };

    for (const secName of sectionOrder) {
      const secContent = sections[secName];
      if (!secContent) continue;
      const icon = sectionIcons[secName] || '📄';

      // 判断内容是否太长需要折叠
      const lines = secContent.split('\n').filter(l => l.trim());
      const isLong = lines.length > 6;

      html += `<div style="margin-bottom:10px;">
        <div style="font-weight:600;font-size:13px;color:#2d3436;margin-bottom:4px;">${icon} ${secName}</div>
        <div style="font-size:12px;color:#555;line-height:1.6;${isLong ? 'max-height:120px;overflow:hidden;' : ''}" ${isLong ? 'id="sec_' + secName + '"' : ''}>`;

      if (secName === '交互记录') {
        // 交互记录按 H3 标题分段展示
        const parts = secContent.split(/\n(?=###\s)/);
        for (const part of parts) {
          const trimmed = part.trim();
          if (!trimmed) continue;
          // H3 标题加粗
          const formatted = trimmed
            .replace(/^###\s+(.+)$/gm, '<div style="font-weight:600;color:#2d3436;margin:4px 0 2px;">$1</div>')
            .replace(/- \*\*(.+?)\*\*[：:]?\s*(.+)/g, '<span style="font-weight:500;">$1：</span>$2<br>');
          html += `<div style="background:#f8f9fa;padding:6px 10px;border-radius:6px;margin:4px 0;">${formatted}</div>`;
        }
      } else if (secName === '待跟进') {
        // 待跟进列表转成 checked/unchecked
        html += secContent
          .replace(/^- \[ \] (.*)$/gm, '<div style="display:flex;align-items:flex-start;gap:4px;margin:2px 0;"><span style="color:#ccc;">⬜</span><span>$1</span></div>')
          .replace(/^- \[x\] (.*)$/gm, '<div style="display:flex;align-items:flex-start;gap:4px;margin:2px 0;color:#27ae60;"><span>✅</span><span style="text-decoration:line-through;">$1</span></div>')
          .replace(/- \*\*(.+?)\*\*[：:]?\s*(.+)/g, '<span style="font-weight:500;">$1：</span>$2<br>');
      } else {
        // 关系、背景等 — 简单格式化作文本块
        html += secContent
          .replace(/- \*\*(.+?)\*\*[：:]?\s*(.+)/g, '<span style="font-weight:500;">$1：</span>$2<br>')
          .replace(/\n\n/g, '<br><br>');
      }

      html += `</div>`;
      if (isLong) {
        html += `<button onclick="var el=document.getElementById('sec_${secName}');el.style.maxHeight=el.style.maxHeight==='none'?'120px':'none';this.textContent=this.textContent==='展开更多'?'收起':'展开更多'" style="border:none;background:none;color:#3498db;cursor:pointer;font-size:12px;padding:2px 0;">展开更多</button>`;
      }
      html += `</div>`;
    }

    body.innerHTML = html || '<div style="color:#888;text-align:center;padding:12px;">暂无详细信息</div>';
  } catch (err) {
    console.error('Failed to load entity detail:', err);
    body.innerHTML = '<div style="color:#e74c3c;text-align:center;padding:12px;">❌ 加载详情失败</div>';
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// 页面 resize 处理
window.addEventListener('resize', () => {
  if (document.getElementById('socialDashboard').style.display === 'block') {
    loadSocialGraph();
  }
});