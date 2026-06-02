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
└─────────────┴───────────────────────────────────────────┘
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
| Wiki库双区布局 | 焦点区（项目/黑板）+ 档案区（实体/日报折叠） | ✅ 已完成 |
| Wiki索引修复 | promotion/nous/blackboard/daily-report目录入索引 | ✅ 已完成 |
| 记忆健康 | 遗忘曲线、衰减预警 | ✅ 已修复激活 |
| **焦点模式** | 时间线播放自动对焦变化区域 | ✅ 已完成 |
| 主题切换 | 浅色/深色主题 | ✅ 浅色版完成 |
| **实时感知** | 源文件变化自动检测与图谱刷新 | ✅ 已完成 |
| **记忆沉淀** | U型6层沉淀路径+激活路径可视化 | ✅ 已完成 |
| **演变追踪** | 记忆产生时间+版本+更新时间+记忆强度 | ✅ 已完成 |
| **图谱逐级展开** | 节点按层级逐步展开 | ✅ 已完成 |
| **Wiki卡片优化** | 卡片预览加大+表格渲染支持 | ✅ 已完成 |
| **Docker化部署** | 容器化打包，一键启动 | ✅ 已完成 |
| **Agent切换** | 标题区下拉菜单一键切换Agent | ✅ 已完成 |
| **多Agent独立数据库** | 每个Agent独立selfmind_{id}.db，wiki共享 | ✅ 已完成 |
| **Gateway发现** | 输入Gateway地址自动探测Agent信息+路径验证 | ✅ 已完成 |
| **多Agent支持** | 苏格拉底+小亚+柏拉图+Grace，动态配置 | ✅ 已完成 |
| **Agent DNA页** | 基因组成+演变事件流+DNA时间线 | ✅ 已完成 |
| **衰减曲线可视化** | 记忆衰减趋势曲线图（per-agent独立曲线） | ✅ 已完成 |
| **分类衰减曲线** | 每个分类的sparkline迷你曲线替代进度条 | ✅ 已完成 |
| **同步目标扩展** | Hermes/OpenClaw/柏拉图/小亚四卡片 | ✅ 已完成 |

### 技术任务

- [x] 前端自动轮询（15s 间隔检测源文件 mtime 变化）
- [x] 后端 `/api/poll` 接口（轻量 mtime hash 比较）
- [x] 三层次视觉反馈（脉冲光效、新节点光晕、横幅通知）
- [x] 时间线焦点模式（自动对焦变化区域、变化节点/连线高亮、丝滑过渡）
- [x] 时间线增量 simulation 更新（不再每帧重建）
- [x] Wiki库改造（知识图谱tab→Wiki库，支持projects目录，卡片展示+详情弹窗+编辑保存）
- [x] 记忆健康修复激活（空db恢复30条数据，decay公式修正，启动时自动sync）
- [x] 项目文件整理（index.html拆成9个静态文件，http_handler拆成4个mixin）
- [x] Docker化部署（Dockerfile+docker-compose，一键启动）
- [x] 自动sync机制（5分钟间隔定时同步）
- [x] 前端防抖+增量更新（减少不必要的渲染和请求）
- [x] 演变追踪实现（核心字段：产生时间+版本+更新时间+记忆强度）
- [x] 衰减曲线可视化（/api/decay-trend + decay_history + 前端曲线图）
- [x] 分类卡片sparkline曲线替代进度条（/api/decay-trend-by-category + SVG sparkline）
- [x] 多Agent独立数据库（selfmind_{agent_id}.db per agent，wiki共享）
- [x] 切换Agent时衰减曲线+健康数据联动刷新
- [x] Wiki库双区布局（焦点区：项目/黑板/查询；档案区：实体/概念/日报折叠）
- [x] Wiki索引修复（promotion/nous/blackboard/daily-report目录+frontmatter+index.md）
- [x] 同步目标扩展（柏拉图+小亚+Hermes+OpenClaw四卡片数据驱动）
- [x] Y轴固定0~100%（不同agent衰减曲线位置差异可见）
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
| 记忆增删 | 创建、编辑、删除记忆 | 🔄 部分实现（mutations_mixin.py: CRUD API存在，前端UI对接进行中） |
| 分类管理 | 自定义分类、标签体系 | 🔄 基础（primary_cat/secondary_cat） |
| 导入导出 | JSON/MD 格式导入导出 | ✅ Manual Import（document_importer.py + /api/documents/scan） |
| 批量操作 | 批量编辑、删除、归类 | 🔄 /api/memories/bulk-status |
| 高级搜索 | 语义搜索、多条件过滤 | 🔄 简单（/api/memories?status=...&primary=...） |
| **数据管道统一** | unified_store + unified_sync，SQLite统一数据源 | ✅ 已完成 |
| **Honcho sync** | Honcho数据接入unified_sync | ✅ 已完成 |
| **Recall Capture** | Agent回访记录自动采集 | ✅ 已完成 |
| **衰减曲线** | 衰减趋势可视化（per-agent） | ✅ 已完成 |
| **分类曲线** | 每个分类sparkline曲线 | ✅ 已完成 |

### 技术任务

- [x] 数据管道统一 ✅
- [x] Honcho数据sync接入 ✅
- [x] Recall Capture实现 ✅
- [x] 衰减曲线可视化 ✅
- [x] Manual Import ✅
- [x] 记忆 CRUD API ✅
- [x] 批量状态更新 ✅
- [x] 分类衰减曲线（sparkline替代进度条） ✅
- [ ] 记忆增删完整闭环（小亚Kanban t_d8eef6ec 进行中：编辑/删除按钮+创建模态框+批量操作+sparkline点击筛选）
- [ ] 分类/标签管理界面
- [ ] JSON格式导出
- [ ] 富文本编辑器
- [ ] 记忆关联推荐

### 交付标准

- 支持记忆的完整生命周期管理 🔄（API存在，前端对接进行中）
- 支持手动导入文档 ✅
- 搜索响应时间 < 200ms
- 统一数据管道稳定运行 ✅
- 每个Agent独立数据库 ✅

---

## v3.0 服务化输出

**目标**：让其他系统能够"用"记忆

### 核心功能

| 模块 | 功能 | 状态 |
|------|------|------|
| REST API | 记忆读写 API | ✅ 已实现 |
| Agent 集成 | 与 Hermes/Openclaw/柏拉图 对接 | ✅ Hermes双向+柏拉图/小亚同步目标 |
| 多数据源 | 记忆源统一管理 | ✅ MEMORY.md + Honcho + Wiki + Skills |
| 多Agent独立存储 | 每个Agent独立数据库，wiki共享 | ✅ 已实现 |
| 插件系统 | 扩展点设计 | ❌ 未实现 |
| Webhook | 记忆变更通知 | ❌ 未实现 |
| **巩固引擎** | 去重、合并、提炼 | ❌ NOT implemented |
| **遗忘引擎** | 衰减、淘汰、归档 | 🔄 PARTIAL（decay_score+曲线+sparkline已实现，状态流转未实现） |
| **分析引擎** | 模式识别、健康评估 | ❌ NOT implemented |
| **理论基础** | 记忆引擎数学模型论文 | 🔄 柏拉图撰写中（Kanban t_0f730a82） |

### 技术任务

- [x] RESTful API ✅
- [x] 演变追踪数据模型纳入API输出 ✅
- [x] 多Agent独立数据库（selfmind_{agent_id}.db） ✅
- [x] 切换Agent时历史衰减数据迁移 ✅
- [ ] OpenAPI 文档
- [ ] **多数据源适配器**（unified_sync已直接编排，Provider interface为遗留代码）
  - [x] File数据源 ✅
  - [x] Honcho数据源 ✅
  - [x] Wiki数据源 ✅
  - [x] Skills数据源 ✅
  - [ ] Mem0 Adapter
  - [ ] 变化聚合引擎
  - [ ] 冲突检测与解决策略
- [ ] 记忆变更事件机制
- [ ] 认证与权限控制
- [ ] 插件 SDK 设计

### 交付标准

- 提供完整的 API 文档 ❌
- 支持 4+ 数据源 ✅（MEMORY.md / Honcho / Wiki / Skills）
- 多源记忆聚合可视化 ✅
- 多Agent独立存储 ✅（hermes/aris/plato/grace各自数据库）
- 巩固引擎实际运行 ❌
- 遗忘引擎状态流转 ❌
- 理论基础论文 🔄（柏拉图撰写中）

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
    ├── 数据管道统一 ✅ → v3.0 多数据源
    │
    ├── Honcho sync ✅ → v3.0 服务化
    │
    ├── 演变追踪 ✅ → v3.0 服务化
    │
    ├── Recall Capture ✅ → v2.0 记忆管理
    │
    ├── 衰减曲线 ✅ → v2.0 遗忘管理
    │
    ├── 分类sparkline ✅ → v2.0 记忆管理（分类级别衰减可视化）
    │
    ├── 多Agent独立DB ✅ → v2.0/v3.0（Agent记忆隔离是管理和服务的基础）
    │
    ├── Wiki双区布局 ✅ → v2.0 知识管理
    │
    ├── 边关系修复 → v2.0 记忆管理
    │
    └── Docker化 ✅ → v3.0 服务化
    
v2.0 (管理)
    │
    ├── Manual Import ✅ → v2.0 导入能力
    │
    ├── 记忆增删 🔄 → v3.0 服务化（小亚进行中）
    │
    └── 分类体系 → v3.0 多数据源
    
v3.0 (服务)
    │
    ├── 理论基础 🔄 → v3.0/v4.0（柏拉图撰写中）
    │
    ├── 巩固引擎 ❌ → v3.0 记忆整理服务
    │
    ├── 遗忘引擎 🔄 → v3.0 记忆衰减服务
    │
    ├── 插件系统 → v4.0 Agent DNA
    │
    └── 记忆模式沉淀 → v4.0 Agent DNA
    
v4.0 (Agent DNA)
    │
    └── DNA转录 → 未来生态扩展
```

---

## 里程碑

| 版本 | 时间 | 核心交付 | 状态 |
|------|------|----------|------|
| v1.0 | ✅ | Wiki库 + 记忆健康激活 + 文件整理 + Docker化 | ✅ 已完成 |
| v1.1 | ✅ | 数据管道统一 + Honcho sync + Recall Capture + 衰减曲线 | ✅ 已完成 |
| v1.2 | ✅ | 演变追踪 + Manual Import + CRUD API + 多Agent独立DB | ✅ 已完成 |
| v1.3 | ✅ | 分类sparkline曲线 + Wiki双区布局 + 理论基础启动 | ✅ 已完成 |
| v1.4 | ✅ | **认知差距检测（Should-Know）** — 信号B推理引擎 + API + 前端可视化，从Memory/wiki推理"你应该知道什么"，红/黄/绿三色标签 | ✅ 已完成 |
| v2.0 | 当前 | 记忆增删闭环（小亚进行中） + 分类管理 + 审查面板 | 🔄 进行中 |
| v2.1 | +1月 | 遗忘引擎状态流转 + 巩固引擎接入运行 | 🔄 |
| v3.0 | +2月 | 理论论文完成 + API文档 + 巩固/遗忘/分析引擎实际运行 | |
| v3.1 | +3月 | 多数据源完善 + 插件系统 | |
| v4.0 | 远期 | Agent DNA测序 + 比对 + 转录 | |

---

## 当前项目结构

```
selfmind/
├── index.html          (17KB shell)
├── server.py           (按active_profile选择selfmind_{id}.db)
├── config.json         (agents配置：hermes/aris/plato/grace)
├── Dockerfile
├── docker-compose.yml
├── data/
│   ├── data.json
│   ├── selfmind.db     (旧共享数据库，保留做历史数据迁移源)
│   ├── selfmind_hermes.db  (hermes独立数据库)
│   ├── selfmind_aris.db    (aris独立数据库)
│   ├── selfmind_plato.db   (plato独立数据库)
│   └── selfmind_grace.db   (grace独立数据库)
├── docs/
├── selfmind_app/
│   ├── handlers/
│   │   ├── stats_mixin.py
│   │   ├── mutations_mixin.py (CRUD + Import + Sync + Agent切换 + switch_db)
│   │   ├── engines_mixin.py
│   │   └── v1_mixin.py
│   ├── providers/       (遗留，待清理)
│   ├── recall_capture/  ✅
│   ├── unified_store.py ✅ (6张表schema + switch_db方法)
│   ├── unified_sync.py  ✅
│   ├── document_importer.py ✅
│   ├── forgetter.py     (PARTIAL)
│   ├── consolidator.py  (NOT impl)
│   ├── analyzer.py      (NOT impl)
│   ├── wiki_parser.py   ✅ (13个目录扫描：含promotion/nous/blackboard等)
│   ├── memory_store.py  ✅ (sync_to_hermes/openclaw/plato)
│   └── ...
├── static/
│   ├── css/            (4个)
│   └── js/             (6个+wiki.js v14)
├── assets/logo.png
├── requirements.txt
└── LICENSE
```

---

## 技术债务

- [x] 前端组件化
- [x] Docker化部署
- [x] 图谱逐级展开优化
- [x] Wiki卡片预览加大+表格渲染
- [x] 自动sync机制
- [x] 前端防抖+增量更新
- [x] 数据管道统一
- [x] Honcho数据sync接入
- [x] Recall Capture实现
- [x] 衰减曲线可视化
- [x] Manual Import
- [x] 记忆 CRUD API
- [x] 分类sparkline曲线
- [x] 多Agent独立数据库
- [x] Wiki双区布局
- [x] Wiki索引修复（promotion/nous/blackboard）
- [x] 同步目标扩展（柏拉图+小亚）
- [x] 每日自动git提交（独立脚本cron，不依赖LLM/企微）
- [ ] 边关系逻辑重构
- [ ] API 文档补全
- [ ] 单元测试覆盖
- [ ] 性能优化（大节点图）
- [ ] 巩固引擎接入运行循环
- [ ] 遗忘引擎状态流转实现
- [ ] Provider interface清理
- [ ] 浅色主题重写

---

## 团队分工

| 成员 | 角色 | 当前任务 |
|------|------|----------|
| 苏哥（hermes） | PM/需求/调度 | 项目整体推进、文档对齐、基础设施 |
| 柏拉图（plato） | 架构/评审/理论 | 理论基础论文撰写（Kanban t_0f730a82） |
| 小亚（aris） | 开发/实现 | 记忆增删前端UI闭环（Kanban t_d8eef6ec） |