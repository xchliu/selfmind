# SelfMind 演进路线图

> 核心理念：**可视化 → 管理 → 服务**

---

## 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                      SelfMind                           │
├─────────────┬─────────────────────┬─────────────────────┤
│   v1.0      │       v2.0          │       v3.0          │
│  可视化深化  │      记忆管理       │     服务化输出      │
├─────────────┼─────────────────────┬─────────────────────┤
│   toC       │       toB          │      to开发者        │
│  (个人用户)  │    (团队/部门)      │   (Agent集成)        │
└─────────────┴──────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    远期愿景                              │
│              v4.0 Agent DNA                             │
│  SelfMind=测序仪，agent的DNA=使用中沉淀的记忆模式        │
└─────────────────────────────────────────────────────────┘
```

---

## v1.0 可视化深化

**目标**：让人直观"看到"记忆的全貌

### 核心功能

| 模块 | 功能 | 状态 |
|------|------|------|
| 记忆图谱 | 节点/边关系可视化 | 🔄 边关系修复中 |
| Wiki库 | 结构化知识卡片+详情弹窗+编辑保存 | ✅ 已完成 |
| 记忆健康 | 遗忘曲线、衰减预警 | ✅ 已修复激活 |
| 时间轴 | 记忆时间线播放 | ✅ 基础完成 |
| **焦点模式** | 时间线播放自动对焦变化区域 | ✅ 已完成 |
| 主题切换 | 浅色/深色主题 | ✅ 浅色版完成 |
| **实时感知** | 源文件变化自动检测与图谱刷新 | ✅ 已完成 |
| **记忆沉淀** | U型6层沉淀路径+激活路径可视化 | ✅ 已完成 |
| **演变追踪** | 记忆产生时间+版本+更新时间+记忆强度 | ✅ 已完成（unified_store + entry_history） |
| **图谱逐级展开** | 节点按层级逐步展开 | ✅ 已完成 |
| **Wiki卡片优化** | 卡片预览加大+表格渲染支持 | ✅ 已完成 |
| **Docker化部署** | 容器化打包，一键启动 | ✅ 已完成 |
| **Agent切换** | 标题区下拉菜单一键切换Agent，图谱+DNA+健康联动 | ✅ 已完成 |
| **Gateway发现** | 输入Gateway地址自动探测Agent信息+路径验证 | ✅ 已完成 |
| **多Agent支持** | 苏格拉底+小亚+Grace，动态配置 | ✅ 已完成 |
| **Agent DNA页** | 基因组成+演变事件流+DNA时间线 | ✅ 已完成 |
| **衰减曲线可视化** | 记忆衰减趋势曲线图 | ✅ 已完成（/api/decay-trend + decay_history） |

### 技术任务

- [x] 前端自动轮询（15s 间隔检测源文件 mtime 变化）
- [x] 后端 `/api/poll` 接口（轻量 mtime hash 比较）
- [x] 三层次视觉反馈（脉冲光效、新节点光晕、横幅通知）
- [x] 时间线焦点模式（自动对焦变化区域、变化节点/连线高亮、丝滑过渡）
- [x] 时间线增量 simulation 更新（不再每帧重建）
- [x] Wiki库改造（知识图谱tab→Wiki库，新增wiki.js/wiki.css/wiki_parser，支持projects目录，卡片展示+详情弹窗+编辑保存）
- [x] 记忆健康修复激活（空db恢复30条数据，decay公式修正，启动时自动sync）
- [x] 项目文件整理（index.html 215KB→17KB拆成9个静态文件，http_handler.py 1782行→476行拆成4个mixin，删12个垃圾文件，根目录重组）
- [x] 图谱逐级展开优化（减少初始节点数，按层级逐步展开）
- [x] Wiki卡片预览加大+表格渲染优化
- [x] Docker化部署（Dockerfile+docker-compose，一键启动）
- [x] 自动sync机制（5分钟间隔定时同步）
- [x] 前端防抖+增量更新（减少不必要的渲染和请求）
- [x] 演变追踪实现（核心字段：产生时间+版本+更新时间+记忆强度，数据源无产生时间则用采集时间）
- [x] 衰减曲线可视化（/api/decay-trend + decay_history 表 + 前端曲线图）
- [ ] 修复边关系逻辑（当前0条边）
- [ ] 完善记忆健康可视化（健康度评分、认知偏差检测）
- [ ] 浅色主题重写
- [ ] 节点交互优化（拖拽、缩放）

### 交付标准

- 记忆图谱节点数 ≥ 180，边数 ≥ 500
- Wiki库可浏览、编辑、保存知识卡片
- 遗忘曲线可展示且数据准确 ✅
- 支持浅色/深色切换

---

## v2.0 记忆管理

**目标**：让人能够"管"记忆

### 核心功能

| 模块 | 功能 | 状态 |
|------|------|------|
| 记忆增删 | 创建、编辑、删除记忆 | 🔄 部分实现（mutations_mixin.py: CRUD API存在） |
| 分类管理 | 自定义分类、标签体系 | 🔄 基础（primary_cat/secondary_cat） |
| 导入导出 | JSON/MD 格式导入导出 | ✅ Manual Import（document_importer.py + /api/documents/scan） |
| 批量操作 | 批量编辑、删除、归类 | 🔄 /api/memories/bulk-status |
| 高级搜索 | 语义搜索、多条件过滤 | 🔄 简单（/api/memories?status=...&primary=...） |
| **数据管道统一** | unified_store + unified_sync，SQLite统一数据源 | ✅ 已完成 |
| **Honcho sync** | Honcho数据接入unified_sync | ✅ 已完成（sync_honcho） |
| **Recall Capture** | Agent回访记录自动采集 | ✅ 已完成（agent_recall_log + scanner.py） |
| **衰减曲线** | 衰减趋势可视化 | ✅ 已完成（/api/decay-trend） |

### 技术任务

- [x] 数据管道统一（unified_store.py + unified_sync.py，SQLite为统一数据源） ✅
- [x] Honcho数据sync接入unified_sync（sync_honcho函数） ✅
- [x] Recall Capture实现（agent_recall_log表 + recall_capture/scanner.py） ✅
- [x] 衰减曲线可视化（decay_history + /api/decay-trend） ✅
- [x] Manual Import（document_importer.py + /api/documents/scan + /api/documents/extract-stream） ✅
- [x] 记忆 CRUD API（mutations_mixin.py: /api/memories, /api/memories/:id）
- [x] 批量状态更新（/api/memories/bulk-status）
- [ ] 记忆增删完整闭环（CRUD API存在但前端UI未对接）
- [ ] 分类/标签管理界面
- [ ] JSON格式导出
- [ ] 富文本编辑器
- [ ] 记忆关联推荐

### 交付标准

- 支持记忆的完整生命周期管理 🔄（API存在，前端未对接）
- 支持手动导入文档 ✅
- 搜索响应时间 < 200ms
- 统一数据管道稳定运行 ✅（SQLite单一数据源，所有数据源正确sync）

---

## v3.0 服务化输出

**目标**：让其他系统能够"用"记忆

### 核心功能

| 模块 | 功能 | 状态 |
|------|------|------|
| REST API | 记忆读写 API | ✅ 已实现（/api/memories, /api/decay-trend, /api/recall） |
| Agent 集成 | 与 Hermes/Openclaw 对接 | ✅ Hermes双向（读取+sync写回） |
| 多数据源 | 记忆源统一管理 | ✅ MEMORY.md + Honcho + Wiki + Skills |
| 插件系统 | 扩展点设计 | ❌ 未实现 |
| Webhook | 记忆变更通知 | ❌ 未实现 |
| **巩固引擎** | 去重、合并、提炼 | ❌ NOT implemented（代码框架存在但未运行） |
| **遗忘引擎** | 衰减、淘汰、归档 | 🔄 PARTIAL（decay_score计算已实现，状态流转未实现） |
| **分析引擎** | 模式识别、健康评估 | ❌ NOT implemented（代码框架存在但未运行） |

### 技术任务

- [x] RESTful API（/api/memories, /api/meta/entries, /api/decay-trend, /api/recall/stats）
- [x] 演变追踪数据模型纳入API输出（entry_history + version字段）
- [ ] OpenAPI 文档
- [ ] **多数据源适配器**（注意：unified_sync.py已直接编排，Provider interface为遗留代码）
  - [x] File数据源（MEMORY.md/USER.md） ✅
  - [x] Honcho数据源 ✅（sync_honcho）
  - [x] Wiki数据源 ✅
  - [x] Skills数据源 ✅
  - [ ] Mem0 Adapter — 未实现
  - [ ] 变化聚合引擎 — 未实现
  - [ ] 冲突检测与解决策略 — 未实现
- [ ] 记忆变更事件机制
- [ ] 认证与权限控制
- [ ] 插件 SDK 设计

### 交付标准

- 提供完整的 API 文档 ❌（API存在但无正式文档）
- 支持 3+ 数据源 ✅（MEMORY.md / Honcho / Wiki / Skills）
- 多源记忆聚合可视化 ✅（unified_store统一）
- 巩固引擎实际运行 ❌
- 遗忘引擎状态流转 ❌
- 每条记忆附带演变追踪信息 ✅

---

## v4.0 Agent DNA（远期愿景）

**目标**：从"记忆可视化"进化到"Agent DNA测序"

> **核心隐喻**：SelfMind = 测序仪，Agent的DNA = 使用中沉淀的记忆模式

### 设计理念

每个Agent在长期使用中会沉淀出独特的记忆模式——偏好、决策习惯、知识结构、交互风格。这些模式构成了Agent的"DNA"。SelfMind作为"测序仪"，能够：

- **测序**：提取和可视化Agent使用中沉淀的记忆模式（偏好权重、决策路径、知识关联密度）
- **比对**：跨Agent的DNA比对，发现共性模式和独特特征
- **编辑**：基于DNA分析结果，优化Agent的行为配置
- **转录**：将Agent DNA转化为可复用的配置模板，赋能新Agent快速"继承"成熟模式

### 核心功能

| 模块 | 功能 | 状态 |
|------|------|------|
| **DNA测序** | 从记忆沉淀中提取Agent行为模式 | 🔄 概念设计 |
| **DNA比对** | 跨Agent记忆模式差异分析 | ❌ 未实现 |
| **DNA编辑** | 基于模式分析优化Agent配置 | ❌ 未实现 |
| **DNA转录** | Agent模式→可复用配置模板 | ❌ 未实现 |

### 技术任务

- [ ] Agent记忆模式提取算法设计
- [ ] DNA数据模型定义（偏好权重、决策路径、知识关联密度）
- [ ] 跨Agent比对引擎
- [ ] 配置模板生成器
- [ ] 与v3.0 API的衔接设计

---

## 版本依赖

```
v1.0 (可视化)
    │
    ├── 数据管道统一 ✅ → v3.0 多数据源（统一数据源支撑 ✅）
    │
    ├── Honcho sync ✅ → v3.0 服务化（Honcho数据接入 ✅）
    │
    ├── 演变追踪 ✅ → v3.0 服务化（记忆版本化是API的基础 ✅）
    │
    ├── Recall Capture ✅ → v2.0 记忆管理（回访数据支撑遗忘引擎）
    │
    ├── 衰减曲线 ✅ → v2.0 遗忘管理（衰减可视化支撑遗忘决策）
    │
    ├── 边关系修复 → v2.0 记忆管理（需要可视化选择节点）
    │
    ├── Wiki库完成  → v2.0 知识管理（卡片编辑即记忆管理）
    │
    └── Docker化 ✅ → v3.0 服务化（容器化是部署和集成的基础 ✅）
    
v2.0 (管理)
    │
    ├── Manual Import ✅ → v2.0 导入能力
    │
    ├── 记忆增删 🔄 → v3.0 服务化（CRUD API支撑记忆操作）
    │
    └── 分类体系   → v3.0 多数据源（统一分类标准）
    
v3.0 (服务)
    │
    ├── 巩固引擎 ❌ → v3.0 记忆整理服务
    │
    ├── 遗忘引擎 🔄 → v3.0 记忆衰减服务
    │
    ├── 插件系统   → v4.0 Agent DNA（DNA测序需要插件化数据采集）
    │
    └── 记忆模式沉淀 → v4.0 Agent DNA（服务化输出是DNA测序的数据基础）
    
v4.0 (Agent DNA)
    │
    └── DNA转录   → 未来生态扩展（配置模板市场）
```

---

## 里程碑

| 版本 | 时间 | 核心交付 | 状态 |
|------|------|----------|------|
| v1.0 | 当前 ✅ | Wiki库 + 记忆健康激活 + 文件整理 + Docker化 | ✅ 已完成 |
| v1.1 | ✅ | 数据管道统一稳定 + Honcho sync + Recall Capture + 衰减曲线 | ✅ 已完成 |
| v1.2 | ✅ | 演变追踪实现 + Manual Import + CRUD API | ✅ 已完成 |
| v2.0 | 当前 | 记忆增删闭环（前端UI） + 分类管理 + 审查面板 | 🔄 进行中 |
| v2.1 | +1月 | 遗忘引擎状态流转 + 巩固引擎接入运行 | 🔄 |
| v3.0 | +2月 | API文档 + 巩固/遗忘/分析引擎实际运行 | |
| v3.1 | +3月 | 多数据源完善 + 插件系统 | |
| v4.0 | 远期 | Agent DNA测序 + 比对 + 转录 | |

---

## 当前项目结构

```
selfmind/
├── index.html          (17KB shell，从215KB拆分而来)
├── server.py
├── config.json
├── Dockerfile          (Docker化部署)
├── docker-compose.yml  (一键启动配置)
├── data/
│   ├── data.json
│   └── selfmind.db     (SQLite统一数据源，6张表)
├── docs/               (11个md文件)
├── selfmind_app/
│   ├── handlers/        (4个mixin，从1782行http_handler拆分而来)
│   │   ├── stats_mixin.py     (数据统计)
│   │   ├── mutations_mixin.py (CRUD + Import + Sync) 🔄
│   │   ├── engines_mixin.py   (引擎API handler)
│   │   └── v1_mixin.py        (V1兼容接口)
│   ├── providers/       (遗留Provider interface，unified_sync未使用)
│   ├── recall_capture/  ✅ (recall_capture/scanner.py + matcher.py + adapter.py)
│   ├── unified_store.py ✅ (统一存储层，6张表schema)
│   ├── unified_sync.py  ✅ (统一同步层，5分钟自动sync)
│   ├── document_importer.py ✅ (Manual Import)
│   ├── forgetter.py     (遗忘引擎，PARTIAL：decay计算存在但未接入运行循环)
│   ├── consolidator.py  (巩固引擎，NOT impl：代码框架存在)
│   ├── analyzer.py      (分析引擎，NOT impl：代码框架存在)
│   ├── wiki_parser.py
│   └── ...
├── static/
│   ├── css/            (4个)
│   └── js/             (6个，含wiki.js，防抖+增量更新)
├── assets/logo.png
├── requirements.txt
└── LICENSE
```

---

## 技术债务

- [x] 前端组件化（index.html拆成9个静态文件，http_handler拆成4个mixin）
- [x] Docker化部署（Dockerfile+docker-compose）
- [x] 图谱逐级展开优化
- [x] Wiki卡片预览加大+表格渲染
- [x] 自动sync机制（5分钟间隔）
- [x] 前端防抖+增量更新
- [x] 数据管道统一（unified_store + unified_sync）
- [x] Honcho数据sync接入
- [x] Recall Capture实现
- [x] 衰减曲线可视化
- [x] Manual Import（document_importer）
- [x] 记忆 CRUD API（mutations_mixin）
- [ ] 边关系逻辑重构
- [ ] API 文档补全
- [ ] 单元测试覆盖
- [ ] 性能优化（大节点图）
- [ ] 巩固引擎接入运行循环
- [ ] 遗忘引擎状态流转实现
- [ ] Provider interface清理（unified_sync不使用，属于遗留代码）
- [ ] 浅色主题重写