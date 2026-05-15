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

function renderDecayCurve() {
  if (!healthEntries || healthEntries.length === 0) {
    document.getElementById('decayCurveChart').innerHTML = '<div style="color:#ccc;text-align:center;padding:30px">请先加载健康数据</div>';
    return;
  }

  const catData = {};
  healthEntries.forEach(e => {
    const cat = e.primary_cat || 'unknown';
    const ds = e.decay_score || 0;
    const imp = e.importance || 0;
    if (!catData[cat]) catData[cat] = { count: 0, decays: [], importances: [] };
    catData[cat].count++;
    catData[cat].decays.push(ds);
    catData[cat].importances.push(imp);
  });

  const catAvg = [];
  for (const cat in catData) {
    const avg = catData[cat].decays.reduce((a,b) => a+b, 0) / catData[cat].decays.length;
    const avgImp = catData[cat].importances.reduce((a,b) => a+b, 0) / catData[cat].importances.length;
    catAvg.push({ cat, avg, avgImp, count: catData[cat].count });
  }
  catAvg.sort((a, b) => b.avg - a.avg);

  renderDecayAreaChart(catAvg);
  renderDecayBucketChart(healthEntries);
  renderDecayTimeline(healthEntries);
}

function renderDecayAreaChart(catAvg) {
  const W = 700, H = 300;
  const padL = 120, padR = 30, padT = 30, padB = 50;
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;
  const maxVal = 1.0;
  const n = catAvg.length;

  let svgParts = [];
  for (let i = 0; i <= 10; i++) {
    const y = padT + chartH * (1 - i/10);
    const val = (i/10 * maxVal * 100).toFixed(0);
    svgParts.push('<line x1="' + padL + '" y1="' + y + '" x2="' + (W-padR) + '" y2="' + y + '" stroke="#ddd" stroke-width="1"/>');
    svgParts.push('<text x="' + (padL-8) + '" y="' + (y+4) + '" text-anchor="end" font-size="11" fill="#999">' + val + '%</text>');
  }
  svgParts.push('<text x="' + (padL-50) + '" y="' + (padT+chartH/2) + '" text-anchor="middle" font-size="12" fill="#666" transform="rotate(-90,' + (padL-50) + ',' + (padT+chartH/2) + ')">衰减强度</text>');

  const points = catAvg.map((d, i) => ({
    x: padL + (i + 0.5) * (chartW / n),
    y: padT + chartH * (1 - d.avg / maxVal),
    cat: d.cat, avg: d.avg, avgImp: d.avgImp, count: d.count
  }));

  // 面积填充
  let areaD = 'M ' + points[0].x + ',' + (padT + chartH);
  points.forEach(p => { areaD += ' L ' + p.x + ',' + p.y; });
  areaD += ' L ' + points[points.length-1].x + ',' + (padT + chartH) + ' Z';
  svgParts.push('<path d="' + areaD + '" fill="rgba(30,144,255,0.15)" stroke="none"/>');

  // 折线
  let lineD = points.map(p => p.x + ',' + p.y).join(' L ');
  svgParts.push('<path d="M ' + lineD + '" fill="none" stroke="#1e90ff" stroke-width="2.5" stroke-linejoin="round"/>');

  // 数据点+标签
  points.forEach(p => {
    const color = DECAY_COLORS[p.cat] || '#636e72';
    const name = DECAY_NAMES[p.cat] || p.cat;
    svgParts.push('<circle cx="' + p.x + '" cy="' + p.y + '" r="6" fill="' + color + '" stroke="#fff" stroke-width="2"/>');
    svgParts.push('<text x="' + p.x + '" y="' + (p.y-14) + '" text-anchor="middle" font-size="11" font-weight="600" fill="' + color + '">' + (p.avg*100).toFixed(0) + '%</text>');
    svgParts.push('<text x="' + (padL-8) + '" y="' + (padT + chartH * (1 - p.avg / maxVal) + 4) + '" text-anchor="end" font-size="11" fill="#666">' + name + ' (' + p.count + ')</text>');
  });

  // 阈值线
  const thresholdY = padT + chartH * (1 - 0.5 / maxVal);
  svgParts.push('<line x1="' + padL + '" y1="' + thresholdY + '" x2="' + (W-padR) + '" y2="' + thresholdY + '" stroke="#f0932b" stroke-width="1.5" stroke-dasharray="6,4"/>');
  svgParts.push('<text x="' + (W-padR+2) + '" y="' + (thresholdY+4) + '" font-size="10" fill="#f0932b">阈值 50%</text>');

  // 图例
  let legendHtml = catAvg.slice(0, 12).map(d => {
    const color = DECAY_COLORS[d.cat] || '#636e72';
    const name = DECAY_NAMES[d.cat] || d.cat;
    return '<div class="decay-legend-item"><span class="decay-legend-dot" style="background:' + color + '"></span>' + name + ': ' + (d.avg*100).toFixed(0) + '% (' + d.count + '条)</div>';
  }).join('');

  const chartHtml = '<div class="decay-curve-title">各分类平均衰减强度（面积图）</div>' +
    '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" preserveAspectRatio="xMidYMid meet" style="max-height:320px">' + svgParts.join('') + '</svg>' +
    '<div class="decay-legend">' + legendHtml + '</div>';
  document.getElementById('decayCurveChart').innerHTML = chartHtml;
}

function renderDecayBucketChart(entries) {
  const W = 700, H = 200;
  const padL = 60, padR = 30, padT = 30, padB = 40;
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;

  const buckets = Array.from({length: 10}, (_, i) => ({ min: i*0.1, max: (i+1)*0.1, count: 0 }));
  entries.forEach(e => {
    const ds = e.decay_score || 0;
    const bi = Math.min(Math.floor(ds / 0.1), 9);
    buckets[bi].count++;
  });
  const maxCount = Math.max.apply(null, buckets.map(b => b.count));
  if (maxCount < 1) maxCount = 1;

  let svgParts = [];
  const barW = (chartW / 10) - 6;

  svgParts.push('<text x="' + (padL-50) + '" y="' + (padT+chartH/2) + '" text-anchor="middle" font-size="12" fill="#666" transform="rotate(-90,' + (padL-50) + ',' + (padT+chartH/2) + ')">条目数</text>');

  buckets.forEach((b, i) => {
    const x = padL + i * (chartW / 10) + 3;
    const h = (b.count / maxCount) * chartH;
    const y = padT + chartH - h;
    const pct = (b.min * 100).toFixed(0) + '-' + (b.max * 100).toFixed(0) + '%';
    let color;
    if (b.min < 0.2) color = '#e74c3c';
    else if (b.min < 0.5) color = '#f0932b';
    else color = '#2ed573';

    svgParts.push('<rect x="' + x + '" y="' + y + '" width="' + barW + '" height="' + h + '" fill="' + color + '" rx="3" opacity="0.85"/>');
    svgParts.push('<text x="' + (x + barW/2) + '" y="' + (y-6) + '" text-anchor="middle" font-size="11" fill="#333" font-weight="600">' + b.count + '</text>');
    svgParts.push('<text x="' + (x + barW/2) + '" y="' + (padT+chartH+18) + '" text-anchor="middle" font-size="10" fill="#999">' + pct + '</text>');
  });

  svgParts.push('<text x="' + (padL+chartW/2) + '" y="' + (padT+chartH+32) + '" text-anchor="middle" font-size="11" fill="#666">衰减强度区间（左弱右强）</text>');
  for (let i = 0; i <= 4; i++) {
    const y = padT + chartH * (1 - i/4);
    const val = Math.round(maxCount * i/4);
    svgParts.push('<line x1="' + padL + '" y1="' + y + '" x2="' + (W-padR) + '" y2="' + y + '" stroke="#eee" stroke-width="1"/>');
    svgParts.push('<text x="' + (padL-8) + '" y="' + (y+4) + '" text-anchor="end" font-size="10" fill="#999">' + val + '</text>');
  }

  const chartHtml = '<div class="decay-curve-title">衰减分布柱状图（红=危险 黄=衰减中 绿=健康）</div>' +
    '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" preserveAspectRatio="xMidYMid meet" style="max-height:220px">' + svgParts.join('') + '</svg>';
  document.getElementById('decayBucketChart').innerHTML = chartHtml;
}

function renderDecayTimeline(entries) {
  const W = 700, H = 180;
  const padL = 60, padR = 30, padT = 20, padB = 40;
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;

  const monthData = {};
  entries.forEach(e => {
    const date = e.first_seen_at || e.updated_at || e.created_at || '';
    const month = date.slice(0, 7);
    if (!month || month.length < 7) return;
    if (!monthData[month]) monthData[month] = { count: 0, decays: [] };
    monthData[month].count++;
    monthData[month].decays.push(e.decay_score || 0);
  });
  for (const m in monthData) {
    monthData[m].avgDecay = monthData[m].decays.reduce((a,b) => a+b, 0) / monthData[m].decays.length;
  }

  const months = Object.keys(monthData).sort();
  if (months.length === 0) {
    document.getElementById('decayTimelineChart').innerHTML = '<div style="color:#ccc;text-align:center;padding:20px">暂无时间数据</div>';
    return;
  }

  const maxCount = Math.max.apply(null, months.map(m => monthData[m].count));
  if (maxCount < 1) maxCount = 1;
  let svgParts = [];
  const barW = Math.max(chartW / months.length - 4, 12);

  months.forEach((m, i) => {
    const d = monthData[m];
    const x = padL + i * (chartW / months.length) + 2;
    const barH = (d.count / maxCount) * chartH * 0.6;
    const barY = padT + chartH - barH;
    svgParts.push('<rect x="' + x + '" y="' + barY + '" width="' + barW + '" height="' + barH + '" fill="rgba(30,144,255,0.25)" rx="2"/>');
    svgParts.push('<text x="' + (x+barW/2) + '" y="' + (barY-4) + '" text-anchor="middle" font-size="10" fill="#1e90ff">' + d.count + '</text>');
    const lineY = padT + chartH * (1 - d.avgDecay) * 0.6;
    const color = d.avgDecay > 0.5 ? '#2ed573' : d.avgDecay > 0.2 ? '#f0932b' : '#e74c3c';
    svgParts.push('<circle cx="' + (x+barW/2) + '" cy="' + lineY + '" r="4" fill="' + color + '"/>');
    svgParts.push('<text x="' + (x+barW/2) + '" y="' + (padT+chartH+16) + '" text-anchor="middle" font-size="9" fill="#999">' + m.slice(2) + '</text>');
  });

  // 衰减连线
  const linePoints = months.map((m, i) => {
    const d = monthData[m];
    const x = padL + i * (chartW / months.length) + 2 + barW/2;
    const y = padT + chartH * (1 - d.avgDecay) * 0.6;
    return x + ',' + y;
  }).join(' L ');
  svgParts.push('<path d="M ' + linePoints + '" fill="none" stroke="#f0932b" stroke-width="2" stroke-linejoin="round"/>');

  svgParts.push('<text x="' + (padL-50) + '" y="' + (padT+chartH/2) + '" text-anchor="middle" font-size="11" fill="#666" transform="rotate(-90,' + (padL-50) + ',' + (padT+chartH/2) + ')">条目数 / 衰减</text>');

  const chartHtml = '<div class="decay-curve-title">记忆产生时间线 — 每月新增(柱) + 平均衰减(线)</div>' +
    '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" preserveAspectRatio="xMidYMid meet" style="max-height:200px">' + svgParts.join('') + '</svg>';
  document.getElementById('decayTimelineChart').innerHTML = chartHtml;
}