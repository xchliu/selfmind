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
// Base formula: decay = importance × (base + recency_weight × recall_freq × recall_recency + type_w × typeFactor)
// - recalled entries: recency_weight=0.5, recall_freq=min(1.0, 0.3+0.1×count), recall_recency=exp(-0.05×days_since_recall)
// - never recalled: recency_weight=0.4, recency=exp(-0.03×days_since_update)
const DECAY_PARAMS = {
  importance_w: 1.0,
  base_w: 0.3,
  // Recalled entries (recall_boost)
  recall_recency_w: 0.5,
  recall_freq_base: 0.3,
  recall_freq_step: 0.1,
  recall_decay_rate: 0.05,  // exp(-0.05 × days_since_last_recall)
  // Never-recalled entries
  no_recall_recency_w: 0.4,
  no_recall_decay_rate: 0.03, // exp(-0.03 × days_since_update)
  type_factor_w: 0.3
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
  document.getElementById('decayBucketChart').innerHTML = '';
  document.getElementById('decayTimelineChart').innerHTML = '';
}

function renderDecayOverview(catAvg) {
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

  let svgParts = [];
  const thresholdX = labelW + chartW * 0.5;
  svgParts.push('<line x1="' + thresholdX + '" y1="0" x2="' + thresholdX + '" y2="' + (H-20) + '" stroke="#f0932b" stroke-width="1.5" stroke-dasharray="4,3" opacity="0.6"/>');
  svgParts.push('<text x="' + (thresholdX+4) + '" y="14" font-size="10" fill="#f0932b">阈值 50%</text>');

  catAvg.forEach(function(d, i) {
    const y = 24 + i * (barH + gap);
    const color = DECAY_COLORS[d.cat] || '#636e72';
    const name = DECAY_NAMES[d.cat] || d.cat;
    const pct = (d.avg * 100).toFixed(0);
    const barWidth = Math.max(d.avg * chartW, 4);

    svgParts.push('<text x="' + (labelW - 8) + '" y="' + (y + barH/2 + 5) + '" text-anchor="end" font-size="13" fill="' + color + '" font-weight="500">' + name + '</text>');
    svgParts.push('<rect x="' + labelW + '" y="' + y + '" width="' + chartW + '" height="' + barH + '" rx="4" fill="rgba(0,0,0,0.04)"/>');
    svgParts.push('<rect x="' + labelW + '" y="' + y + '" width="' + barWidth + '" height="' + barH + '" rx="4" fill="' + color + '" opacity="0.7"/>');
    svgParts.push('<text x="' + (labelW + barWidth + 8) + '" y="' + (y + barH/2 + 5) + '" font-size="12" fill="#333" font-weight="600">' + pct + '%</text>');
    svgParts.push('<text x="' + (labelW + barWidth + 50) + '" y="' + (y + barH/2 + 5) + '" font-size="10" fill="#999">' + d.count + '条</text>');
  });

  html += '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" preserveAspectRatio="xMidYMid meet" style="max-height:' + (H + 20) + 'px">';
  html += svgParts.join('');
  html += '</svg>';
  html += '</div>';

  document.getElementById('decayCurveChart').innerHTML = html;
}

// ========== 单条记忆衰减曲线（真实历史 + 起伏） ==========

function showEntryDecayCurve(entryId) {
  const entry = healthEntries.find(function(e) { return e.id === entryId; });
  if (!entry) return;

  // 先获取真实衰减历史数据，再画曲线
  fetch('/api/meta/entries/' + encodeURIComponent(entryId) + '/decay-history')
    .then(function(resp) { return resp.json(); })
    .then(function(historyData) {
      renderEntryDecayModal(entry, historyData);
    })
    .catch(function(err) {
      // 网络失败时用模拟曲线（没有历史数据）
      console.warn('Failed to fetch decay history:', err);
      renderEntryDecayModal(entry, []);
    });
}

function renderEntryDecayModal(entry, historyData) {
  const importance = entry.importance || 0.5;
  const typeFactor = TYPE_FACTOR[entry.entry_type] || 0.5;
  const createdAt = entry.first_seen_at || entry.updated_at || entry.created_at || new Date().toISOString();
  const currentDecay = entry.decay_score || 0;
  const recallCount = entry.recall_count || 0;
  const lastRecalled = entry.last_recalled || null;
  const hasRecall = recallCount > 0;
  const now = new Date();
  const created = new Date(createdAt);
  const daysSinceCreation = Math.max((now - created) / 86400000, 0);

  // ── 计算recall_boost相关参数 ──
  const recallFreq = Math.min(1.0, DECAY_PARAMS.recall_freq_base + DECAY_PARAMS.recall_freq_step * recallCount);
  let daysSinceRecall = daysSinceCreation;
  let recallRecency = Math.exp(-DECAY_PARAMS.no_recall_decay_rate * daysSinceCreation);
  let recencyWeight = DECAY_PARAMS.no_recall_recency_w;
  if (hasRecall && lastRecalled) {
    const lastRecDate = new Date(lastRecalled);
    daysSinceRecall = Math.max((now - lastRecDate) / 86400000, 0);
    recallRecency = Math.exp(-DECAY_PARAMS.recall_decay_rate * daysSinceRecall);
    recencyWeight = DECAY_PARAMS.recall_recency_w;
  }

  // ── 构建衰减曲线数据 ──
  // 如果有真实历史数据，用它画起伏曲线；否则模拟
  const futureDays = 30;
  const totalDays = daysSinceCreation + futureDays;
  let realHistoryPoints = [];
  let pastPoints = [];
  let futurePoints = [];
  let noRecallBaseline = [];  // 无recall的理论衰减线（对比参考）

  // 解析真实历史数据
  if (historyData && historyData.length > 0) {
    historyData.forEach(function(h) {
      const hTime = new Date(h.timestamp);
      const dayOffset = Math.max((hTime - created) / 86400000, 0);
      if (dayOffset <= daysSinceCreation) {
        realHistoryPoints.push({
          day: dayOffset,
          decay: h.decay_score,
          isPast: true,
          isReal: true,
          trigger: h.trigger
        });
      }
    });
  }

  // 模拟曲线（含recall_boost）—— 带起伏的真实衰减参考线
  for (let day = 0; day <= daysSinceCreation; day += Math.max(1, Math.floor(daysSinceCreation / 200))) {
    // recall_boost 曲线：使用recall参数
    const simRecallFreq = recallFreq;
    const simDaysSinceRecall = hasRecall ? Math.max(day - (daysSinceCreation - daysSinceRecall), 0) : day;
    const simRecallRecency = hasRecall
      ? Math.exp(-DECAY_PARAMS.recall_decay_rate * simDaysSinceRecall)
      : Math.exp(-DECAY_PARAMS.no_recall_decay_rate * day);
    const simRecencyW = hasRecall ? DECAY_PARAMS.recall_recency_w : DECAY_PARAMS.no_recall_recency_w;
    const decay = importance * (DECAY_PARAMS.base_w + simRecencyW * simRecallFreq * simRecallRecency + DECAY_PARAMS.type_factor_w * typeFactor);
    pastPoints.push({ day: day, decay: Math.min(decay, 1.0), isPast: true, isReal: false });

    // 无recall对比线（纯衰减）
    const baseRecency = Math.exp(-DECAY_PARAMS.no_recall_decay_rate * day);
    const baseDecay = importance * (DECAY_PARAMS.base_w + DECAY_PARAMS.no_recall_recency_w * baseRecency + DECAY_PARAMS.type_factor_w * typeFactor);
    noRecallBaseline.push({ day: day, decay: Math.min(baseDecay, 1.0) });
  }

  // 未来预测
  for (let day = Math.ceil(daysSinceCreation); day <= totalDays; day += 1) {
    const futDaysSinceRecall = hasRecall ? Math.max(day - (daysSinceCreation - daysSinceRecall), 0) : day;
    const futRecallRecency = hasRecall
      ? Math.exp(-DECAY_PARAMS.recall_decay_rate * futDaysSinceRecall)
      : Math.exp(-DECAY_PARAMS.no_recall_decay_rate * day);
    const futRecencyW = hasRecall ? DECAY_PARAMS.recall_recency_w : DECAY_PARAMS.no_recall_recency_w;
    const decay = importance * (DECAY_PARAMS.base_w + futRecencyW * recallFreq * futRecallRecency + DECAY_PARAMS.type_factor_w * typeFactor);
    futurePoints.push({ day: day, decay: Math.min(decay, 1.0), isPast: false, isReal: false });
  }

  const cat = entry.primary_cat || 'unknown';
  const color = DECAY_COLORS[cat] || '#636e72';
  const name = DECAY_NAMES[cat] || cat;
  const preview = extractPreview(entry.content_preview).substring(0, 80);
  const hasHistory = realHistoryPoints.length > 1;

  // ── SVG绘制 ──
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

  // ── 模拟底色曲线（含recall_boost，浅色实线） ──
  if (pastPoints.length > 0) {
    let simPath = '';
    pastPoints.forEach(function(p, i) {
      const x = padL + (p.day / maxDay) * chartW;
      const y = padT + chartH * (1 - p.decay);
      simPath += (i === 0 ? 'M ' : ' L ') + x.toFixed(1) + ',' + y.toFixed(1);
    });
    svgParts.push('<path d="' + simPath + '" fill="none" stroke="' + color + '" stroke-width="1.5" opacity="0.25" stroke-linejoin="round"/>');
  }

  // ── 无recall对比线（灰色虚线，展示recall_boost的提升效果） ──
  if (hasRecall && noRecallBaseline.length > 0) {
    let basePath = '';
    noRecallBaseline.forEach(function(p, i) {
      const x = padL + (p.day / maxDay) * chartW;
      const y = padT + chartH * (1 - p.decay);
      basePath += (i === 0 ? 'M ' : ' L ') + x.toFixed(1) + ',' + y.toFixed(1);
    });
    svgParts.push('<path d="' + basePath + '" fill="none" stroke="#999" stroke-width="1" stroke-dasharray="3,3" opacity="0.4"/>');
    // recall_boost 区域填充（两条曲线之间的差值）
    if (pastPoints.length > 0 && pastPoints.length === noRecallBaseline.length) {
      let boostArea = '';
      // 上边界：recall_boost曲线（更高的decay值）
      pastPoints.forEach(function(p, i) {
        const x = padL + (p.day / maxDay) * chartW;
        const y = padT + chartH * (1 - p.decay);
        boostArea += (i === 0 ? 'M ' : ' L ') + x.toFixed(1) + ',' + y.toFixed(1);
      });
      // 下边界：无recall曲线（反转方向）
      for (let i = noRecallBaseline.length - 1; i >= 0; i--) {
        const p = noRecallBaseline[i];
        const x = padL + (p.day / maxDay) * chartW;
        const y = padT + chartH * (1 - p.decay);
        boostArea += ' L ' + x.toFixed(1) + ',' + y.toFixed(1);
      }
      boostArea += ' Z';
      svgParts.push('<path d="' + boostArea + '" fill="#00b894" opacity="0.12"/>');
    }
  }

  // ── 真实历史曲线（起伏！重点展示） ──
  if (realHistoryPoints.length > 1) {
    // 连线
    let realPath = '';
    realHistoryPoints.forEach(function(p, i) {
      const x = padL + (p.day / maxDay) * chartW;
      const y = padT + chartH * (1 - p.decay);
      realPath += (i === 0 ? 'M ' : ' L ') + x.toFixed(1) + ',' + y.toFixed(1);
    });
    svgParts.push('<path d="' + realPath + '" fill="none" stroke="' + color + '" stroke-width="2.5" stroke-linejoin="round"/>');

    // 数据点圆圈（起伏的关键标记）
    realHistoryPoints.forEach(function(p) {
      const x = padL + (p.day / maxDay) * chartW;
      const y = padT + chartH * (1 - p.decay);
      // recall_boost标记用绿色外圈+向上箭头感
      if (p.trigger === 'recall_boost') {
        svgParts.push('<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="6" fill="' + color + '" stroke="#00b894" stroke-width="2"/>');
        svgParts.push('<text x="' + x.toFixed(1) + '" y="' + (y - 10).toFixed(1) + '" text-anchor="middle" font-size="8" fill="#00b894" font-weight="600">↑recall</text>');
      } else if (p.trigger === 'decay_change') {
        svgParts.push('<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="6" fill="' + color + '" stroke="#f0932b" stroke-width="2"/>');
      } else {
        svgParts.push('<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="4" fill="' + color + '" stroke="#fff" stroke-width="1.5"/>');
      }
    });
  } else if (pastPoints.length > 0 && !hasHistory) {
    // 无历史数据：用模拟曲线作为主线
    let pastPath = '';
    pastPoints.forEach(function(p, i) {
      const x = padL + (p.day / maxDay) * chartW;
      const y = padT + chartH * (1 - p.decay);
      pastPath += (i === 0 ? 'M ' : ' L ') + x.toFixed(1) + ',' + y.toFixed(1);
    });
    svgParts.push('<path d="' + pastPath + '" fill="none" stroke="' + color + '" stroke-width="2.5" stroke-linejoin="round"/>');
  }

  // ── 未来预测曲线（虚线） ──
  if (futurePoints.length > 0) {
    const lastPastDecay = currentDecay;
    let futPath = 'M ' + nowX.toFixed(1) + ',' + (padT + chartH * (1 - lastPastDecay)).toFixed(1);
    futurePoints.forEach(function(p) {
      const x = padL + (p.day / maxDay) * chartW;
      const y = padT + chartH * (1 - p.decay);
      futPath += ' L ' + x.toFixed(1) + ',' + y.toFixed(1);
    });
    svgParts.push('<path d="' + futPath + '" fill="none" stroke="' + color + '" stroke-width="2" stroke-dasharray="6,3" opacity="0.5"/>');

    let futArea = futPath + ' L ' + (padL + (futurePoints[futurePoints.length-1].day / maxDay) * chartW).toFixed(1) + ',' + (padT + chartH) + ' L ' + nowX.toFixed(1) + ',' + (padT + chartH) + ' Z';
    svgParts.push('<path d="' + futArea + '" fill="' + color + '" opacity="0.08"/>');
  }

  // 当前衰减点
  const currentY = padT + chartH * (1 - currentDecay);
  svgParts.push('<circle cx="' + nowX.toFixed(1) + '" cy="' + currentY.toFixed(1) + '" r="5" fill="' + color + '" stroke="#fff" stroke-width="2"/>');
  svgParts.push('<text x="' + (nowX+10).toFixed(1) + '" y="' + (currentY+4).toFixed(1) + '" font-size="12" fill="' + color + '" font-weight="700">' + (currentDecay*100).toFixed(0) + '%</text>');

  // X轴标签
  const dayLabels = [0, Math.round(daysSinceCreation/2), Math.round(daysSinceCreation), Math.round(daysSinceCreation + futureDays/2), totalDays];
  dayLabels.forEach(function(d) {
    if (d > totalDays) return;
    const x = padL + (d / maxDay) * chartW;
    svgParts.push('<text x="' + x.toFixed(1) + '" y="' + (padT+chartH+16) + '" text-anchor="middle" font-size="10" fill="#999">第' + d + '天</text>');
  });

  // 曲线类型说明
  let curveLabel = '实线=真实历史（有起伏） 虚线=预测 浅线=理论衰减';
  if (hasRecall) {
    curveLabel = '实线=真实历史 绿点↑=recall_boost 灰虚线=无recall对比 预测=虚线';
  }
  if (!hasHistory) {
    curveLabel = hasRecall
      ? '实线=含recall_boost模拟 灰虚线=无recall对比 预测=虚线'
      : '实线=模拟衰减（积累历史后可见起伏） 虚线=预测';
  }
  svgParts.push('<text x="' + (padL+chartW/2) + '" y="' + (padT+chartH+30) + '" text-anchor="middle" font-size="11" fill="#666">' + curveLabel + '</text>');

  // ── 模态窗口HTML ──
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
  modalHtml += '<div class="entry-decay-stat"><span class="entry-decay-stat-label">Recall次数</span><span class="entry-decay-stat-value" style="color:' + (hasRecall ? '#00b894' : '#999') + '">' + recallCount + (hasRecall ? '次 ↑' : '') + '</span></div>';
  if (hasRecall) {
    modalHtml += '<div class="entry-decay-stat"><span class="entry-decay-stat-label">Recall频率</span><span class="entry-decay-stat-value" style="color:#00b894">' + (recallFreq*100).toFixed(0) + '%</span></div>';
    modalHtml += '<div class="entry-decay-stat"><span class="entry-decay-stat-label">最近Recall</span><span class="entry-decay-stat-value">' + Math.round(daysSinceRecall) + '天前</span></div>';
  }
  modalHtml += '<div class="entry-decay-stat"><span class="entry-decay-stat-label">已存活</span><span class="entry-decay-stat-value">' + Math.round(daysSinceCreation) + '天</span></div>';
  modalHtml += '<div class="entry-decay-stat"><span class="entry-decay-stat-label">历史记录</span><span class="entry-decay-stat-value">' + realHistoryPoints.length + '次</span></div>';
  modalHtml += '<div class="entry-decay-stat"><span class="entry-decay-stat-label">30天后预测</span><span class="entry-decay-stat-value" style="color:#999">' + (futurePoints.length > 0 ? (futurePoints[futurePoints.length-1].decay*100).toFixed(0) : '--') + '%</span></div>';
  modalHtml += '</div>';

  modalHtml += '<div class="entry-decay-modal-chart">';
  modalHtml += '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" preserveAspectRatio="xMidYMid meet">';
  modalHtml += svgParts.join('');
  modalHtml += '</svg>';
  modalHtml += '</div>';

  modalHtml += '<div class="entry-decay-modal-formula">';
  if (hasRecall) {
    modalHtml += '衰减公式: decay = imp × (0.3 + 0.5 × recallFreq × exp(-0.05×daysSinceRecall) + 0.3 × typeFactor)';
    modalHtml += '<br><span style="font-size:10px;color:#00b894">recallFreq = min(1.0, 0.3 + 0.1×recallCount) — recall_boost ↑</span>';
  } else {
    modalHtml += '衰减公式: decay = imp × (0.3 + 0.4 × exp(-0.03×days) + 0.3 × typeFactor)';
    modalHtml += '<br><span style="font-size:10px;color:#999">无recall记录，使用传统衰减（agent推理后recall_boost可见）</span>';
  }
  modalHtml += '</div>';
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