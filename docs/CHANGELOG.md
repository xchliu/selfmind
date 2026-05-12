## [2.6.0] — 2026-05-11

### Added
- 🐳 **Docker化** — Dockerfile + docker-compose.yml + .env.example + config.example.json，一键容器化部署
- 🔥 **热挂载+watch脚本** — 开发模式热重载，watch.sh监控文件变更自动重启容器
- 🔄 **统一数据管道** — unified_store + unified_sync 取代 legacy memory/user/skill 独立存储，SQLite为唯一数据源
- 🧠 **记忆健康修复** — 分类解析bug修正 + 衰减公式重构(新条目不再归零)
- 🕸️ **图谱逐级展开** — 默认只显示self + 8个primary节点，点击逐级展开子节点，避免全图爆炸
- 📇 **Wiki卡片预览加大+表格渲染** — 卡片尺寸增大，支持markdown表格渲染
- 🧬 **Agent DNA设计文档** — 新增Agent DNA架构设计文档，定义自我进化核心机制

### Changed
- 数据流从legacy多文件 → unified SQLite单管道
- 知识图谱默认视图从全量展示 → 逐级展开

### Fixed
- 修复分类解析bug — wiki_parser类别映射错误导致部分条目缺失
- 修复衰减公式 — freq=0时所有新条目decay归零问题

---

## [2.5.0] — 2026-05-08

### Added
- 📁 **项目文件整理** — index.html 215KB拆为9个静态文件(CSS 4个+JS 6个)，缩减93.7%
- 🏗️ **http_handler.py模块化拆分** — 1782行拆为4个mixin模块(StatsMixin/MutationsMixin/EnginesMixin/V1Mixin)，缩减73.4%
- 📚 **Wiki库页面** — 知识图谱tab改为Wiki库，卡片展示+详情弹窗+markdown渲染+编辑保存
- 📝 **PUT /api/wiki/page API** — 支持wiki页面编辑保存
- 📂 **wiki_parser.py新增projects扫描** — 支持6种分类(entities/concepts/comparisons/queries/projects/summaries)
- 🧠 **记忆健康模块修复** — 启动时自动sync + decay公式修正(新条目不再全是0分) + 前端自动触发sync
- 🔄 **unified_store.py** — SQLite统一数据模型(entries+entry_history+operations_log+snapshots)
- 🔄 **unified_sync.py** — 统一采集入口，从memory/user/skill文件sync到SQLite
- 📐 **演变追踪设计** — 核心字段(产生时间+版本+更新时间+记忆强度)，数据源无产生时间则用采集时间

### Changed
- 标签名'知识图谱'→'Wiki库'
- `server.py` — 启动时自动sync meta_db
- 根目录清理 — 删除12个垃圾文件(bak/碎片html/空json/pycache等)，ROADMAP.md移入docs/
- data.json移入data/子目录

### Fixed
- 修复wiki_parser缺少projects目录扫描
- 修复marketization-kpi-2026.md行号格式污染
- 修复agi-pathfinder-party-brand.md frontmatter type错误
- 修复metadata_db decay公式(freq=0导致所有新条目decay=0)
- 修复记忆健康页面数据为空(db重建后未sync)

---

## [2.4.0] — 2026-05-06

### Added
- 🧠 **U型记忆沉淀页面** — 新增"记忆沉淀"导航tab，展示记忆从对话到固化技能的完整沉淀路径
- 📊 **6层实时状态指标** — 每层节点卡片显示关键指标数字（会话数、容量占比、Honcho状态、节点数、Skill数、实体数）
- 🔄 **动态健康检查** — L1-L6全部从 `/api/stats` 实时获取状态，不再硬编码
- 🎯 **6条激活路径** — 右臂展示对话/推理/可视化/任务/检索/学习6条激活路径，贝塞尔射线连接源节点
- 🏗️ **后端 `/api/stats` 端点** — 新增API，一次性返回6层实时指标数据（sessions/memories/honcho/selfmind/skills/wiki）
- 🔗 **U型SVG弧线骨架** — 贝塞尔曲线绘制完整U型路径，节点沿弧线分布

### Changed
- `index.html` — 新增记忆沉淀视图(sediment)及相关CSS/HTML/JS
- `index.html` — 浅色主题重写（白色背景、深色文字、无网格线）
- `index.html` — U弧线右臂改为更直的路径（减少弯曲）
- `index.html` — 激活卡片移至右臂弧线旁，射线从源节点连接
- `selfmind_app/http_handler.py` — 新增 `/api/stats` 路由及 `_handle_stats()` 方法
- `selfmind_app/http_handler.py` — `_handle_poll()` 新增 Honcho 健康检查

### Fixed
- 修复 L3/L4 状态硬编码❌ — 改为动态检查（Honcho用/health端点，SelfMind检测进程）
- 修复 Honcho健康检查 — curl从GET /v3/workspaces改为/health端点
- 修复 JS `<<script>` typo — 双小于号导致脚本不加载

---

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