<p align="center">
  <h1 align="center">🧠 SelfMind</h1>
  <p align="center"><strong>See what your AI really thinks.</strong></p>
  <p align="center">基于认知心理学的 AI 记忆可视化系统 — 把 AI 的大脑变成一张可交互的知识图谱。</p>
  <p align="center"><a href="#-selfmind--认知记忆图谱">中文</a> | <a href="#-selfmind--cognitive-memory-graph">English</a></p>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="#cognitive-memory-system">认知记忆体系</a> ·
  <a href="#iq-system">IQ 系统</a> ·
  <a href="#features">Features</a> ·
  <a href="PRD.md">PRD</a> ·
  <a href="MEMORY_TAXONOMY.md">分类设计</a>
</p>

---

## What is SelfMind?

AI 助手在工作中不断积累记忆 — 用户偏好、项目上下文、行为规则、人际关系、技能库。但这些记忆是不可见的。

**SelfMind 把 AI 的记忆变成可视化的、可交互的知识图谱。**

每条记忆是一个节点，关系是连线，分类是颜色。基于认知心理学的 8 大记忆系统分类，让你看清 AI 大脑的全貌。

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

## Features

- 🧠 **认知记忆体系** — 8 大分类 24 子类，基于认知心理学
- 🧬 **IQ 智商系统** — 参考人类标准的 AI 智商评估，6 维度计算
- 🛠️ **技能图谱** — 95+ 技能四层层级展示（根→分类→子分类→技能）
- 🕸️ **力导向图谱** — D3.js 驱动，物理模拟，层级自然聚集
- 🔍 **搜索与过滤** — 按名称、描述、分类筛选
- 🎯 **分类导航** — 顶部 8 大分类标签，底部指示条高亮
- ⏱️ **时间轴** — 底部全宽时间刻度，按时间回溯记忆
- 🎨 **暗色主题** — 毛玻璃效果，现代极简设计
- 📖 **知识图谱** — LLM Wiki 可视化，支持记忆/知识双视图切换
- 💾 **持久化缓存** — 解析一次，即时加载

## Wiki Knowledge Graph

SelfMind 支持双视图切换：**记忆图谱** 和 **知识图谱**。

知识图谱基于 [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)（Karpathy 提出的持久知识库模式），将 markdown 知识库可视化为交互式图谱。

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

### Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `HERMES_HOME` | `~/.hermes` | Hermes profile home directory |
| `SELFMIND_SOURCE_MODE` | `auto` | `auto` reads all profiles, `single` reads one |
| `SELFMIND_PROFILE` | `hermes` | Active profile name |

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
│ USER.md      │          │  - 8大分类解析    │       │  D3.js 图谱  │
│ Skills/*.md  │          │  - 技能层级构建   │       │  IQ 仪表盘   │
│ Wiki/*.md    │          │  - IQ 算法计算    │       │  双视图切换  │
└──────────────┘          │  - Wiki 图谱构建  │       └──────────────┘
                          │ http_handler.py   │
                          │ wiki_parser.py    │
                          │ server.py (entry) │
                          └──────────────────┘
```

1. **解析记忆** — 读取 MEMORY.md / USER.md，按 `§` 分段，识别 `[分类/子分类]` 标签
2. **扫描技能** — 遍历 `~/.hermes/skills/` 目录，解析 SKILL.md 的 YAML frontmatter
3. **构建图谱** — 生成节点和连线，记忆 + 技能四层层级结构
4. **计算 IQ** — 6 维度加权评估，映射到人类 IQ 标准
5. **解析 Wiki** — 扫描 Wiki 目录，解析 frontmatter + `[[wikilinks]]`，构建知识图谱
6. **渲染展示** — D3.js 力导向图，双视图切换，分类着色，交互式探索

### Backend Structure

```text
selfmind_app/
├── config.py        # 配置加载、Profile 管理
├── parser.py        # 记忆解析 + 技能扫描 + 图谱构建 + IQ 计算
├── wiki_parser.py   # Wiki 知识库解析 + 知识图谱构建
├── memory_store.py  # 记忆存储管理（CRUD + 同步）
├── document_importer.py  # 文档导入 + LLM 记忆提取
└── http_handler.py  # API 端点、刷新/保存处理
server.py            # 服务入口（默认 3002 端口）
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

## Roadmap

- [x] 知识图谱视图（LLM Wiki 可视化）
- [x] 记忆/知识双视图切换
- [x] 记忆管理面板（导入/审批/同步）
- [x] 文档智能导入（LLM 记忆提取）
- [ ] 直接在图谱上编辑记忆（写回 .md 文件）
- [ ] 明暗主题切换
- [ ] 跨 session 保存节点位置
- [ ] 记忆健康度分析（冗余与冲突检测）
- [ ] 导出为图片 / PDF
- [ ] 支持更多 Agent 框架（LangChain, AutoGen 等）
- [ ] 插件系统（自定义记忆源）
- [ ] 多 Agent 记忆对比

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

**SelfMind makes AI memory visible and interactive as a knowledge graph.**

Each memory is a node, relationships are links, categories are colors. Based on 8 cognitive memory systems from psychology, giving you a complete picture of the AI's brain.

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
- 🔍 **Search & Filter** — Filter by name, description, or category
- 🎯 **Category Navigation** — Top nav with 8 category tabs, bottom indicator highlight
- ⏱️ **Timeline** — Full-width bottom timeline for temporal memory browsing
- 🎨 **Dark Theme** — Glassmorphism effects, modern minimalist design
- 📖 **Wiki Knowledge Graph** — LLM Wiki visualization with dual-view toggle (Memory / Knowledge)
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
│ USER.md      │          │  - 8-category    │       │  D3.js graph │
│ Skills/*.md  │          │  - skill hierarchy│      │  IQ dashboard│
│ Wiki/*.md    │          │  - IQ algorithm  │       │  dual view   │
└──────────────┘          │  - wiki graph    │       └──────────────┘
                          │ http_handler.py   │
                          │ wiki_parser.py    │
                          │ server.py (entry) │
                          └──────────────────┘
```

## Interactions

| Action | Effect |
|--------|--------|
| **Hover** node | Highlight connected nodes and links |
| **Click** node | Open detail panel, expand skill labels |
| **Drag** node | Move and pin position |
| **Double-click** | Release pinned node |
| **Scroll** | Zoom in/out |
| **Drag canvas** | Pan view |
| **Category tab** | Filter to show that category |
| **IQ ball** | Click to expand IQ details |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE)

---

<p align="center">
  Built with 🧠 by <a href="https://github.com/xchliu">xchliu</a>
</p>
