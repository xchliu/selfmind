## [2.3.0] — 2026-04-27

### Added
- 🔍 **时间线焦点模式** — 播放时自动对焦到新增节点所在区域，镜头随变化平滑移动
- 🎯 **变化节点高亮** — 新增节点带 ✦ 标识（20px/900粗）+ 绿色脉冲光环 + 光晕填充
- 🌟 **变化连线高亮** — 新增连线荧光绿 `#00ffaa`、3.5px粗、标签加粗；非变化连线淡化到20%透明度
- 🔄 **丝滑时间线过渡** — 增量更新 force simulation（不再每帧重建），alphaDecay=0.02、velocityDecay=0.4
- 📐 **节点布局优化** — 斥力增50%、连线距离增30%、碰撞半径增30-60%，节点更铺开不重叠
- 🏠 **自动回归全局视角** — 无变化帧和播放结束后镜头平滑回到全局视角

### Changed
- `index.html` — 重写时间线播放机制（焦点模式 + 增量 simulation 更新）
- `index.html` — 优化力导向参数（斥力/距离/碰撞/居心全面调优）
- `index.html` — 连线 key 函数修复（source/target 对象引用 vs 字符串 ID 兼容）
- `index.html` — 非变化连线透明度从 0.08 改到 0.2（结构骨架可见）
- `index.html` — 播放间隔从 800ms → 2秒

### Fixed
- 修复连线消失问题 — D3 data-join key 匹配因 source/target 类型不一致导致连线误判为 exit
- 修复变化标记残留 — 帧切换时清除所有旧标记元素再重新标记，避免 _isNew 累积
- 修复播放结束后镜头不回归 — stopTimelinePlay 时自动 zoom 回全局视角

---

File unchanged since last read. The content from the earlier read_file result in this conversation is still current — refer to that instead of re-reading.