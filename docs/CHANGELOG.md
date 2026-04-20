# Changelog

All notable changes to SelfMind will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/).

---

## [2.1.0] — 2026-04-20

### Added (V2: Agent 睡眠系统)
- 🆕 **ARCHITECTURE_V2.md** — V2 架构设计文档（三大引擎：巩固/遗忘/分析）
- 🆕 **Consolidator (巩固引擎)** — 去重检测、冲突检测、可压缩条目识别、LLM 驱动的智能合并
- 🆕 **MetadataDB (元数据库)** — SQLite 持久化存储，支持记忆状态管理、版本快照、操作日志
- 🆕 **Wiki 数据解析增强** — wiki_data.json 结构化数据，wiki_parser.py 优化

### Changed
- `index.html` — 增强前端交互（节点状态可视化、健康度展示）
- `http_handler.py` — 扩展 API 端点支持 V2 功能
- `wiki_parser.py` — 优化 Wiki 知识图谱构建逻辑

### Data
- `wiki_data.json` — Wiki 知识库的结构化缓存
- `selfmind.db` — SQLite 元数据数据库
- `selfmind_meta.db` — 元数据管理数据库

---

## [2.0.0] — 2026-04-11

### Added
- 🧠 **认知记忆体系** — 基于认知心理学的 8 大分类 24 子类（自传体/语义/情景/程序性/社会认知/工作/空间/情绪）
- 🧬 **IQ 智商系统** — 参考人类 IQ 标准（均值 100，标准差 15），6 维度加权计算
- 🛠️ **技能图谱融合** — 扫描 `~/.hermes/skills/` 目录，95+ 技能四层层级展示（根→分类→子分类→技能）
- 📊 **IQ 圆球面板** — 左上角小圆球显示分数，点击展开 6 维度详情 + 等级对照表
- ⏱️ **全宽时间轴** — 底部透明毛玻璃时间刻度栏
- 🎯 **分类导航栏** — 顶部 8 大分类标签，底部指示条高亮选中态
- 📄 **MEMORY_TAXONOMY.md** — 完整的认知记忆分类设计文档
- 🏷️ **记忆标签格式** — `[分类/子分类] 内容` 规范化存储

### Changed
- 记忆分类从 6 类重构为 **8 大认知分类 + 24 子分类**
- 节点渲染按层级差异化（身份 r=22, 一级分类 r=14, 二级 r=9, 三级 r=6, 技能 r=4）
- 力导向参数按节点类型分层（排斥力 -400 到 -20 递减）
- 全局字体提升清晰度（antialiased 渲染、加粗字重、深色文字、节点标签描边）
- 暗色主题全面优化

---

## [0.2.0] — 2026-04-11

### Added
- Source profile support in `config.json` (`source.mode`, `active_profile`, `profiles`)
- OpenClaw memory source support (`~/.openclaw`)
- Honcho memory source support (`~/.honcho`)
- Multi-source parsing mode (`auto`) and single-profile mode (`single`)

### Changed
- Refactored backend into modules:
	- `selfmind_app/config.py`
	- `selfmind_app/parser.py`
	- `selfmind_app/http_handler.py`
- `server.py` is now a thin entrypoint
- Updated documentation to reflect standard-library HTTP backend and rule-based parsing

## [0.1.0] — 2025-04-11

### Added
- 🧠 Initial release
- Flask backend with LLM-powered memory parsing
- D3.js force-directed graph visualization
- 6 memory categories with color coding (identity, relationships, projects, rules, capabilities, environment)
- Node importance → size mapping
- Interactive hover highlighting (connected nodes + edges)
- Click-to-inspect detail panel
- Category filter bar
- Real-time search (name + description matching)
- Stats dashboard (nodes, links, categories, avg importance)
- Keyboard shortcuts (R/S/F/Escape)
- Graph data caching (data.json)
- Refresh + Save buttons
- Toast notifications (success/error/info)
- Light theme with glassmorphism UI
- SVG glow effect for high-importance nodes
- Drag-to-reposition nodes
- Zoom + pan canvas navigation
- Background grid decoration
- Support for Hermes Agent memory format (MEMORY.md + USER.md)
