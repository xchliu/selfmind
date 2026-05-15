// ========== 衰减曲线可视化 ==========

const DECAY_COLORS = {
  security: '#e74c3c', identity: '#e74c3c',
  autobiographical: '#6c5ce7', procedural: '#00b894',
  project: '#0984e3', skill: '#00cec9',
  social: '#fdcb6e', semantic: '#f0932b',
  entity: '#a29bfe', concept: '#fd79a8',
  config: '#636e72', working: '#dfe6e9',
  episodic: '#ffeaa7', failure: '#ff7675',
  summary: '#b2bec3', comparison: '#55efc4',
  query: '#74b9ff', spatial: '#fab1a0'
};

const DECAY_NAMES = {
  security: '安全', identity: '身份',
  autobiographical: '自传', procedural: '程序',
  project: '项目', skill: '技能',
  social: '社交', semantic: '语义',
  entity: '实体', concept: '概念',
  config: '配置', working: '工作',
  episodic: '情境', failure: '教训',
  summary: '摘要', comparison: '对比',
  query: '查询', spatial: '空间'
};

const TYPE_FACTOR = {
  memory: 0.7, skill: 0.5, wiki: 0.4, honcho_obs: 0.3
};

// 衰减公式参数（跟后端一致）
const DECAY_PARAMS = {
  importance_w: 1.0,
  recency_w: 0.4,
  type_factor_w: 0.3,
  base_w: 0.3,
  decay_rate: 0.03  // exp(-0.03 * days_since)
};

function renderDecayCurve() {
  if (!healthEntries || healthEntries.length === 0) {
    document.getElementById('decayCurveChart').innerHTML = '<div style="color:#999;text-align:center;padding:40px">请先加载健康数据</div>';
    return;
  }

  // 按分类聚合平均衰减
  const catData = {};
  healthEntries.forEach(function(e) {
    const cat = e.primary_cat || 'unknown';
    const ds = e.decay_score || 0;
    if (!catData[cat]) catData[cat] = { count: 0, decays: [] };
    catData[cat].count++;
    catData[cat].decays.push(ds);
  });

  const catAvg = [];
  for (const cat in catData) {
    const avg = catData[cat].decays.reduce(function(a,b) { return a+b; }, 0) / catData[cat].decays.length;
    catAvg.push({ cat: cat, avg: avg, count: catData[cat].count });
  }
  catAvg.sort(function(a, b) { return b.avg - a.avg; });

  renderDecayOverview(catAvg);
  // 不再渲染bucket和timeline，总图简化为只有一个overview
  document.getElementById('decayBucketChart').innerHTML = '';
  document.getElementById('decayTimelineChart').innerHTML = '';
}

function renderDecayOverview(catAvg) {
  // 横向条形图：每个分类一行，从左到右表示衰减强度
  const n = catAvg.length;
  const barH = 28;
  const gap = 6;
  const labelW = 120;
  const chartW = 600;
  const H = n * (barH + gap) + 50;
  const W = labelW + chartW + 80;

  let html = '<div class="decay-overview-container">';
  html += '<div class="decay-overview-title">记忆衰减总览</div>';
  html += '<div class="decay-overview-desc">各分类平均衰减强度，右端标注百分比</div>';

  // SVG条形图
  let svgParts = [];
  // 阈值线
  const thresholdX = labelW + chartW * 0.5;
  svgParts.push('<line x1="' + thresholdX + '" y1="0" x2="' + thresholdX + '" y2="' + (H-20) + '" stroke="#f0932b" stroke-width="1.5" stroke-dasharray="4,3" opacity="0.6"/>');
  svgParts.push('<text x="' + (thresholdX+4) + '" y="14" font-size="10" fill="#f0932b">阈值 50%</text>');

  catAvg.forEach(function(d, i) {
    const y = 24 + i * (barH + gap);
    const color = DECAY_COLORS[d.cat] || '#636e72';
    const name = DECAY_NAMES[d.cat] || d.cat;
    const pct = (d.avg * 100).toFixed(0);
    const barWidth = Math.max(d.avg * chartW, 4);
    const dcClass = d.avg > 0.5 ? 'green' : d.avg > 0.2 ? 'yellow' : 'red';

    // 分类标签
    svgParts.push('<text x="' + (labelW - 8) + '" y="' + (y + barH/2 + 5) + '" text-anchor="end" font-size="13" fill="' + color + '" font-weight="500">' + name + '</text>');

    // 背景条
    svgParts.push('<rect x="' + labelW + '" y="' + y + '" width="' + chartW + '" height="' + barH + '" rx="4" fill="rgba(0,0,0,0.04)"/>');

    // 填充条
    svgParts.push('<rect x="' + labelW + '" y="' + y + '" width="' + barWidth + '" height="' + barH + '" rx="4" fill="' + color + '" opacity="0.7"/>');

    // 百分比标注
    svgParts.push('<text x="' + (labelW + barWidth + 8) + '" y="' + (y + barH/2 + 5) + '" font-size="12" fill="#333" font-weight="600">' + pct + '%</text>');

    // 条目数
    svgParts.push('<text x="' + (labelW + barWidth + 50) + '" y="' + (y + barH/2 + 5) + '" font-size="10" fill="#999">' + d.count + '条</text>');
  });

  html += '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" preserveAspectRatio="xMidYMid meet" style="max-height:' + (H + 20) + 'px">';
  html += svgParts.join('');
  html += '</svg>';
  html += '</div>';

  document.getElementById('decayCurveChart').innerHTML = html;
}

// ========== 单条记忆衰减曲线 ==========

function showEntryDecayCurve(entryId) {
  const entry = healthEntries.find(function(e) { return e.id === entryId; });
  if (!entry) return;

  const importance = entry.importance || 0.5;
  const typeFactor = TYPE_FACTOR[entry.entry_type] || 0.5;
  const createdAt = entry.first_seen_at || entry.updated_at || entry.created_at || new Date().toISOString();
  const now = new Date();
  const created = new Date(createdAt);
  const daysSinceCreation = Math.max((now - created) / 86400000, 0);

  // 模拟衰减曲线：从创建到现在 + 预测未来30天
  const futureDays = 30;
  const totalDays = daysSinceCreation + futureDays;
  const points = [];

  for (let day = 0; day <= totalDays; day += 1) {
    const recency = Math.exp(-0.03 * Math.max(day, 0));
    const decay = importance * (DECAY_PARAMS.base_w + DECAY_PARAMS.recency_w * recency + DECAY_PARAMS.type_factor_w * typeFactor);
    points.push({ day: day, decay: Math.min(decay, 1.0), isPast: day <= daysSinceCreation });
  }

  const cat = entry.primary_cat || 'unknown';
  const color = DECAY_COLORS[cat] || '#636e72';
  const name = DECAY_NAMES[cat] || cat;
  const preview = (entry.content_preview || '').substring(0, 80);

  // SVG绘制
  const W = 500, H = 220;
  const padL = 50, padR = 30, padT = 30, padB = 40;
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;
  const maxDay = totalDays;

  let svgParts = [];

  // 背景网格
  for (let i = 0; i <= 5; i++) {
    const y = padT + chartH * (1 - i/5);
    const val = (i/5 * 100).toFixed(0);
    svgParts.push('<line x1="' + padL + '" y1="' + y + '" x2="' + (W-padR) + '" y2="' + y + '" stroke="#eee" stroke-width="1"/>');
    svgParts.push('<text x="' + (padL-8) + '" y="' + (y+4) + '" text-anchor="end" font-size="10" fill="#999">' + val + '%</text>');
  }

  // 阈值线
  const thresholdY = padT + chartH * (1 - 0.5);
  svgParts.push('<line x1="' + padL + '" y1="' + thresholdY + '" x2="' + (W-padR) + '" y2="' + thresholdY + '" stroke="#f0932b" stroke-width="1" stroke-dasharray="4,3" opacity="0.5"/>');
  svgParts.push('<text x="' + (W-padR) + '" y="' + (thresholdY-6) + '" text-anchor="end" font-size="9" fill="#f0932b">50%</text>');

  // "现在"标记线
  const nowX = padL + (daysSinceCreation / maxDay) * chartW;
  svgParts.push('<line x1="' + nowX + '" y1="' + padT + '" x2="' + nowX + '" y2="' + (padT+chartH) + '" stroke="#1e90ff" stroke-width="1.5" stroke-dasharray="3,2"/>');
  svgParts.push('<text x="' + nowX + '" y="' + (padT-8) + '" text-anchor="middle" font-size="10" fill="#1e90ff" font-weight="600">现在</text>');

  // 过去曲线（实线）
  const pastPoints = points.filter(function(p) { return p.isPast; });
  if (pastPoints.length > 0) {
    let pastPath = '';
    pastPoints.forEach(function(p, i) {
      const x = padL + (p.day / maxDay) * chartW;
      const y = padT + chartH * (1 - p.decay);
      pastPath += (i === 0 ? 'M ' : ' L ') + x + ',' + y;
    });
    svgParts.push('<path d="' + pastPath + '" fill="none" stroke="' + color + '" stroke-width="2.5" stroke-linejoin="round"/>');
  }

  // 未来预测曲线（虚线）
  const futurePoints = points.filter(function(p) { return !p.isPast; });
  if (futurePoints.length > 0) {
    // 从当前点开始画
    const lastPast = pastPoints[pastPoints.length - 1];
    let futPath = 'M ' + padL + ',' + (padT + chartH * (1 - lastPast.decay));
    futurePoints.forEach(function(p) {
      const x = padL + (p.day / maxDay) * chartW;
      const y = padT + chartH * (1 - p.decay);
      futPath += ' L ' + x + ',' + y;
    });
    svgParts.push('<path d="' + futPath + '" fill="none" stroke="' + color + '" stroke-width="2" stroke-dasharray="6,3" opacity="0.5"/>');

    // 预测区域填充
    let futArea = futPath + ' L ' + (padL + (futurePoints[futurePoints.length-1].day / maxDay) * chartW) + ',' + (padT + chartH) + ' L ' + padL + ',' + (padT + chartH) + ' Z';
    svgParts.push('<path d="' + futArea + '" fill="' + color + '" opacity="0.08"/>');
  }

  // 当前衰减点
  const currentDecay = entry.decay_score || 0;
  const currentY = padT + chartH * (1 - currentDecay);
  svgParts.push('<circle cx="' + nowX + '" cy="' + currentY + '" r="5" fill="' + color + '" stroke="#fff" stroke-width="2"/>');
  svgParts.push('<text x="' + (nowX+10) + '" y="' + (currentY+4) + '" font-size="12" fill="' + color + '" font-weight="700">' + (currentDecay*100).toFixed(0) + '%</text>');

  // X轴标签
  const dayLabels = [0, Math.round(daysSinceCreation/2), Math.round(daysSinceCreation), Math.round(daysSinceCreation + futureDays/2), totalDays];
  dayLabels.forEach(function(d) {
    if (d > totalDays) return;
    const x = padL + (d / maxDay) * chartW;
    svgParts.push('<text x="' + x + '" y="' + (padT+chartH+16) + '" text-anchor="middle" font-size="10" fill="#999">第' + d + '天</text>');
  });
  svgParts.push('<text x="' + (padL+chartW/2) + '" y="' + (padT+chartH+30) + '" text-anchor="middle" font-size="11" fill="#666">时间（实线=过去 虚线=预测）</text>');

  // 模态窗口HTML
  let modalHtml = '<div class="entry-decay-modal-overlay" onclick="closeEntryDecayModal()"></div>';
  modalHtml += '<div class="entry-decay-modal">';
  modalHtml += '<div class="entry-decay-modal-header">';
  modalHtml += '<div class="entry-decay-modal-cat" style="color:' + color + '">' + name + '</div>';
  modalHtml += '<div class="entry-decay-modal-preview">' + preview + '</div>';
  modalHtml += '<button class="entry-decay-modal-close" onclick="closeEntryDecayModal()">✕</button>';
  modalHtml += '</div>';

  modalHtml += '<div class="entry-decay-modal-stats">';
  modalHtml += '<div class="entry-decay-stat"><span class="entry-decay-stat-label">衰减强度</span><span class="entry-decay-stat-value" style="color:' + color + '">' + (currentDecay*100).toFixed(0) + '%</span></div>';
  modalHtml += '<div class="entry-decay-stat"><span class="entry-decay-stat-label">重要性</span><span class="entry-decay-stat-value">' + (importance*100).toFixed(0) + '%</span></div>';
  modalHtml += '<div class="entry-decay-stat"><span class="entry-decay-stat-label">类型因子</span><span class="entry-decay-stat-value">' + (typeFactor*100).toFixed(0) + '%</span></div>';
  modalHtml += '<div class="entry-decay-stat"><span class="entry-decay-stat-label">已存活</span><span class="entry-decay-stat-value">' + Math.round(daysSinceCreation) + '天</span></div>';
  modalHtml += '<div class="entry-decay-stat"><span class="entry-decay-stat-label">30天后预测</span><span class="entry-decay-stat-value" style="color:#999">' + (points[points.length-1].decay*100).toFixed(0) + '%</span></div>';
  modalHtml += '</div>';

  modalHtml += '<div class="entry-decay-modal-chart">';
  modalHtml += '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" preserveAspectRatio="xMidYMid meet">';
  modalHtml += svgParts.join('');
  modalHtml += '</svg>';
  modalHtml += '</div>';

  modalHtml += '<div class="entry-decay-modal-formula">衰减公式: decay = importance × (0.3 + 0.4 × exp(-0.03 × days) + 0.3 × typeFactor)</div>';
  modalHtml += '</div>';

  // 创建或更新模态DOM
  let modalContainer = document.getElementById('entryDecayModalContainer');
  if (!modalContainer) {
    modalContainer = document.createElement('div');
    modalContainer.id = 'entryDecayModalContainer';
    document.body.appendChild(modalContainer);
  }
  modalContainer.innerHTML = modalHtml;
  modalContainer.style.display = 'block';
}

function closeEntryDecayModal() {
  const modal = document.getElementById('entryDecayModalContainer');
  if (modal) modal.style.display = 'none';
}