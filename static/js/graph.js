async function loadData() {
  try {
    const res = await fetch('/api/data?t=' + Date.now());
    graphData = await res.json();
  } catch (e) {
    showToast('❌ 无法加载数据', 'error');
    return;
  }
  timelinePoints = buildTimelinePoints(graphData);
  applyTimepoint(timelinePoints.length - 1);
}

// 加载数据源状态
async function loadSourceStatus() {
  try {
    const res = await fetch('/api/v1/status');
    const data = await res.json();
    renderSourcePanel(data.providers || []);
  } catch (e) {
    console.error('加载数据源状态失败:', e);
  }
}

// 渲染数据源面板
function renderSourcePanel(providers) {
  const container = document.getElementById('sourceList');
  if (!providers.length) {
    container.innerHTML = '<div style="color:#888;font-size:11px">暂无数据源</div>';
    return;
  }
  container.innerHTML = providers.map(p => `
    <div class="source-item ${p.name === 'skills' ? 'source-skill-item' : ''}" 
         ${p.name === 'skills' ? 'onclick="toggleSkillPanel()" title="点击查看技能库"' : ''}>
      <span class="dot ${p.status === 'connected' ? 'connected' : 'disconnected'}"></span>
      <span class="name">${p.name === 'skills' ? '⚡ 技能库' : p.name}</span>
      <span class="count">${p.item_count || 0} 条</span>
      ${p.name === 'skills' ? '<span class="skill-arrow" id="skillArrow">▶</span>' : ''}
    </div>
  `).join('');
}

// 节点大小函数（层级递减 + V2重要性增强: center > primary > secondary > memory/skill_cat > skill_subcat > skill）
function nodeRadius(d) {
  // Base radius by category
  if (d.category === 'center') return 24;
  if (d.category === 'primary') return 14;
  if (d.category === 'secondary') return 9;
  if (d.category === 'skill_category') return 7;
  if (d.category === 'skill_subcategory') return 5;
  if (d.category === 'skill') return 3.5;

  // Memory nodes: scale by access_count + importance (V2)
  if (d.category === 'memory') {
    const base = 5;
    const ac = d.access_count || 0;
    const imp = d.importance || 0.5;
    
    // Access count boost: 0 → 11px (log scale)
    const acBoost = Math.min(Math.log1p(ac) * 2.5, 11);
    
    // Importance boost: 0 → 5px (linear scale from 0.3 to 1.0)
    const impBoost = Math.max(0, (imp - 0.3) * 8.3);
    
    return base + acBoost + impBoost;
  }
  return 8;
}
function glowRadius(d) {
  if (d.category === 'center') return 42;
  if (d.category === 'primary') return 26;
  if (d.category === 'secondary') return 16;
  if (d.category === 'memory') return nodeRadius(d) * 1.8;
  if (d.category === 'skill_category') return 12;
  if (d.category === 'skill_subcategory') return 8;
  if (d.category === 'skill') return 5;
  return 14;
}

// 力距离配置
function linkDistance(d) {
  const src = d.source.category || '', tgt = d.target.category || '';
  if (src === 'center' && tgt === 'primary') return 320;
  if (src === 'primary' && tgt === 'secondary') return 200;
  if (src === 'secondary' && tgt === 'memory') return 130;
  if (tgt === 'skill_category' || src === 'skill_category') return 100;
  if (tgt === 'skill_subcategory' || src === 'skill_subcategory') return 70;
  if (src === 'skill_subcategory' && tgt === 'skill') return 50;
  if ((src === 'skill_category' || src === 'secondary') && tgt === 'skill') return 70;
  if (src === 'skill' && tgt === 'skill') return 45;
  return 170;
}

// 力斥力配置 — 增大斥力让节点更铺开
function chargeStrength(d) {
  if (d.category === 'center') return -1200;
  if (d.category === 'primary') return -700;
  if (d.category === 'secondary') return -400;
  if (d.category === 'memory') return -180;
  if (d.category === 'skill_category') return -180;
  if (d.category === 'skill_subcategory') return -100;
  if (d.category === 'skill') return -40;
  return -200;
}

// 碰撞半径 — 增大碰撞半径避免重叠
function collisionRadius(d) {
  if (d.category === 'center') return 65;
  if (d.category === 'primary') return 45;
  if (d.category === 'secondary') return 28;
  if (d.category === 'memory') return nodeRadius(d) + 14;
  if (d.category === 'skill_category') return 22;
  if (d.category === 'skill_subcategory') return 15;
  if (d.category === 'skill') return 9;
  return 30;
}

// 为节点组设置内部 DOM 元素（发光圈、主圆、标签、折叠指示器）
function setupNodeDOM(sel) {
  // 发光底圈
  sel.append('circle')
    .attr('class', 'node-glow')
    .attr('r', d => glowRadius(d))
    .attr('fill', d => getNodeColor(d))
    .attr('opacity', d => {
      // V2: 应用衰减分数到透明度
      if (d.category === 'memory' && d.decay_score !== undefined) {
        return 0.12 * d.decay_score;
      }
      if (d.category === 'skill') return 0.06;
      if (d.category === 'skill_subcategory') return 0.08;
      if (d.category === 'center') return 0.25;
      if (d.category === 'primary') return 0.18;
      return 0.12;
    });

  // 主圆
  sel.append('circle')
    .attr('class', 'node-circle')
    .attr('r', d => nodeRadius(d))
    .attr('fill', d => getNodeColor(d))
    .attr('opacity', d => {
      // V2: 衰减分数影响主圆透明度
      if (d.category === 'memory' && d.decay_score !== undefined) {
        return Math.max(0.3, d.decay_score);
      }
      return 1;
    })
    .attr('stroke', d => {
      // V2: 根据状态显示不同边框颜色
      if (d.category === 'memory') {
        // 固定节点：金色边框
        if (d.pinned) return '#FFD700';
        // 根据衰减状态
        const decay = d.decay_score;
        if (decay !== undefined) {
          if (decay < 0.3) return '#FF4444';  // 危险：红色
          if (decay < 0.6) return '#FFaa00';  // 衰减中：橙色
          if (decay > 0.95) return '#44FF88'; // 健康：绿色
        }
      }
      return getNodeColor(d) + '88';
    })
    .attr('stroke-width', d => {
      if (d.category === 'memory' && (d.pinned || d.decay_score < 0.6)) {
        return 2; // 重要状态节点加粗边框
      }
      return 1;
    })
    .attr('filter', d => {
      const key = d.primary || d.category;
      return `url(#glow-${key})`;
    });

  // ── 时间线变化标记：新增节点显示醒目的脉冲光环 + "✦" 标识 ──
  sel.filter(d => d._isNew && _timelineChangeInfo.newNodeIds.has(d.id))
    .append('circle')
    .attr('class', 'change-marker-glow')
    .attr('r', d => nodeRadius(d) + 22)
    .attr('fill', '#00ffaa')
    .attr('fill-opacity', 0.3)
    .attr('stroke', 'none');

  sel.filter(d => d._isNew && _timelineChangeInfo.newNodeIds.has(d.id))
    .append('circle')
    .attr('class', 'change-marker-new')
    .attr('r', d => nodeRadius(d) + 22)
    .attr('fill', 'none')
    .attr('stroke', '#00ffaa')
    .attr('stroke-width', 4)
    .attr('stroke-dasharray', '10 5')
    .style('opacity', 1);

  sel.filter(d => d._isNew && _timelineChangeInfo.newNodeIds.has(d.id))
    .append('text')
    .attr('class', 'change-marker-text')
    .attr('dy', d => -(nodeRadius(d) + 20))
    .attr('text-anchor', 'middle')
    .text('✦')
    .style('font-size', '20px')
    .style('font-weight', '900')
    .style('fill', '#00ffaa')
    .style('opacity', 1);

  // 标签
  sel.append('text')
    .attr('class', 'node-label')
    .attr('dy', d => {
      if (d.category === 'center') return 40;
      if (d.category === 'primary') return 28;
      if (d.category === 'secondary') return 20;
      if (d.category === 'memory') return 16;
      if (d.category === 'skill_category') return 16;
      if (d.category === 'skill_subcategory') return 14;
      if (d.category === 'skill') return 12;
      return 20;
    })
    .text(d => d.label)
    .style('font-size', d => {
      if (d.category === 'center') return '14px';
      if (d.category === 'primary') return '12px';
      if (d.category === 'secondary') return '10px';
      if (d.category === 'memory') return '9px';
      if (d.category === 'skill_category') return '9px';
      if (d.category === 'skill_subcategory') return '8px';
      if (d.category === 'skill') return '7px';
      return '10px';
    })
    .style('fill', d => {
      if (d.category === 'center') return '#FFD700';
      if (d.category === 'primary') return getNodeColor(d);
      return null;
    })
    .attr('display', 'block')
    .style('opacity', d => d.category === 'skill' ? 0.7 : 1);

  return sel;
}

// 更新折叠指示器（无需重建节点）
function updateCollapseIndicators() {
  const fullData = getActiveData();
  if (!fullData) return;

  d3.selectAll('.node-group').each(function(d) {
    const g = d3.select(this);
    // 删除旧指示器
    g.selectAll('.collapse-indicator, .collapse-indicator-text').remove();

    if (!isCollapsible(d, fullData.links)) return;

    const isExpanded = expandedNodes.has(d.id);
    const descendantCount = getDescendantIds(d.id, fullData.nodes, fullData.links).size;
    const r = nodeRadius(d);

    g.append('circle')
      .attr('class', 'collapse-indicator')
      .attr('cx', r + 2)
      .attr('cy', -(r + 2))
      .attr('r', 6)
      .attr('fill', isExpanded ? '#10B981' : '#6B7280')
      .attr('stroke', '#fff')
      .attr('stroke-width', 1.5)
      .style('cursor', 'pointer');

    g.append('text')
      .attr('class', 'collapse-indicator-text')
      .attr('x', r + 2)
      .attr('y', -(r + 2))
      .attr('dy', '0.35em')
      .attr('text-anchor', 'middle')
      .attr('fill', '#fff')
      .attr('font-size', '8px')
      .attr('font-weight', 'bold')
      .attr('pointer-events', 'none')
      .text(isExpanded ? '−' : descendantCount);
  });
}

// ========== renderGraph: 首次完整渲染 ==========
function renderGraph(data = getActiveData()) {
  if (!data) return;

  const visibleData = getVisibleData(data);
  const container = document.getElementById('graph');
  container.innerHTML = '';

  _graphWidth = container.clientWidth;
  _graphHeight = container.clientHeight;

  _svg = d3.select('#graph').append('svg')
    .attr('width', _graphWidth)
    .attr('height', _graphHeight);

  _svg.on('click', (e) => {
    if (e.target.tagName === 'svg' || e.target.tagName === 'rect') hideDetail();
  });

  _g = _svg.append('g');

  _zoom = d3.zoom()
    .scaleExtent([0.3, 4])
    .on('zoom', (e) => _g.attr('transform', e.transform));
  _svg.call(_zoom);

  // 发光滤镜（只创建一次）
  const defs = _svg.append('defs');
  const glowDefs = { ...PRIMARY_COLORS, center: { color: '#FFD700' } };
  Object.entries(glowDefs).forEach(([key, cat]) => {
    const filter = defs.append('filter').attr('id', `glow-${key}`).attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%');
    filter.append('feGaussianBlur').attr('stdDeviation', '4').attr('result', 'blur');
    filter.append('feFlood').attr('flood-color', cat.color).attr('flood-opacity', '0.6').attr('result', 'color');
    filter.append('feComposite').attr('in', 'color').attr('in2', 'blur').attr('operator', 'in').attr('result', 'glow');
    const merge = filter.append('feMerge');
    merge.append('feMergeNode').attr('in', 'glow');
    merge.append('feMergeNode').attr('in', 'SourceGraphic');
  });

  // 连线层和节点层分组（连线在下，节点在上）
  _g.append('g').attr('class', 'links-layer');
  _g.append('g').attr('class', 'nodes-layer');

  // 深拷贝数据
  const nodes = visibleData.nodes.map(d => ({ ...d }));
  const links = visibleData.links.map(d => ({ ...d }));

  // 力导向（丝滑参数：慢衰减、低摩擦，让布局渐进收敛）
  simulation = d3.forceSimulation(nodes)
    .alphaDecay(0.02)
    .alphaMin(0.005)
    .velocityDecay(0.4)
    .force('link', d3.forceLink(links).id(d => d.id).distance(linkDistance))
    .force('charge', d3.forceManyBody().strength(chargeStrength))
    .force('center', d3.forceCenter(_graphWidth / 2, _graphHeight / 2))
    .force('collision', d3.forceCollide().radius(collisionRadius))
    .force('x', d3.forceX(_graphWidth / 2).strength(0.02))
    .force('y', d3.forceY(_graphHeight / 2).strength(0.02));

  // 用 D3 data-join 渲染连线
  _linkGroup = _g.select('.links-layer').selectAll('.link-group')
    .data(links, d => `${d.source.id || d.source}-${d.target.id || d.target}`)
    .join(enter => {
      const lg = enter.append('g').attr('class', 'link-group');
      lg.append('line').attr('class', 'link-line');
      lg.append('text').attr('class', 'link-label').text(d => d.label || '');
      return lg;
    });

  // Dynamic link styling based on strength and type
  _linkGroup.select('.link-line')
    .attr('stroke-width', d => {
      const s = d.strength || 1.0;
      // co_occurs links: thicker based on co-occurrence count
      if (d.label === 'co_occurs') return Math.max(1, s * 1.2);
      // mentions links: slightly thicker
      if (d.label === 'mentions') return 1.5;
      // hierarchy links: thin
      return 1;
    })
    .attr('stroke', d => {
      if (d.label === 'co_occurs') return 'rgba(255, 152, 0, 0.35)';
      if (d.label === 'mentions') return 'rgba(33, 150, 243, 0.25)';
      return null; // use CSS default
    })
    .attr('stroke-dasharray', d => {
      if (d.label === 'co_occurs') return '4,2';
      return null;
    });

  // 用 D3 data-join 渲染节点
  _nodeGroup = _g.select('.nodes-layer').selectAll('.node-group')
    .data(nodes, d => d.id)
    .join(enter => {
      const ng = enter.append('g')
        .attr('class', 'node-group');
      setupNodeDOM(ng);
      return ng;
    });

  // 事件绑定
  _nodeGroup
    .on('click', (e, d) => {
      e.stopPropagation();
      const fullData = getActiveData();
      if (isCollapsible(d, fullData ? fullData.links : [])) {
        toggleNodeExpansion(d);
      } else {
        showDetail(d);
      }
    })
    .on('dblclick', (e, d) => {
      e.stopPropagation();
      showDetail(d);
    })
    .call(d3.drag()
      .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
    );

  // 折叠指示器
  updateCollapseIndicators();

  // Center 节点光晕
  _nodeGroup.filter(d => d.category === 'center')
    .select('.node-glow')
    .attr('opacity', 0.3);

  // Tick — 保存位置到全局映射
  simulation.on('tick', () => {
    _g.select('.links-layer').selectAll('.link-group').select('.link-line')
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);

    _g.select('.links-layer').selectAll('.link-group').select('.link-label')
      .attr('x', d => (d.source.x + d.target.x) / 2)
      .attr('y', d => (d.source.y + d.target.y) / 2);

    _g.select('.nodes-layer').selectAll('.node-group')
      .attr('transform', d => `translate(${d.x},${d.y})`);

    // 持续保存位置
    nodes.forEach(n => { _nodePositions[n.id] = { x: n.x, y: n.y }; });
  });

  // 初始居中
  setTimeout(() => {
    _svg.transition().duration(800).call(
      _zoom.transform,
      d3.zoomIdentity.translate(_graphWidth / 2, _graphHeight / 2).scale(0.85).translate(-_graphWidth / 2, -_graphHeight / 2)
    );
  }, 1000);
}

// ========== updateVisibleGraph: 增量更新（展开/折叠时调用） ==========
function updateVisibleGraph() {
  const data = getActiveData();
  if (!data || !_g) return;

  const visibleData = getVisibleData(data);

  // 保存当前力模拟中所有节点的位置
  if (simulation) {
    simulation.nodes().forEach(n => {
      _nodePositions[n.id] = { x: n.x, y: n.y };
    });
    simulation.stop();
  }

  // 准备新数据，复用已有位置
  const nodes = visibleData.nodes.map(d => {
    const pos = _nodePositions[d.id];
    if (pos) {
      return { ...d, x: pos.x, y: pos.y };
    }
    // 新节点：从父节点位置出发（或画面中心）
    const parentLink = visibleData.links.find(l => {
      const tid = l.target.id || l.target;
      return tid === d.id;
    });
    if (parentLink) {
      const parentId = parentLink.source.id || parentLink.source;
      const parentPos = _nodePositions[parentId];
      if (parentPos) {
        // 加一点随机偏移避免重叠
        return { ...d, x: parentPos.x + (Math.random() - 0.5) * 40, y: parentPos.y + (Math.random() - 0.5) * 40 };
      }
    }
    return { ...d, x: _graphWidth / 2 + (Math.random() - 0.5) * 100, y: _graphHeight / 2 + (Math.random() - 0.5) * 100 };
  });
  // 确保 source/target 始终是 ID 字符串，避免 D3 forceLink 替换为对象后残留
  const links = visibleData.links.map(d => ({
    ...d,
    source: d.source?.id || d.source,
    target: d.target?.id || d.target,
  }));

  // 取消未完成的 transition（快速切换时间刻度时避免残留）
  _g.select('.links-layer').selectAll('.link-group').interrupt();
  _g.select('.nodes-layer').selectAll('.node-group').interrupt();

  // 增量更新连线（D3 data-join: enter/update/exit）
  // 确保所有连线数据 source/target 都是 ID 字符串，避免 D3 节点对象引用导致 key 不匹配
  const linkKeyFn = d => {
    const sId = typeof d.source === 'object' ? d.source.id : d.source;
    const tId = typeof d.target === 'object' ? d.target.id : d.target;
    return `${sId}-${tId}`;
  };

  _g.select('.links-layer').selectAll('.link-group')
    .data(links, linkKeyFn)
    .join(
      enter => {
        const lg = enter.append('g').attr('class', 'link-group').style('opacity', 0);
        lg.append('line').attr('class', 'link-line');
        lg.append('text').attr('class', 'link-label').text(d => d.label || '');
        lg.transition().duration(600).ease(d3.easeCubicOut).style('opacity', 1);
        return lg;
      },
      update => update,
      exit => exit.transition().duration(400).ease(d3.easeCubicIn).style('opacity', 0).remove()
    );

  // ── 时间线变化时：新增连线高亮，非变化连线淡化 ──
  const hasChanges = _timelineChangeInfo.newNodeIds.size > 0 || _timelineChangeInfo.disappearedIds.size > 0;
  if (hasChanges) {
    // 新增连线：连到新增节点的线 → 绿色高亮
    _g.select('.links-layer').selectAll('.link-group')
      .classed('link-new', d => {
        const sId = d.source.id || d.source;
        const tId = d.target.id || d.target;
        return _timelineChangeInfo.newNodeIds.has(sId) || _timelineChangeInfo.newNodeIds.has(tId);
      })
      .classed('link-old', d => {
        const sId = d.source.id || d.source;
        const tId = d.target.id || d.target;
        return !_timelineChangeInfo.newNodeIds.has(sId) && !_timelineChangeInfo.newNodeIds.has(tId);
      });
    // 新增连线样式：醒目高亮
    _g.select('.links-layer').selectAll('.link-group.link-new .link-line')
      .attr('stroke', '#00ffaa')
      .attr('stroke-width', 3.5)
      .attr('stroke-opacity', 1);
    // 新增连线标签也高亮
    _g.select('.links-layer').selectAll('.link-group.link-new .link-label')
      .style('fill', '#00ffaa')
      .style('font-weight', '600')
      .style('opacity', 0.9);
    // 非变化连线轻微淡化，保持结构骨架可见
    _g.select('.links-layer').selectAll('.link-group.link-old .link-line')
      .attr('stroke-opacity', 0.2);
  } else {
    // 清除变化样式
    _g.select('.links-layer').selectAll('.link-group')
      .classed('link-new', false)
      .classed('link-old', false);
    _g.select('.links-layer').selectAll('.link-group .link-line')
      .attr('stroke-opacity', null)
      .attr('stroke', null)
      .attr('stroke-width', null);
    _g.select('.links-layer').selectAll('.link-group .link-label')
      .style('fill', null)
      .style('opacity', null);
  }

  // 增量更新节点（D3 data-join: enter/update/exit）
  // 先清除所有残留的变化标记元素（上一帧新增的节点在本帧不再是新增）
  _g.select('.nodes-layer').selectAll('.node-group .change-marker-glow').remove();
  _g.select('.nodes-layer').selectAll('.node-group .change-marker-new').remove();
  _g.select('.nodes-layer').selectAll('.node-group .change-marker-text').remove();

  _g.select('.nodes-layer').selectAll('.node-group')
    .data(nodes, d => d.id)
    .join(
      enter => {
        const ng = enter.append('g')
          .attr('class', 'node-group')
          .style('opacity', 0)
          .attr('transform', d => `translate(${d.x},${d.y})`);
        setupNodeDOM(ng);
        // 丝滑淡入
        ng.transition().duration(500).ease(d3.easeCubicOut).style('opacity', 1);
        return ng;
      },
      update => update,  // 保持不动
      exit => exit.transition().duration(400).ease(d3.easeCubicIn).style('opacity', 0).remove()
    );

  // 重新绑定事件（因为新节点需要）
  _g.select('.nodes-layer').selectAll('.node-group')
    .on('click', (e, d) => {
      e.stopPropagation();
      const fullData = getActiveData();
      if (isCollapsible(d, fullData ? fullData.links : [])) {
        toggleNodeExpansion(d);
      } else {
        showDetail(d);
      }
    })
    .on('dblclick', (e, d) => {
      e.stopPropagation();
      showDetail(d);
    })
    .call(d3.drag()
      .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
    );

  // 更新折叠指示器
  updateCollapseIndicators();

  // Center 光晕
  _g.select('.nodes-layer').selectAll('.node-group')
    .filter(d => d.category === 'center')
    .select('.node-glow')
    .attr('opacity', 0.3);

  // ── 焦点模式：时间线变化时，镜头对焦到新增节点区域 ──
  if (hasChanges && _timelineChangeInfo.newNodeIds.size > 0 && _zoom) {
    // 计算新增节点的中心位置
    const newNodePositions = nodes.filter(n => _timelineChangeInfo.newNodeIds.has(n.id))
      .map(n => ({ x: n.x || _nodePositions[n.id]?.x || _graphWidth/2, y: n.y || _nodePositions[n.id]?.y || _graphHeight/2 }));

    if (newNodePositions.length > 0) {
      const cx = newNodePositions.reduce((s, p) => s + p.x, 0) / newNodePositions.length;
      const cy = newNodePositions.reduce((s, p) => s + p.y, 0) / newNodePositions.length;

      // 根据新增节点分布范围决定缩放级别
      const spreadX = Math.max(...newNodePositions.map(p => Math.abs(p.x - cx)), 80);
      const spreadY = Math.max(...newNodePositions.map(p => Math.abs(p.y - cy)), 80);
      const focusScale = Math.min(1.5, Math.max(0.8, Math.min(_graphWidth / (spreadX * 4), _graphHeight / (spreadY * 4))));

      // 丝滑 zoom transition 移动镜头到焦点区域
      _svg.transition().duration(1200).ease(d3.easeCubicInOut)
        .call(_zoom.transform,
          d3.zoomIdentity
            .translate(_graphWidth / 2, _graphHeight / 2)
            .scale(focusScale)
            .translate(-cx, -cy)
        );
    }
  } else if (_zoom && isTimelineActive) {
    // 无变化帧：镜头平滑回到全局视角
    _svg.transition().duration(1200).ease(d3.easeCubicInOut)
      .call(_zoom.transform,
        d3.zoomIdentity.translate(_graphWidth / 2, _graphHeight / 2).scale(0.85).translate(-_graphWidth / 2, -_graphHeight / 2)
      );
  }

  // 增量更新力模拟（不重建，保持位置连续性 → 丝滑过渡）
  const isTimelineActive = activeTimelineIndex >= 0 && activeTimelineIndex < (timelinePoints?.length || 0);
  const alphaValue = isTimelineActive ? 0.25 : 0.15;

  if (!simulation) {
    // 首次创建
    simulation = d3.forceSimulation(nodes)
      .alphaDecay(0.02)
      .alphaMin(0.005)
      .velocityDecay(0.4)
      .alpha(alphaValue)
      .force('link', d3.forceLink(links).id(d => d.id).distance(linkDistance))
      .force('charge', d3.forceManyBody().strength(chargeStrength))
      .force('center', d3.forceCenter(_graphWidth / 2, _graphHeight / 2))
      .force('collision', d3.forceCollide().radius(collisionRadius))
      .force('x', d3.forceX(_graphWidth / 2).strength(0.02))
      .force('y', d3.forceY(_graphHeight / 2).strength(0.02));
  } else {
    // 增量更新：保留已有节点位置，只更新 nodes/links 数据
    simulation
      .nodes(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(linkDistance))
      .force('charge', d3.forceManyBody().strength(chargeStrength))
      .force('center', d3.forceCenter(_graphWidth / 2, _graphHeight / 2))
      .force('collision', d3.forceCollide().radius(collisionRadius))
      .force('x', d3.forceX(_graphWidth / 2).strength(0.02))
      .force('y', d3.forceY(_graphHeight / 2).strength(0.02))
      .alpha(alphaValue)
      .alphaDecay(0.02)
      .alphaMin(0.005)
      .velocityDecay(0.4)
      .restart();
  }

  // 平滑 tick 回调：用 requestAnimationFrame 插值，避免硬拉
  let _lastTickTime = 0;
  simulation.on('tick', () => {
    // 连线直接更新（线条过渡视觉上不明显，不需要插值）
    _g.select('.links-layer').selectAll('.link-group').select('.link-line')
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);

    _g.select('.links-layer').selectAll('.link-group').select('.link-label')
      .attr('x', d => (d.source.x + d.target.x) / 2)
      .attr('y', d => (d.source.y + d.target.y) / 2);

    // 节点位置平滑过渡：利用 SVG transform transition
    _g.select('.nodes-layer').selectAll('.node-group')
      .attr('transform', d => `translate(${d.x},${d.y})`);

    // 持续保存位置
    nodes.forEach(n => { _nodePositions[n.id] = { x: n.x, y: n.y }; });
  });
}

// IQ 仪表盘
const DIM_COLORS = {
  capacity: '#1e90ff',
  density: '#a855f7',
  coverage: '#2ed573',
  depth: '#ffa502',
  network: '#ff4757',
  skills: '#ff6b6b',
};

function toggleIqPanel() {
  const panel = document.getElementById('iqPanel');
  const isExpanded = panel.classList.toggle('expanded');
  // 展开时自动展开详情
  if (isExpanded) {
    const details = document.getElementById('iqDetails');
    details.style.maxHeight = '400px';
    details.style.marginTop = '10px';
  }
}

async function loadIQ() {
  try {
    const res = await fetch('/api/iq?t=' + Date.now());
    const data = await res.json();
    renderIQ(data);
  } catch (e) {
    console.error('IQ load error:', e);
  }
}

function renderIQ(data) {
  const { iq, level, breakdown, tips, stats, skills } = data;

  // Animate ball number (小圆球上的数字)
  const ballEl = document.getElementById('iqBallNumber');
  animateNumber(ballEl, iq, 1500);

  // Animate gauge number (展开后的数字)
  const numEl = document.getElementById('iqNumber');
  animateNumber(numEl, iq, 1500);

  // Level
  document.getElementById('iqLevel').textContent = level;
  document.getElementById('iqSubtitle').textContent = '点击收起';

  // Gauge ring (r=26)
  const circumference = 2 * Math.PI * 26; // r=26
  const pct = Math.min(1, (iq - 40) / 120); // 40-160 mapped to 0-1
  const offset = circumference * (1 - pct);
  const fill = document.getElementById('iqGaugeFill');

  // Color based on IQ (human-scale)
  let gaugeColor = '#78909c';
  if (iq >= 140) gaugeColor = '#a855f7';
  else if (iq >= 120) gaugeColor = '#1e90ff';
  else if (iq >= 100) gaugeColor = '#2ed573';
  else if (iq >= 90) gaugeColor = '#ffa502';
  else if (iq >= 80) gaugeColor = '#ff6348';

  fill.style.stroke = gaugeColor;
  // Delay to trigger animation
  requestAnimationFrame(() => {
    fill.style.strokeDashoffset = offset;
  });

  // Dimensions
  const dimEl = document.getElementById('iqDimensions');
  if (breakdown && typeof breakdown === 'object') {
    dimEl.innerHTML = Object.entries(breakdown).map(([key, dim]) => {
      const pct = (dim.score / dim.max * 100).toFixed(0);
      const color = DIM_COLORS[key] || '#888';
      return `
        <div class="iq-dimension">
          <span class="iq-dim-label">${dim.label}</span>
          <div class="iq-dim-bar-bg">
            <div class="iq-dim-bar-fill" style="width:${pct}%;background:${color}"></div>
          </div>
          <span class="iq-dim-score">${dim.score}/${dim.max}</span>
        </div>`;
    }).join('');
  }

  // Tips
  const tipsEl = document.getElementById('iqTips');
  if (Array.isArray(tips) && tips.length) {
    tipsEl.innerHTML = tips.map(t => `<div class="iq-tip">${t}</div>`).join('');
  }

  // IQ Scale Table
  const scales = [
    { range: '140~160', name: '天才', emoji: '🧠', color: '#a855f7' },
    { range: '120~140', name: '非常聪明', emoji: '🌟', color: '#1e90ff' },
    { range: '110~120', name: '中上水平', emoji: '💡', color: '#2ed573' },
    { range: '100~110', name: '正常偏上', emoji: '📖', color: '#2ed573' },
    { range: '90~100', name: '正常水平', emoji: '📖', color: '#ffa502' },
    { range: '80~90',  name: '发育中',   emoji: '🌱', color: '#ff6348' },
    { range: '60~80',  name: '刚觉醒',   emoji: '👶', color: '#ff4757' },
    { range: '40~60',  name: '沉睡中',   emoji: '💤', color: '#78909c' },
  ];
  const scaleEl = document.getElementById('iqScaleTable');
  scaleEl.innerHTML = `<div class="iq-scale-title">📊 智商等级对照</div>` +
    scales.map(s => {
      const [lo, hi] = s.range.split('~').map(Number);
      const isCurrent = iq >= lo && iq < hi;
      return `<div class="iq-scale-row${isCurrent ? ' current' : ''}">
        <span class="iq-scale-dot" style="background:${s.color}"></span>
        <span class="iq-scale-range">${s.range}</span>
        <span class="iq-scale-name">${s.name} ${s.emoji}</span>
        ${isCurrent ? '<span style="font-size:10px">◀ 当前</span>' : ''}
      </div>`;
    }).join('');

  // Skill summary
  if (skills && skills.total > 0) {
    const skillSummary = document.getElementById('iqSkillSummary');
    if (skillSummary) {
      skillSummary.innerHTML = `
        <div class="iq-scale-title">🛠️ 技能概览</div>
        <div style="display:flex;justify-content:space-between;padding:4px 8px;font-size:11px;color:#b0bec5">
          <span>已掌握 <b style="color:#ff6b6b">${skills.total}</b> 项技能</span>
          <span>覆盖 <b style="color:#ff6b6b">${skills.categories}</b> 个领域</span>
        </div>
        <div style="padding:2px 8px 6px;font-size:10px;color:#78909c;line-height:1.6">
          ${skills.category_list.slice(0, 8).map(c => `<span style="background:rgba(255,107,107,0.15);padding:1px 6px;border-radius:8px;margin:2px 2px;display:inline-block">${c}</span>`).join('')}
          ${skills.category_list.length > 8 ? `<span style="color:#666">+${skills.category_list.length - 8}更多</span>` : ''}
        </div>`;
    }
  }
}

function animateNumber(el, target, duration) {
  const start = parseInt(el.textContent) || 0;
  const diff = target - start;
  const startTime = performance.now();

  function step(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
    el.textContent = Math.round(start + diff * eased);
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
function switchToSettings() {
  hideDetail();
  currentView = 'settings';
  
  // 更新 Tab 样式
  document.getElementById('tabMemory').classList.remove('active');
  document.getElementById('tabWiki').classList.remove('active');
  document.getElementById('tabInsight').classList.remove('active');
  document.getElementById('tabSettings').classList.add('active');
  
  // 隐藏其他视图元素
  document.getElementById('settingsDashboard').style.display = 'block';
  document.getElementById('insightDashboard').style.display = 'none';
  document.getElementById('graph').style.display = 'none';
  document.querySelectorAll('.filter-bar,.stats-panel,.timeline-ruler,.iq-panel,.health-filter-bar').forEach(el => el.style.display = 'none');
  if (document.getElementById('btnRefresh')) document.getElementById('btnRefresh').style.display = 'none';
  if (document.getElementById('timelineRuler')) document.getElementById('timelineRuler').style.display = 'none';
  
  // 加载设置数据
  loadSettingsData();
}

// ========== 视图切换 ==========
function switchView(view) {
  if (view === currentView) return;

  // 保存当前视图状态
  if (currentView === 'memory') {
    // Memory 状态已在 graphData/currentViewData 中
  } else {
    // Wiki 状态已在 wikiGraphData/wikiCurrentViewData 中
  }

  currentView = view;

  // 更新 Tab 样式
  document.getElementById('tabMemory').classList.toggle('active', view === 'memory');
  document.getElementById('tabWiki').classList.toggle('active', view === 'wiki');
  document.getElementById('tabInsight').classList.toggle('active', view === 'insight');

  // 洞察面板显隐
  document.getElementById('insightDashboard').style.display = view === 'insight' ? 'block' : 'none';
  // 设置面板显隐
  document.getElementById('settingsDashboard').style.display = view === 'settings' ? 'block' : 'none';
  // Wiki库面板显隐
  document.getElementById('wikiDashboard').style.display = view === 'wiki' ? 'block' : 'none';
  document.getElementById('graph').style.display = (view === 'insight' || view === 'settings' || view === 'wiki') ? 'none' : '';
  document.querySelectorAll('.filter-bar,.stats-panel,.timeline-ruler,.iq-panel,.health-filter-bar').forEach(el => el.style.display = (view === 'insight' || view === 'settings' || view === 'wiki') ? 'none' : '');

  // 更新标题图标颜色
  const titleIcon = document.querySelector('.title-icon');
  if (view === 'wiki') {
    titleIcon.style.background = 'radial-gradient(circle, #3498db 0%, #3498db44 70%)';
    titleIcon.style.boxShadow = '0 0 15px #3498db44';
  } else {
    titleIcon.style.background = '';
    titleIcon.style.boxShadow = '';
  }

  // 切换刷新按钮文字
  const refreshBtn = document.getElementById('btnRefresh');
  refreshBtn.innerHTML = `<span class="btn-icon">🔄</span><span class="spinner"></span>${view === 'wiki' ? '刷新Wiki' : '刷新记忆'}`;
  refreshBtn.style.display = (view === 'insight' || view === 'settings' || view === 'wiki') ? 'none' : '';

  // 切换时间刻度线可见性（仅记忆视图显示）
  const timelineRuler = document.getElementById('timelineRuler');
  if (timelineRuler) timelineRuler.style.display = view === 'memory' ? '' : 'none';

  // 重置筛选
  activeFilters.clear();

  // 重置展开状态
  expandedNodes.clear();
  _nodePositions = {};

  if (view === 'insight') {
    loadHealthData();
    return;
  }

  if (view === 'wiki') {
    loadWikiPages();
  } else {
    buildFilterBar();
    if (graphData) {
      currentViewData = { ...graphData };
      updateStats(currentViewData);
      renderGraph(currentViewData);
      // 重建时间轴
      timelinePoints = buildTimelinePoints(graphData);
      applyTimepoint(timelinePoints.length - 1);
    } else {
      loadData();
    }
    loadIQ();
  }
}

