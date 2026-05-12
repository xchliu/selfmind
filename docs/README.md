<p align="center">
  <img src="assets/logo.png" alt="SelfMind" width="200"/>
  <h1 align="center">🧠 SelfMind</h1>
  <p align="center"><strong>Agent DNA 测序仪 — 记录演变，驱动进化</strong></p>
  <p align="center">AI Agent 的记忆过程态管理系统 — 可见 · 可追踪 · 可反哺</p>
  <p align="center">记录记忆的产生、版本变化、更新和衰减，让每个 Agent 形成自己的 DNA</p>
  <p align="center">
    <a href="#-selfmind--认知记忆图谱">中文</a> ·
    <a href="#-selfmind--cognitive-memory-graph">English</a>
  </p>
</p>

<p align="center">
  <a href="#why-selfmind">为什么存在</a> ·
  <a href="#quick-start">快速开始</a> ·
  <a href="#features">核心特性</a> ·
  <a href="MEMORY_TAXONOMY.md">分类设计</a>
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/xchliu/selfmind?style=flat" alt="Stars"/>
  <img src="https://img.shields.io/github/license/xchliu/selfmind" alt="License"/>
</p>

---

## Why SelfMind?

> **SelfMind 不是 DNA 本身，而是 Agent 的 DNA 测序仪。**

Agent 在持续工作中会积累经验、踩过坑、总结出模式——这些过程态记忆就是 Agent 的 DNA。
但大部分 Agent 框架只关注"实时态"（当前需要什么上下文），忽略了"过程态"（记忆怎么演变、哪些在衰减、哪些需要强化）。

**SelfMind 做的就是记录和利用过程态：**

| 特性 | 含义 |
|------|------|
| 🧬 **DNA测序** | 记录记忆的产生时间、版本变化、更新时间、衰减强度——完整的过程态 |
| 👁️ **可视化** | 双螺旋DNA图谱 + 记忆图谱 + Wiki库 + 沉淀页，看清记忆演变轨迹 |
| 🔄 **闭环反哺** | 过程态训练记忆 → 反哺实时态 → Agent 持续进化 |
| 🐳 **Docker化** | 一键容器化部署，热挂载开发，5分钟自动sync |

不同 Agent（Hermes、OpenClaw等）使用久了会形成不同的记忆基因组合——SelfMind 记录的就是这个"用出来的过程"。

---

## What is SelfMind?

**SelfMind 把 AI 的记忆变成可视化的、可交互的知识图谱和 Wiki 库。**

每条记忆是一个节点，关系是连线，分类是颜色。Wiki 库以卡片展示知识，支持详情弹窗、Markdown 渲染和编辑保存。基于认知心理学的 8 大记忆系统分类，让你看清 AI 大脑的全貌。

## Cognitive Memory System

基于认知心理学的记忆分类体系，将 AI 记忆组织为 8 大类 24 子类：

| # | 一级分类 | 英文 | 脑区对应 | 内容 |
|---|---------|------|---------|------|
| 1 | 🧬 自传体记忆 | Autobiographical | 海马体+前额叶 | 身份认同、成长轨迹、行为准则 |
| 2 | 📚 语义记忆 | Semantic | 颞叶皮层 | 行业知识、技术概念、方法论 |
| 3 | 📖 情景记忆 | Episodic | 海马体 | 成功经验、失败教训、关键事件 |
| 4 | ⚙️ 程序性记忆 | Procedural | 基底神经节+小脑 | 技能库（95+技能，四层层级结构） |
| 5 | 👥 社会认知 | Social Cognition | 镜像神经元+杏仁核 | 核心人物、关系网络、沟通偏好 |
| 6 | 💼 工作记忆 | Working Memory | 前额叶皮层 | 活跃项目、待办事项、历史项目 |
| 7 | 🗺️ 空间记忆 | Spatial | 海马体位置细胞 | 系统环境、文件地图、服务拓扑 |
| 8 | ❤️ 情绪记忆 | Emotional | 杏仁核 | 用户情绪、偏好厌恶、信任关系 |

详细设计文档见 [MEMORY_TAXONOMY.md](MEMORY_TAXONOMY.md)。

## IQ System

SelfMind 内置 AI 智商评估系统，参考人类 IQ 分布（均值 100，标准差 15），基于 6 个维度综合计算：

| 维度 | 权重 | 衡量内容 |
|------|------|---------|
| 📦 记忆容量 | 30% | 节点总数的对数增长 |
| 🔗 连接密度 | 25% | 连接数与节点数的比值 |
| 🗂️ 分类覆盖 | 15% | 8 大分类的覆盖率 |
| 📚 知识深度 | 10% | 节点描述的平均长度 |
| 🌐 网络效应 | 10% | 平均每节点的连接数 |
| 🛠️ 技能掌握 | 10% | 技能数量与分类覆盖 |

**IQ 等级对照：**

| IQ 区间 | 等级 |
|---------|------|
| 140~160 | 天才 🧠 |
| 120~140 | 非常聪明 🌟 |
| 110~120 | 中上水平 💡 |
| 100~110 | 正常偏上 📖 |
| 90~100 | 正常水平 📖 |
| 80~90 | 发育中 🌱 |
| 60~80 | 刚觉醒 👶 |
| 40~60 | 沉睡中 💤 |

## 核心架构

> **核心理念：可视化 → 管理 → 服务**

```
SelfMind v1.0 ──→ v2.0 ──→ v3.0
   (看到)        (管到)      (用到)
   toC          toB       to开发者
```

---

### v1.0 可视化深化 👁️

**目标**：让人直观"看到"记忆的全貌

|| 模块 | 功能 | 状态 ||
||------|------|------||
|| 记忆图谱 | 节点/边关系可视化 | 🔄 边关系修复中 |
|| Wiki 库 | 卡片展示+详情弹窗+Markdown渲染+编辑保存 | ✅ 已完成 |
|| 记忆健康 | 遗忘曲线、衰减预警、30条数据、自动sync | ✅ 已激活 |
|| 记忆沉淀 | U型6层路径+激活路径可视化 | ✅ 已完成 |
|| 时间轴 | 记忆时间线播放 | ✅ 基础完成 |
|| **焦点模式** | 时间线播放自动对焦变化区域 | ✅ 已完成 |
|| 主题切换 | 浅色/深色主题 | 🔄 优化中 |
|| **实时感知** | 源文件变化自动检测与图谱刷新 | ✅ 已完成 |

**核心特性**：
- 🧠 **认知记忆体系** — 8 大分类 24 子类，基于认知心理学
- 🕸️ **力导向图谱** — D3.js 驱动，物理模拟，层级自然聚集
- 🧬 **IQ 智商系统** — 参考人类标准的 AI 智商评估，6 维度计算
- 📖 **Wiki 库** — 卡片展示 + 详情弹窗 + Markdown 渲染 + 编辑保存，替代知识图谱
- 📊 **记忆健康仪表盘** — 30 条数据、衰减公式修正、启动自动 sync
- 📉 **记忆沉淀** — U 型 6 层路径 + 激活路径可视化
- 🔍 **焦点模式** — 时间线播放时自动对焦到新增节点，变化高亮（节点✦标记+绿色脉冲光环，连线荧光绿高亮）
- 🔄 **实时感知** — 自动检测 MEMORY.md/USER.md 变化并刷新图谱，无需手动操作
- 🔄 **演变追踪** — 核心字段：产生时间 + 版本 + 更新时间 + 记忆强度

---

### v2.0 记忆管理 ✏️

**目标**：让人能够"管"记忆

|| 模块 | 功能 | 状态 ||
||------|------|------||
|| 记忆增删 | 创建、编辑、删除记忆 | 🔄 基础实现（Wiki 库编辑） ||
|| 分类管理 | 自定义分类、标签体系 | 🔄 基础 ||
|| 导入导出 | JSON/MD 格式导入导出 | ❌ 未实现 ||
|| 批量操作 | 批量编辑、删除、归类 | ❌ 未实现 ||
|| 高级搜索 | 语义搜索、多条件过滤 | 🔄 简单 |

---

### v3.0 服务化输出 🚀

**目标**：让其他系统能够"用"记忆

| 模块 | 功能 | 状态 |
|------|------|------|
| REST API | 记忆读写 API | ✅ 已实现（13个端点） |
| Agent 集成 | 与 Hermes/Openclaw 对接 | 🔄 Hermes 读取 |
| 多数据源 | 记忆源统一管理 | 🔄 unified_store + unified_sync 进行中 |
| 插件系统 | 扩展点设计 | ❌ 未实现 |
| Webhook | 记忆变更通知 | ❌ 未实现 |

---

### 🚚 可移植 — 一个文件夹走天下

- 💾 **纯文本格式** — Markdown 文件存储，无专有格式
- 📦 **SQLite 数据源** — selfmind.db 统一存储，SQLite 成为唯一数据源方向
- 📤 **随时导出** — 一键导出为 JSON/CSV，迁移无压力
- 🔌 **多框架兼容** — 抽象接口设计，轻松适配不同 Agent 框架

### 🎨 体验

- 🎯 **分类导航** — 顶部 8 大分类标签，底部指示条高亮
- ⏱️ **时间轴** — 底部全宽时间刻度，按时间回溯记忆
- 🌗 **明暗主题** — 毛玻璃效果，现代极简设计
- 📖 **Wiki 库 Tab** — 卡片展示、详情弹窗、Markdown 渲染、编辑保存

### V2: Agent 睡眠系统 (Beta)

> 从"可视化工具"升级为 Agent 的"睡眠系统"

- 🔄 **巩固引擎 (Consolidator)** — 去重、合并、提炼、冲突检测
- 📉 **遗忘引擎** — 基于艾宾浩斯曲线的重要性衰减（衰减公式已修正）
- 📊 **记忆健康仪表盘** — 30 条数据、衰减公式修正、启动自动 sync
- 🛡️ **人工审查面板** — 可视化干预，确认/拒绝自动操作
- 💾 **SQLite 元数据库** — 记忆元数据持久化，版本快照
- 🤖 **LLM 驱动的智能合并** — AI 自动生成合并/压缩建议
- 🔄 **数据管道统一** — unified_store + unified_sync，SQLite 成为唯一数据源方向
- 🔄 **演变追踪** — 核心字段：产生时间 + 版本 + 更新时间 + 记忆强度

详细设计见 [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md)。

## Wiki Library

SelfMind 支持 Wiki 库 tab：**卡片展示 + 详情弹窗 + Markdown 渲染 + 编辑保存**，替代了原有的知识图谱视图。

Wiki 库基于 [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)（Karpathy 提出的持久知识库模式），将 markdown 知识库以卡片形式展示，支持点击查看详情、Markdown 渲染和在线编辑保存。

### Wiki 结构

```
wiki/
├── SCHEMA.md       # 规则和约定
├── index.md        # 内容目录
├── log.md          # 操作日志
├── entities/       # 实体页面（人、公司、模型）
├── concepts/       # 概念页面
├── comparisons/    # 对比分析
└── queries/        # 查询结果
```

### 节点类型

| 类型 | 颜色 | 说明 |
|------|------|------|
| 📖 Entity | 蓝色 | 实体（公司、产品、人物） |
| 💡 Concept | 紫色 | 概念（技术、方法、理论） |
| ⚖️ Comparison | 橙色 | 对比分析 |
| 🔍 Query | 青色 | 查询结果 |
| 🏷️ Tag | 灰色 | 标签节点 |

### 关系类型

- **`[[wikilinks]]`** — 页面之间的引用关系
- **Tags** — 页面与标签的关联

### Wiki 配置

在 `config.json` 中设置 wiki 路径：

```json
{
  "wiki": {
    "path": "~/Documents/aiworkspace/wiki"
  }
}
```

或通过环境变量 `SELFMIND_WIKI_PATH` 指定。

## Quick Start

### Prerequisites

- Python 3.8+

### Install & Run

```bash
git clone https://github.com/xchliu/selfmind.git
cd selfmind
pip install -r requirements.txt

# Launch
python server.py
```

Open **http://localhost:3002** in your browser.

### 项目结构

```text
selfmind/
├── index.html           # 前端 shell（17KB）
├── server.py            # 后端入口
├── config.json          # 运行配置
├── data/
│   ├── data.json        # 图谱数据缓存
│   └── selfmind.db      # 统一 SQLite 数据源
├── docs/                # 文档目录
├── selfmind_app/        # 后端模块
├── static/              # 前端 CSS/JS（模块化9个文件）
├── assets/logo.png
├── requirements.txt
├── LICENSE
```

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/stats` | GET | 图谱统计信息 |
| `/api/poll` | GET | 变化轮询 |
| `/api/memories` | GET | 全部记忆 |
| `/api/wiki/pages` | GET | Wiki 页面列表 |
| `/api/wiki/page` | GET | 单个 Wiki 页面内容 |
| `/api/wiki/page` | PUT | 保存 Wiki 页面编辑 |
| `/api/meta/health` | GET | 记忆健康数据 |
| `/api/meta/entries` | GET | 元数据条目 |
| `/api/meta/evolution` | GET | 演变追踪数据 |
| `/api/consolidate` | POST | 触发巩固 |
| `/api/forget` | POST | 触发遗忘 |
| `/api/analyze` | POST | 触发分析 |
| `/api/meta/sync` | POST | 触发元数据同步 |

### 配置

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `HERMES_HOME` | `~/.hermes` | Hermes 配置目录 |
| `SELFMIND_SOURCE_MODE` | `auto` | `auto` 读取全部 profile，`single` 读取一个 |
| `SELFMIND_PROFILE` | `hermes` | 当前 Profile 名称 |

### Memory Format

记忆文件使用 `§` 分隔，支持分类标签：

```markdown
[autobiographical/identity] 我是小苏/苏格拉底，AI 部门管理助手
§
[social/key_people] AI部门负责人
§
[spatial/filesystem] SelfMind 项目存放在 ~/Documents/selfmind/
```

## How It Works

```
Memory Files              Backend                    Browser
┌──────────────┐   parse  ┌──────────────────┐ JSON  ┌──────────────┐
│ MEMORY.md    │ ───────→ │ parser.py        │ ────→ │  index.html  │
│ USER.md      │          │  - 8大分类解析    │       │  (17KB shell)│
│ Skills/*.md  │          │  - 技能层级构建   │       │  D3.js 图谱  │
│ Wiki/*.md    │          │  - IQ 算法计算    │       │  IQ 仪表盘   │
│ selfmind.db  │          │  - Wiki 图谱构建  │       │  Wiki 库 tab │
└──────────────┘          │  - 记忆健康/沉淀  │       │  记忆健康    │
                          │ http_handler.py   │       │  记忆沉淀    │
                          │ wiki_parser.py    │       │  模块化前端  │
                          │ unified_store.py  │       └──────────────┘
                          │ server.py (entry) │
                          └──────────────────┘
```

1. **解析记忆** — 读取 MEMORY.md / USER.md，按 `§` 分段，识别 `[分类/子分类]` 标签
2. **扫描技能** — 遍历 `~/.hermes/skills/` 目录，解析 SKILL.md 的 YAML frontmatter
3. **构建图谱** — 生成节点和连线，记忆 + 技能四层层级结构
4. **计算 IQ** — 6 维度加权评估，映射到人类 IQ 标准
5. **解析 Wiki** — 扫描 Wiki 目录，解析 frontmatter + `[[wikilinks]]`，构建卡片展示
6. **记忆健康** — 衰减公式计算、30 条健康数据、启动自动 sync
7. **记忆沉淀** — U 型 6 层路径 + 激活路径可视化
8. **渲染展示** — D3.js 力导向图，Wiki 库 tab，分类着色，交互式探索

### Backend Structure

```text
selfmind_app/
├── config.py            # 配置加载、Profile 管理
├── parser.py            # 记忆解析 + 技能扫描 + 图谱构建 + IQ 计算
├── wiki_parser.py       # Wiki 知识库解析 + 卡片构建
├── memory_store.py      # 记忆存储管理（CRUD + 同步）
├── document_importer.py # 文档导入 + LLM 记忆提取
├── http_handler.py      # API 端点入口（拆为 4 个 mixin）
│   ├── stats_handler.py     # /api/stats, /api/poll
│   ├── memories_handler.py  # /api/memories
│   ├── wiki_handler.py      # /api/wiki/pages, /api/wiki/page
│   └── meta_handler.py      # /api/meta/health, /api/meta/entries, /api/meta/evolution, /api/meta/sync
├── consolidator.py      # V2 巩固引擎（去重/合并/冲突检测）
├── metadata_db.py       # V2 SQLite 元数据库（记忆状态/快照）
├── analytics.py         # V2 遗忘引擎（衰减分数计算）
├── unified_store.py     # 统一数据管道（SQLite 为唯一数据源）
├── unified_sync.py      # 统一同步逻辑（启动自动 sync）

server.py                # 服务入口（默认 3002 端口）
```

### Frontend Structure

```text
static/
├── css/
│   ├── main.css          # 全局布局与基础样式
│   ├── graph.css         # 图谱与力导向图样式
│   ├── wiki.css          # Wiki 库卡片与详情弹窗样式
│   ├── meta.css          # 记忆健康与沉淀路径样式
├── js/
│   ├── app.js            # 主入口、初始化与 Tab 切换
│   ├── graph.js          # 记忆图谱（D3.js 力导向图）
│   ├── wiki.js           # Wiki 库（卡片展示 + 详情弹窗 + Markdown 渲染 + 编辑保存）
│   ├── health.js         # 记忆健康仪表盘
│   ├── consolidation.js  # 记忆沉淀页（U型6层路径 + 激活路径可视化）
│   ├── utils.js          # 通用工具函数

index.html               # 前端 shell（17KB，较原版缩减 93.7%）
```

## Interactions

| Action | Effect |
|--------|--------|
| **Hover** 节点 | 高亮关联节点和连线 |
| **Click** 节点 | 打开详情面板，技能节点展开标签 |
| **Drag** 节点 | 拖拽移动（固定位置） |
| **Double-click** | 释放固定的节点 |
| **Scroll** | 缩放 |
| **拖拽画布** | 平移视图 |
| **分类标签** | 过滤显示该分类节点 |
| **IQ 圆球** | 点击展开智商详情 |
| **时间线播放** | 自动对焦变化区域，新增节点✦标记+绿色脉冲，新增连线荧光绿高亮 |
| **跳到最新** | 镜头回到全局视角，清除所有变化标记 |

## Roadmap

> 详细版本规划见 [ROADMAP.md](../ROADMAP.md)

### v1.0 可视化深化（当前）

- [x] 记忆图谱力导向可视化
- [x] Wiki 库 tab（卡片展示+详情弹窗+Markdown渲染+编辑保存）
- [x] IQ 智商系统
- [x] 时间轴功能
- [x] 时间线焦点模式 — 播放时自动对焦变化区域，变化节点/连线高亮
- [x] 记忆健康模块激活（30条数据、衰减公式修正、启动自动sync）
- [x] 记忆沉淀页（U型6层路径+激活路径可视化）
- [x] 前端模块化（index.html 缩减93.7%，拆为9个CSS/JS文件）
- [x] 后端 http_handler 拆为4个 mixin
- [x] 数据管道统一（unified_store + unified_sync，SQLite成为唯一数据源方向）
- [ ] 修复边关系逻辑（当前0条边）
- [ ] 浅色主题重写

### v2.0 记忆管理

- [x] Wiki 库编辑保存功能
- [ ] 记忆 CRUD API 完善
- [ ] 分类/标签管理界面
- [ ] 导入导出功能（JSON/MD）
- [ ] 批量选择与操作
- [ ] 记忆关联推荐
- [ ] 演变追踪系统（核心字段：产生时间+版本+更新时间+记忆强度）

### v3.0 服务化输出

- [x] REST API 已实现（13个端点）
- [ ] OpenAPI 文档
- [ ] 多数据源适配器（Hermes/Openclaw/Honcho）
- [ ] 记忆变更事件机制（Webhook）
- [ ] 插件 SDK 设计

### 技术债务

- [ ] 边关系逻辑重构
- [x] 前端组件化（已完成：9个CSS/JS文件，index.html缩减93.7%）
- [ ] API 文档补全
- [ ] 单元测试覆盖
- [ ] 性能优化（大节点图）

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE)

---

<p align="center">
  Built with 🧠 by <a href="https://github.com/xchliu">xchliu</a>
</p>

---

<a id="-selfmind--cognitive-memory-graph"></a>

# 🧠 SelfMind — Cognitive Memory Graph

**See what your AI really thinks.**

An AI memory visualization system based on cognitive psychology — turning AI's brain into an interactive knowledge graph.

## What is SelfMind?

AI assistants accumulate memories during work — user preferences, project context, behavioral rules, relationships, skill libraries. But these memories are invisible.

**SelfMind makes AI memory visible and interactive as a knowledge graph and Wiki Library.**

Each memory is a node, relationships are links, categories are colors. The Wiki Library presents knowledge as cards with detail popups, Markdown rendering, and edit/save. Based on 8 cognitive memory systems from psychology, giving you a complete picture of the AI's brain.

## Cognitive Memory System

Based on cognitive psychology, AI memory is organized into 8 categories with 24 subcategories:

| # | Category | Brain Region | Content |
|---|----------|-------------|---------|
| 1 | 🧬 Autobiographical | Hippocampus + Prefrontal | Identity, growth trajectory, principles |
| 2 | 📚 Semantic | Temporal Cortex | Domain knowledge, technical concepts, methodologies |
| 3 | 📖 Episodic | Hippocampus | Successes, failures, key milestones |
| 4 | ⚙️ Procedural | Basal Ganglia + Cerebellum | 95+ skills in 4-layer hierarchy |
| 5 | 👥 Social Cognition | Mirror Neurons + Amygdala | Key people, relationships, communication preferences |
| 6 | 💼 Working Memory | Prefrontal Cortex | Active projects, backlog, archived projects |
| 7 | 🗺️ Spatial | Place Cells | System environment, file map, service topology |
| 8 | ❤️ Emotional | Amygdala | User mood, likes/dislikes, trust relationships |

See [MEMORY_TAXONOMY.md](MEMORY_TAXONOMY.md) for the full design document.

## IQ System

SelfMind includes an AI IQ assessment system, referenced against human IQ distribution (mean 100, σ 15), calculated across 6 dimensions:

| Dimension | Weight | Measures |
|-----------|--------|----------|
| 📦 Memory Capacity | 30% | Logarithmic growth of total nodes |
| 🔗 Connection Density | 25% | Links-to-nodes ratio |
| 🗂️ Category Coverage | 15% | Coverage of 8 major categories |
| 📚 Knowledge Depth | 10% | Average length of node descriptions |
| 🌐 Network Effect | 10% | Average connections per node |
| 🛠️ Skill Mastery | 10% | Skill count and category coverage |

**IQ Scale:**

| IQ Range | Level |
|----------|-------|
| 140~160 | Genius 🧠 |
| 120~140 | Very Smart 🌟 |
| 110~120 | Above Average 💡 |
| 100~110 | Slightly Above Normal 📖 |
| 90~100 | Normal 📖 |
| 80~90 | Developing 🌱 |
| 60~80 | Just Awakened 👶 |
| 40~60 | Dormant 💤 |

## Features

- 🧠 **Cognitive Memory System** — 8 categories, 24 subcategories based on cognitive psychology
- 🧬 **IQ System** — Human-referenced AI IQ assessment, 6-dimension calculation
- 🛠️ **Skill Graph** — 95+ skills in 4-layer hierarchy (root → category → subcategory → skill)
- 🕸️ **Force-Directed Graph** — D3.js powered, physics simulation, hierarchical clustering
- 📖 **Wiki Library** — Card display + detail popup + Markdown rendering + edit/save, replacing Knowledge Graph
- 📊 **Memory Health Dashboard** — 30 health entries, decay formula correction, auto-sync on startup
- 📉 **Memory Consolidation** — U-shaped 6-layer path + activation path visualization
- 🔍 **Focus Mode** — Timeline auto-focuses on changed areas, new nodes highlighted with ✦ marker + green pulse, new links in fluorescent green
- 🔄 **Evolution Tracking** — Core fields: creation time + version + update time + memory strength
- 🔍 **Search & Filter** — Filter by name, description, or category
- 🎯 **Category Navigation** — Top nav with 8 category tabs, bottom indicator highlight
- ⏱️ **Timeline** — Full-width bottom timeline for temporal memory browsing
- 🎨 **Dark Theme** — Glassmorphism effects, modern minimalist design
- 💾 **Persistent Cache** — Parse once, load instantly

## Quick Start

### Prerequisites

- Python 3.8+

### Install & Run

```bash
git clone https://github.com/xchliu/selfmind.git
cd selfmind
pip install -r requirements.txt

# Launch
python server.py
```

Open **http://localhost:3002** in your browser.

### Project Structure

```text
selfmind/
├── index.html           # Frontend shell (17KB)
├── server.py            # Backend entry
├── config.json          # Runtime config
├── data/
│   ├── data.json        # Graph data cache
│   └── selfmind.db      # Unified SQLite data source
├── docs/                # Documentation
├── selfmind_app/        # Backend modules
├── static/              # Frontend CSS/JS (9 modular files)
├── assets/logo.png
├── requirements.txt
├── LICENSE
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stats` | GET | Graph statistics |
| `/api/poll` | GET | Poll for changes |
| `/api/memories` | GET | All memories |
| `/api/wiki/pages` | GET | Wiki page list |
| `/api/wiki/page` | GET | Single wiki page content |
| `/api/wiki/page` | PUT | Save wiki page edits |
| `/api/meta/health` | GET | Memory health data |
| `/api/meta/entries` | GET | Metadata entries |
| `/api/meta/evolution` | GET | Evolution tracking data |
| `/api/consolidate` | POST | Trigger consolidation |
| `/api/forget` | POST | Trigger forgetting |
| `/api/analyze` | POST | Trigger analysis |
| `/api/meta/sync` | POST | Trigger metadata sync |

### Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `HERMES_HOME` | `~/.hermes` | Hermes profile home directory |
| `SELFMIND_SOURCE_MODE` | `auto` | `auto` reads all profiles, `single` reads one |
| `SELFMIND_PROFILE` | `hermes` | Active profile name |

### Memory Format

Memory files use `§` as separator with category tags:

```markdown
[autobiographical/identity] I am an AI department management assistant
§
[social/key_people] AI Department Head
§
[spatial/filesystem] SelfMind project at ~/Documents/selfmind/
```

## How It Works

```
Memory Files              Backend                    Browser
┌──────────────┐   parse  ┌──────────────────┐ JSON  ┌──────────────┐
│ MEMORY.md    │ ───────→ │ parser.py        │ ────→ │  index.html  │
│ USER.md      │          │  - 8-category    │       │  (17KB shell)│
│ Skills/*.md  │          │  - skill hierarchy│      │  D3.js graph │
│ Wiki/*.md    │          │  - IQ algorithm  │       │  IQ dashboard│
│ selfmind.db  │          │  - wiki cards    │       │  Wiki Library│
└──────────────┘          │  - health/consol │       │  Memory Health│
                          │ http_handler.py   │       │  Consolidation│
                          │ wiki_parser.py    │       │  Modular UI  │
                          │ unified_store.py  │       └──────────────┘
                          │ server.py (entry) │
                          └──────────────────┘
```

## Interactions

|| Action | Effect |
|--------|--------|
| **Hover** node | Highlight connected nodes and links |
| **Click** node | Open detail panel, expand skill labels |
| **Drag** node | Move and pin position |
| **Double-click** | Release pinned node |
| **Scroll** | Zoom in/out |
| **Drag canvas** | Pan view |
| **Category tab** | Filter to show that category |
| **IQ ball** | Click to expand IQ details |
| **Timeline play** | Auto-focus on changed areas, new nodes ✦ + green pulse, new links fluorescent green |
| **Jump to latest** | Reset camera to global view, clear change markers |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE)

---

<p align="center">
  Built with 🧠 by <a href="https://github.com/xchliu">xchliu</a>
</p>
