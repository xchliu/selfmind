// ========== U型记忆沉淀 ==========
// Live stats from /api/stats — fetched dynamically, no hardcoded values
let sedimentLiveStats = {};

const sedimentLayers = [
  { id:'L1', name:'对话记忆', sub:'Session', icon:'💬', desc:'原始对话，最详细' },
  { id:'L2', name:'核心快照', sub:'Memory', icon:'🧠', desc:'2K chars极限容量' },
  { id:'L3', name:'身份推理', sub:'Honcho', icon:'🔮', desc:'dialectic推理引擎' },
  { id:'L4', name:'可视化图谱', sub:'SelfMind', icon:'🕸️', desc:'力导向图渲染' },
  { id:'L5', name:'程序记忆', sub:'Skills', icon:'⚡', desc:'可复用工作流' },
  { id:'L6', name:'知识库', sub:'Wiki', icon:'📚', desc:'结构化实体存储' }
];

const sedimentBreaks = [
  { from:'L1', to:'L2', label:'主观判断' },
  { from:'L2', to:'L3', label:'Honcho不读Mem' },
  { from:'L3', to:'L4', label:'格式不结构化' },
  { from:'L4', to:'L5', label:'无自动流' }
];

const sedimentActPaths = [
  { id:'conv', name:'对话激活', icon:'💬', desc:'L2/L5/L6 → L1', srcs:['L2','L5','L6'], color:'#1a6b4f' },
  { id:'reason', name:'推理激活', icon:'🔮', desc:'L1/L2 → L3', srcs:['L1','L2','L3'], color:'#a855f7' },
  { id:'visual', name:'可视化', icon:'🕸️', desc:'L2/L6 → L4', srcs:['L2','L6'], color:'#00d4ff' },
  { id:'task', name:'任务激活', icon:'⚡', desc:'L5/L6 → 执行', srcs:['L5','L2','L6'], color:'#c05621' },
  { id:'search', name:'检索激活', icon:'🔍', desc:'L1 → 历史', srcs:['L1'], color:'#ffd700' },
  { id:'learn', name:'学习闭环', icon:'📝', desc:'L1 → L2/L5/L6', srcs:['L1','L2','L5'], color:'#ff6b6b' }
];

function loadSedimentData() {
  // Fetch live stats from /api/stats — all 6 layers with real metrics
  fetch('/api/stats?t=' + Date.now())
    .then(r => r.json())
    .then(data => {
      sedimentLiveStats = data;
      renderSediment();
    })
    .catch(() => {
      // Fallback: still render with whatever data we have
      renderSediment();
    });
}

function renderSediment() {
  const canvas = document.getElementById('sedCanvas');
  const svg = document.getElementById('sedSvg');
  const nodesDiv = document.getElementById('sedNodes');
  if (!svg || !nodesDiv || !canvas) return;

  const W = canvas.offsetWidth || 1280;
  const H = canvas.offsetHeight || 670;

  // U curve coordinates — full width spread
  const LX = W * 0.12;      // left arm X
  const RX = W * 0.88;      // right arm X
  const TY = H * 0.04;      // top Y
  const BY = H * 0.82;      // bottom Y (U bottom)
  const MX = W * 0.50;      // bottom midpoint X

  // Node positions — left arm (L1→L4 going down), bottom (L5→L6)
  const nodePos = {
    L1: { x: LX - 10, y: TY },
    L2: { x: LX - 10, y: TY + H*0.22 },
    L3: { x: LX - 10, y: TY + H*0.44 },
    L4: { x: LX + W*0.05, y: TY + H*0.66 },
    L5: { x: MX - W*0.10, y: BY },
    L6: { x: MX + W*0.05, y: BY },
  };

  // Activation path positions — RIGHT side, next to the right arm of U curve
  // Spread vertically alongside RX (right arm)
  const actPos = {
    conv:   { x: W * 0.80, y: H * 0.10 },
    reason: { x: W * 0.80, y: H * 0.24 },
    visual: { x: W * 0.80, y: H * 0.38 },
    task:   { x: W * 0.80, y: H * 0.52 },
    search: { x: W * 0.80, y: H * 0.66 },
    learn:  { x: W * 0.80, y: H * 0.78 },
  };

  // 1. Build SVG
  let svgHtml = '';

  // Defs
  svgHtml += `<defs>
    <linearGradient id="uCurveGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#00ffa3" stop-opacity="0.9"/>
      <stop offset="40%" stop-color="#ff6b35" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="#a855f7" stop-opacity="0.9"/>
    </linearGradient>
    <linearGradient id="uCurveGlow" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#00ffa3" stop-opacity="0.15"/>
      <stop offset="40%" stop-color="#ff6b35" stop-opacity="0.15"/>
      <stop offset="100%" stop-color="#a855f7" stop-opacity="0.15"/>
    </linearGradient>
    <filter id="sedGlow">
      <feGaussianBlur stdDeviation="6" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>`;

  // Background grid removed

  // U curve path — smooth bezier, full-width U shape
  // Left arm down: L1→L2→L3→L4
  // Bottom arc: L4→L5→L6→curve up
  // Right arm up to RX
  const uPath = `M ${LX} ${TY}
    C ${LX} ${TY+H*0.08}, ${LX} ${TY+H*0.14}, ${LX} ${nodePos.L2.y}
    C ${LX} ${nodePos.L2.y+H*0.08}, ${LX} ${nodePos.L3.y-H*0.06}, ${LX} ${nodePos.L3.y}
    C ${LX} ${nodePos.L3.y+H*0.08}, ${LX+W*0.06} ${nodePos.L4.y-H*0.06}, ${nodePos.L4.x} ${nodePos.L4.y}
    C ${nodePos.L4.x+W*0.08} ${nodePos.L4.y+H*0.08}, ${nodePos.L5.x-W*0.04} ${BY-H*0.04}, ${nodePos.L5.x} ${BY}
    C ${nodePos.L5.x+W*0.04} ${BY+H*0.04}, ${nodePos.L6.x-W*0.04} ${BY+H*0.04}, ${nodePos.L6.x} ${BY}
    C ${nodePos.L6.x+W*0.06} ${BY+H*0.02}, ${RX-W*0.04} ${BY+H*0.01}, ${RX} ${BY}
    C ${RX+W*0.02} ${BY-H*0.04}, ${RX} ${BY-H*0.15}, ${RX} ${nodePos.L3.y}
    L ${RX} ${TY}`;

  // Glow layer
  svgHtml += `<path d="${uPath}" stroke="url(#uCurveGlow)" stroke-width="24" fill="none" filter="url(#sedGlow)"/>`;
  // Main curve
  svgHtml += `<path d="${uPath}" stroke="url(#uCurveGrad)" stroke-width="3" fill="none"/>`;

  // Flow particles
  const pColors = ['#00ffa3','#ff6b35','#a855f7','#00d4ff'];
  pColors.forEach((c, i) => {
    svgHtml += `<circle r="${4-i*0.5}" fill="${c}" opacity="0.9">
      <animateMotion dur="6s" repeatCount="indefinite" begin="${i*1.5}s" path="${uPath}"/>
    </circle>`;
  });

// Break markers between left arm nodes
  sedimentBreaks.forEach(brk => {
    const from = nodePos[brk.from];
    const to = nodePos[brk.to];
    if (!from || !to) return;
    const mx = (from.x + to.x) / 2 + 80;
    const my = (from.y + to.y) / 2 + 20;
    svgHtml += `<circle cx="${mx}" cy="${my}" r="5" fill="#ff6b6b" opacity="0.8" filter="url(#sedGlow)"/>`;
    svgHtml += `<text x="${mx+8}" y="${my+4}" fill="#ff6b6b" font-size="11" font-family="monospace" opacity="0.9">${brk.label}</text>`;
  });

  // Activation rays: from memory layer nodes → activation cards INSIDE the U
  sedimentActPaths.forEach(path => {
    const destPos = actPos[path.id];
    path.srcs.forEach((srcId, srcIdx) => {
      const srcPos = nodePos[srcId];
      if (!srcPos) return;
      // Source: right edge of node card → dest: left edge of act card (inside U)
      const sx = srcPos.x + 90;
      const sy = srcPos.y + 20;
      const dx = destPos.x;
      const dy = destPos.y + 20;
      // Bezier curving inward (toward center of U)
      const cpx = sx + (dx - sx) * 0.4;
      const cpy = sy + (dy - sy) * 0.5 + (srcIdx * 6);
      const opacity = srcIdx === 0 ? 0.7 : 0.4;
      const width = srcIdx === 0 ? 2 : 1.2;
      svgHtml += `<path d="M ${sx} ${sy} Q ${cpx} ${cpy}, ${dx} ${dy}"
        stroke="${path.color}" stroke-width="${width}" opacity="${opacity}" fill="none" stroke-dasharray="5 3"/>`;
      if (srcIdx === 0) {
        const rayPath = `M ${sx} ${sy} Q ${cpx} ${cpy}, ${dx} ${dy}`;
        svgHtml += `<circle r="2" fill="${path.color}" opacity="0.6">
          <animateMotion dur="2s" repeatCount="indefinite" begin="${Math.random()*2}s" path="${rayPath}"/>
        </circle>`;
      }
    });
  });

// Arm labels
  svgHtml += `<text x="${LX-10}" y="${TY+H*0.04}" fill="#00ffa3" font-size="16" font-weight="bold" text-anchor="start">沉淀 ▼</text>`;
  svgHtml += `<text x="${MX}" y="${BY+H*0.08}" fill="#ff6b35" font-size="14" font-weight="bold" text-anchor="middle">固化</text>`;
  svgHtml += `<text x="${RX+10}" y="${TY+H*0.04}" fill="#c084fc" font-size="16" font-weight="bold" text-anchor="start">激活 ▲</text>`;

  svg.innerHTML = svgHtml;

  // 2. Build HTML node cards
  let nodesHtml = '';

  // Left arm + bottom nodes — with live metrics from /api/stats
  sedimentLayers.forEach(layer => {
    const pos = nodePos[layer.id];
    const live = sedimentLiveStats[layer.id] || { status:'warn', metric:0, metric_label:'', detail:'loading...' };
    const sc = live.status === 'ok' ? 'sed-ok' : live.status === 'warn' ? 'sed-warn' : 'sed-err';
    const sl = live.status === 'ok' ? '✅' : live.status === 'warn' ? '⚠️' : '❌';
    const isBottom = (layer.id === 'L5' || layer.id === 'L6');
    const bc = isBottom ? ' bottom-card' : '';
    const metricColor = live.status === 'err' ? '#cc3333' : live.status === 'warn' ? '#b8860b' : '#1a6b4f';
    nodesHtml += `
    <div class="sed-node-card ${sc}${bc}" style="left:${pos.x}px;top:${pos.y}px;">
      <div class="sed-node-icon">${layer.icon}</div>
      <div class="sed-node-id">${layer.id}</div>
      <div class="sed-node-name">${layer.name}</div>
      <div class="sed-node-sub">${layer.sub}</div>
      <div class="sed-metric" style="color:${metricColor}">${live.metric}</div>
      <div class="sed-metric-label">${live.metric_label}</div>
      <div class="sed-detail">${live.detail}</div>
      <div class="sed-node-status">${sl}</div>
    </div>`;
  });

  // Right arm activation cards
  sedimentActPaths.forEach(path => {
    const pos = actPos[path.id];
    nodesHtml += `
    <div class="sed-act-card" style="left:${pos.x}px;top:${pos.y}px;border-left:2px solid ${path.color};">
      <div class="sed-act-icon">${path.icon}</div>
      <div class="sed-act-name" style="color:${path.color}">${path.name}</div>
      <div class="sed-act-desc">${path.desc}</div>
      <div class="sed-act-srcs">${path.srcs.map(s => '<span class="sed-act-src">' + s + '</span>').join('')}</div>
    </div>`;
  });

  nodesDiv.innerHTML = nodesHtml;
}

function sedimentRunCheck() {
  loadSedimentData(); // re-fetch live status then render
}
