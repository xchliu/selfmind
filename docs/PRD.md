# SelfMind — Product Requirements Document

 > AI Agent DNA Sequencer · v0.3.0

---

## 1. 项目概述

### 1.1 什么是 SelfMind

SelfMind 是一个 **Agent DNA 测序仪**——将 AI Agent 的持久化记忆（用户画像、环境知识、行为准则、人物关系等）解码为结构化的「DNA 双螺旋」，让每个 Agent 的身份、能力和关系链如同基因序列般可读、可比、可追溯。

它解决的核心问题是：**AI Agent 的记忆是黑箱的**。用户无法直观地看到 Agent 记住了什么、记忆之间有什么关联、哪些记忆是核心的、Agent 之间有什么基因差异。SelfMind 把这个黑箱打开，把记忆从「文本碎片」升级为「DNA 序列」——一张可逐级展开、可交互的基因图谱。

### 1.2 目标用户

- **AI Agent 开发者** — 调试和理解 Agent 的记忆状态
- **AI Agent 用户** — 查看 AI 记住了什么，管理自己的"数字画像"
- **AI 研究者** — 研究 Agent 记忆的结构化组织方式

### 1.3 设计理念

| 原则 | 说明 |
|------|------|
| **零配置** | Docker Compose 一键启动，热挂载记忆文件 |
| **轻量级** | 模块化前端（9个静态文件）+ 模块化 Python 后端，无需构建工具 |
| **可读性优先** | 清晰的浅色主题，信息层次分明 |
| **交互驱动** | 逐级展开、拖拽、筛选、搜索、高亮关联 |
| **DNA隐喻** | 记忆不是碎片，而是可测序、可解码的 Agent 基因序列 |

---

## 2. 系统架构

### 2.1 技术栈

```
┌─────────────────────────────────────────────┐
│              Docker Compose                  │
│  ┌─────────────────────────────────────────┐│
│  │            Frontend Container            ││
│  │  模块化 HTML+CSS+JS（9个静态文件）       ││
│  │  D3.js (Force Graph) · 6个视图模块       ││
│  │  Agent DNA 双螺旋可视化                  ││
│  └──────────────────┬──────────────────────┘│
│                     │ HTTP API (JSON)        │
│  ┌──────────────────┴──────────────────────┐│
│  │            Backend Container             ││
│  │  Python stdlib HTTPServer                ││
│  │  4个 Handler Mixin + wiki_parser         ││
│  └──────────────────┬──────────────────────┘│
│                     │ Unified Data Pipeline  │
│  ┌──────────────────┴──────────────────────┐│
│  │            Data Layer                    ││
│  │  SQLite (unified_store) ← 统一数据源     ││
│  │  unified_sync: 采集 memory/user/skill    ││
│  │  → SQLite（legacy模块已移除）            ││
│  │  data.json (图谱缓存，从SQLite派生)      ││
│  └─────────────────────────────────────────┘│
│  volumes: 热挂载记忆目录 / 环境变量注入      │
└─────────────────────────────────────────────┘
```

### 2.2 文件结构

```
selfmind/
├── index.html          # 前端 shell（引用外部 CSS/JS）
├── server.py           # 后端入口（启动 HTTP 服务）
├── config.json         # 运行配置
├── Dockerfile          # 后端容器镜像定义
├── docker-compose.yml  # Docker Compose 编排（前端+后端+热挂载）
├── .env.example        # 环境变量示例
├── data/
│   ├── data.json       # 图谱数据缓存（从 SQLite 派生）
│   └── selfmind.db     # 统一 SQLite 数据源
├── docs/               # 文档目录（PRD、README 等）
├── selfmind_app/       # 后端模块
│   ├── config.py       # 配置加载与 source profiles
│   ├── parser.py       # 记忆解析与分类逻辑
│   ├── wiki_parser.py  # Wiki 页面解析
│   ├── http_handler.py # API 路由核心
│   ├── unified_store.py # 统一 SQLite 存储层
│   ├── unified_sync.py  # 统一采集入口（memory/user/skill → SQLite）
│   ├── handlers/       # 4个 Handler Mixin
│   │   ├── stats_mixin.py
│   │   ├── mutations_mixin.py
│   │   ├── engines_mixin.py
│   │   └── v1_mixin.py
│   └── providers/      # 数据源适配器
│       ├── base.py
│       ├── file_adapter.py
│       ├── skills_provider.py
│       └── aggregation.py
├── static/             # 前端静态资源
│   ├── css/            # global.css, graph.css, health.css, wiki.css, sediment.css, dna.css
│   └── js/             # app.js, graph.js, views.js, wiki.js, sediment.js, dna.js, init.js
├── assets/
│   └── logo.png
├── requirements.txt    # Python 依赖
└── LICENSE             # 开源协议
```

### 2.3 数据流

```
1. 启动: docker-compose up → Backend 容器初始化 UnifiedStore → unified_sync 采集数据
   (memory/user/skill → Providers → SQLite，legacy 模块已移除)
2. 请求: HTTP API → http_handler 路由 → Handler Mixin 处理 → 从 SQLite 读取 → 返回 JSON
3. 图谱: build_graph 从 SQLite 读取 entries → 构建层级结构 → 写入 data.json
4. Wiki: wiki_parser 解析 Wiki 页面 → 存入 SQLite → API 查询返回
5. 前端: 浏览器加载 index.html → 按需加载 CSS/JS 模块 → API 获取数据 → 渲染视图
6. 视图: 记忆图谱 / Wiki库 / 记忆健康 / AI分析 / 记忆沉淀 / Agent DNA — 6个独立视图模块
7. 交互: 逐级展开图谱、搜索、筛选、拖拽、查看详情、Wiki编辑、沉淀操作、DNA 测览
```

---

## 3. 后端设计 (selfmind_app)

### 3.1 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 返回 index.html 前端页面 |
| `GET` | `/static/*` | 返回前端静态资源（CSS/JS） |
| `GET` | `/api/stats` | 返回6层记忆实时指标数据 |
| `GET` | `/api/poll` | 轻量 mtime 变化检测 + Honcho 健康检查 |
| `GET` | `/api/memories` | 返回记忆条目列表 |
| `GET` | `/api/wiki/pages` | 返回 Wiki 页面列表 |
| `GET` | `/api/wiki/page` | 返回指定 Wiki 页面内容（?name=xxx） |
| `PUT` | `/api/wiki/page` | 更新指定 Wiki 页面内容 |
| `GET` | `/api/meta/health` | 记忆健康度分析数据 |
| `GET` | `/api/meta/entries` | 返回元数据条目列表 |
| `GET` | `/api/meta/evolution` | 记忆演变时间线数据 |
| `POST` | `/api/consolidate` | 记忆沉淀操作 |
| `POST` | `/api/forget` | 记忆遗忘操作 |
| `POST` | `/api/analyze` | AI 分析请求 |
| `POST` | `/api/meta/sync` | 触发数据同步（重新采集到 SQLite） |

### 3.2 记忆文件格式

支持 source profile 方式配置记忆目录，默认包含 Hermes、OpenClaw 与 Honcho：

- Hermes: `~/.hermes/memories/`
- OpenClaw: `~/.openclaw/memories/`
- Honcho: `~/.honcho/memories/`

**MEMORY.md** — Agent 的个人笔记：
```markdown
记忆条目1的内容
§
记忆条目2的内容
§
记忆条目3的内容
```

**USER.md** — 用户画像：
```markdown
**Name:** 用户名
§
**Timezone:** Asia/Shanghai
§
其他用户信息
```

- 分隔符：`§`（独占一行）
- 每个 `§` 之间的文本块是一条独立记忆

### 3.3 规则解析

后端通过关键词匹配进行分类与关系推断，图谱数据结构如下：

```json
{
  "nodes": [
    {
      "id": "unique_id",
      "label": "显示名称",
      "category": "分类",
      "description": "详细描述"
    }
  ],
  "links": [
    {
      "source": "node_id_1",
      "target": "node_id_2",
      "label": "关系描述"
    }
  ]
}
```

### 3.4 节点分类体系

| 分类 | 英文标识 | 说明 | 示例 |
|------|----------|------|------|
| 核心身份 | `core_identity` | Agent 自身的身份定义 | Agent 名称、角色 |
| 人物关系 | `relationship` | 与用户/他人的关系 | 用户名、团队成员 |
| 项目/任务 | `project` | 正在进行或关注的项目 | 产品开发、调研任务 |
| 行为准则 | `behavioral` | 行为规范和红线 | 安全红线、沟通风格 |
| 能力/工具 | `capability` | 掌握的工具和技能 | 日历管理、代码能力 |
| 环境配置 | `environment` | 运行环境信息 | 时区、系统配置 |

### 3.5 配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `HERMES_HOME` | `~/.hermes` | Hermes profile 根目录 |
| `OPENCLAW_HOME` | `~/.openclaw` | OpenClaw profile 根目录 |
| `HONCHO_HOME` | `~/.honcho` | Honcho profile 根目录 |
| `SELFMIND_SOURCE_MODE` | `auto` | `auto` 读取全部 profiles，`single` 只读一个 |
| `SELFMIND_PROFILE` | `hermes` | `single` 模式下激活的 profile 名称 |

---

## 4. 前端设计 (模块化 SPA)

### 4.1 整体布局与视图

6个前端视图模块：

| 视图 | JS模块 | CSS模块 | 说明 |
|------|---------|---------|------|
| 记忆图谱 | graph.js | graph.css | D3.js 力导向图（逐级展开） |
| Wiki库 | wiki.js | wiki.css | Wiki 页面浏览与编辑（卡片预览+表格渲染） |
| 记忆健康 | views.js | health.css | 健康度分析仪表盘 |
| AI分析 | views.js | — | AI 分析结果展示 |
| 记忆沉淀 | sediment.js | sediment.css | 沉淀操作界面 |
| Agent DNA | dna.js | dna.css | DNA 双螺旋可视化 |

全局样式：global.css，初始化入口：init.js，主控制器：app.js

### 4.2 整体布局

```
┌──────────────────────────────────────────────────┐
│ [Logo] SelfMind · Agent DNA Sequencer  [🔄] [💾] [📊] │  ← 顶部栏
├──────────────────────────────────────────────────┤
│  [全部] [核心身份] [人物关系] [项目] [行为] ...    │  ← 筛选栏
├──────────────────────────────────────────────────┤
│                                                  │
│              ◉─────◉                             │
│             / \   / \         ┌───────────┐     │
│            ◉   ◉─◉  ◉        │ 统计面板   │     │  ← 图谱区域
│             \ /   \           │ 16 nodes  │     │
│              ◉─────◉         │ 20 links  │     │
│                               └───────────┘     │
│                                                  │
│  ┌──────────────────┐                            │
│  │ 节点详情面板      │                            │  ← 点击节点显示
│  │ 名称 / 分类      │                            │
│  │ 描述 / 连接      │                            │
│  └──────────────────┘                            │
└──────────────────────────────────────────────────┘
```

### 4.3 视觉规范

#### 4.3.1 配色方案（浅色主题）

**基础色**：
| 元素 | 色值 | 用途 |
|------|------|------|
| 页面背景 | `#f5f7fa` | 主背景 |
| 网格线 | `rgba(30, 144, 255, 0.08)` | 背景网格装饰 |
| 主文字 | `#333` | 正文内容 |
| 次文字 | `#888` / `#999` | 标签、说明 |
| 边框 | `rgba(0, 0, 0, 0.08~0.12)` | 面板/按钮边框 |
| 面板背景 | `rgba(255, 255, 255, 0.85~0.95)` | 毛玻璃面板 |

**节点分类色**（HSL 高饱和）：
| 分类 | 色值 | Hex |
|------|------|-----|
| 核心身份 | — | `#ff6b6b` |
| 人物关系 | — | `#ffa502` |
| 项目/任务 | — | `#2ed573` |
| 行为准则 | — | `#1e90ff` |
| 能力/工具 | — | `#a55eea` |
| 环境配置 | — | `#778ca3` |

**连线**：
| 状态 | 样式 |
|------|------|
| 默认 | `rgba(0, 0, 0, 0.12)` · 1.2px |
| 高亮 | 继承源节点颜色 · 2.5px |
| 淡化 | `opacity: 0.05` |

**连线标签**：
| 状态 | 样式 |
|------|------|
| 默认 | `rgba(0, 0, 0, 0.35)` · 9px |
| 高亮 | `rgba(0, 0, 0, 0.8)` · 10px · bold |

#### 4.3.2 毛玻璃效果

所有浮动面板统一使用 `backdrop-filter: blur()` 毛玻璃效果：

```css
background: rgba(255, 255, 255, 0.85~0.95);
backdrop-filter: blur(15~25px);
border: 1px solid rgba(0, 0, 0, 0.08~0.1);
border-radius: 10~14px;
box-shadow: 0 2px 8~20px rgba(0, 0, 0, 0.06~0.08);
```

#### 4.3.3 字体

```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
```

### 4.4 组件详细设计

#### 4.4.1 顶部栏 (Top Bar)

- **位置**：固定顶部，`z-index: 100`
- **高度**：56px
- **背景**：白色毛玻璃 `rgba(255,255,255,0.95)` → `rgba(255,255,255,0.85)`
- **下边框**：`rgba(0, 0, 0, 0.08)`
- **左侧**：
  - Logo 文字 `🧠 SelfMind` — 渐变色 `#333 → #1e90ff`
  - 副标题 `Agent DNA Sequencer` — `#999`，13px
- **右侧按钮组**：
  - 🔄 刷新（重新解析记忆文件）— hover 绿色发光
  - 💾 保存（持久化当前图谱）— hover 蓝色发光
  - 🔍 搜索框（点击展开）

#### 4.4.2 搜索框 (Search Box)

- **默认状态**：收起，仅显示搜索图标
- **展开状态**：`width: 200px`，输入框获得焦点
- **背景**：`rgba(0, 0, 0, 0.03)`
- **边框**：`rgba(0, 0, 0, 0.1)`
- **功能**：实时过滤节点（匹配名称 / 描述）

#### 4.4.3 筛选栏 (Filter Bar)

- **位置**：顶部栏下方，水平居中
- **背景**：白色毛玻璃 + 阴影
- **标签**：圆角药丸形 chip
  - 默认：浅色底 + 灰色文字
  - 选中：对应分类色背景 + 白色文字 + 微弱发光
  - 悬停：加深背景
- **首项**：「全部」显示所有节点
- **动态生成**：根据当前数据中的分类自动生成

#### 4.4.4 力导向图 (Force Graph)

基于 D3.js v7 `forceSimulation`：

**力模型参数**：
| 力 | 参数 | 值 |
|----|------|-----|
| `forceLink` | distance | `150` |
| `forceManyBody` | strength | `-300 ~ -1200`（按层级） |
| `forceCenter` | — | 画布中心 |
| `forceCollide` | radius | `35 ~ 60`（按层级） |

**时间线焦点模式**：
| 行为 | 说明 |
|------|------|
| 播放自动对焦 | 镜头 zoom 平移到新增节点区域，1.2秒丝滑过渡 |
| 变化节点标记 | ✦ 标识（20px/900粗）+ 绿色脉冲光环 + 光晕填充 |
| 变化连线高亮 | 荧光绿 `#00ffaa`、3.5px粗；非变化连线淡化到20% |
| 无变化帧 | 镜头回到全局视角（0.85x） |
| 播放结束 | 镜头自动复位到全局视角 |
| 增量 simulation | 不重建 force simulation，alpha=0.15~0.25 增量更新 |

**节点**：
| 属性 | 规则 |
|------|------|
| 半径 | identity 节点 22，其他节点 14 |
| 颜色 | 按分类映射 |
| 描边 | 白色 2px |
| 发光 | 按分类应用 `glow` SVG filter |
| 标签 | 节点下方 12px，深灰色 `#444`，白色文字阴影 |

**逐级展开交互**：
| 操作 | 效果 |
|------|------|
| 点击分类节点 | 展开该分类下的子节点，从收缩态变为展开态 |
| 再次点击 | 收缩子节点，恢复为单一分类节点 |
| 双击叶节点 | 进入该节点详情面板 |
| 展开动画 | 子节点从中心向外扩散，0.8秒贝塞尔曲线过渡 |
| 收缩动画 | 子节点收回中心点，0.5秒过渡 |

默认状态下，6个分类节点以聚合态显示（每个分类仅一个节点）；点击后逐级展开为具体记忆节点，支持多级嵌套。

**交互**：
| 操作 | 效果 |
|------|------|
| 悬停节点 | 高亮该节点 + 所有直连节点和连线，其余淡化 |
| 点击节点 | 打开详情面板（聚合节点则展开子节点） |
| 拖拽节点 | 移动节点位置 |
| 鼠标滚轮 | 缩放画布 |
| 拖拽空白区 | 平移画布 |

#### 4.4.5 统计面板 (Stats Panel)

- **位置**：右下角，可切换显隐
- **内容**：
  - 📊 总节点数
  - 🔗 总连线数
  - 📂 各分类节点统计
- **分隔线**：`rgba(0, 0, 0, 0.08)`

#### 4.4.6 详情面板 (Detail Panel)

- **位置**：左下角
- **触发**：点击任意节点
- **关闭**：点击面板外区域
- **内容**：
  - 🏷️ 节点名称（大字 · `#222`）
  - 📂 分类标签（药丸形 · 对应分类色）
  - 📝 描述文本（`#666` · 1.6 行高）
  - 🔗 关联节点数量（`#888`）

#### 4.4.7 Agent DNA 视图 (DNA View)

Agent DNA 页面以「双螺旋」隐喻呈现 Agent 的记忆基因序列：

**布局**：
```
┌──────────────────────────────────────────────────┐
│  🧬 Agent DNA Sequencer                           │
│                                                   │
│  ┌─ 核心身份 ─┐    ┌─ 环境配置 ─┐               │
│  │ 🔴 Agent名 │    │ 🔵 时区    │               │
│  │ 🔴 角色    │    │ 🔵 系统    │               │
│  └─╱══════╲─┘    └─╱══════╲─┘               │
│   ║ 双螺旋 ║      ║ 双螺旋 ║                  │  ← 两条螺旋线连接成对
│  └─╲══════╱─┘    └─╲══════╱─┘               │
│  │ 🟠 用户A  │    │ 🟣 工具1   │               │
│  │ 🟠 用户B  │    │ 🟣 工具2   │               │
│  └─ 人物关系 ─┘    └─ 能力/工具 ─┘               │
│                                                   │
│  ┌─ 侧栏：DNA 指标 ─────────────────┐           │
│  │ 记忆总量: 42    基因长度: 128      │           │
│  │ 分类占比饼图                        │           │
│  │ Agent 基因突变率（新增/变更记忆）    │           │
│  └────────────────────────────────────┘           │
└──────────────────────────────────────────────────┘
```

**双螺旋可视化规则**：
| 元素 | 规则 |
|------|------|
| 螺旋结构 | 左侧螺旋=身份类节点（core_identity + relationship），右侧螺旋=能力类节点（capability + behavioral + environment） |
| 碱基对 | 每对节点用横线连接（如「Agent名」—「工具1」），形成 DNA 碱基对视觉 |
| 螺旋线 | 用 SVG path 绘制 S 形曲线，颜色随分类渐变 |
| 节点尺寸 | 加大节点圆（r=20~30），支持 hover 展开 mini 详情 |
| 展开/收缩 | 点击碱基对可展开该分类的完整子树，收缩后回到碱基对 |
| 旋转动画 | 首次加载时螺旋线缓慢旋转入场，0.6s |

**DNA 指标面板**：
- 记忆总量（节点数）
- 基因长度（描述文本平均字数 × 节点数）
- 分类占比（6色饼图）
- 基因突变率（最近一周新增/变更记忆占比）

#### 4.4.8 Wiki 卡片优化

Wiki 库视图的卡片预览和表格渲染增强：

**卡片预览加大**：
| 属性 | 旧值 | 新值 |
|------|------|------|
| 卡片宽度 | 280px | 380px |
| 卡片高度 | 200px | 280px |
| 预览文字行数 | 3行 | 6行 |
| 卡片间距 | 16px | 20px |
| 卡片圆角 | 8px | 12px |
| 卡片阴影 | `0 2px 8px` | `0 4px 16px rgba(0,0,0,0.08)` |

**表格渲染**：
- Wiki 页面内容中的 Markdown 表格（`|...|...|`）自动渲染为 HTML `<table>`
- 表格样式：浅灰边框 + 分类色表头背景 + 斑马纹行
- 支持表格内超链接和加粗
- 超宽表格自动水平滚动（`overflow-x: auto`）

#### 4.4.9 Toast 通知

三种类型统一规范：

| 类型 | 边框色 | 文字色 | 用途 |
|------|--------|--------|------|
| ✅ success | `rgba(46,213,115,0.25)` | `#1aad50` | 保存成功 |
| ❌ error | `rgba(255,71,87,0.25)` | `#e63946` | 操作失败 |
| ℹ️ info | `rgba(30,144,255,0.25)` | `#1a7de0` | 提示信息 |

- 出现位置：顶部居中
- 动画：从上滑入 → 3 秒后淡出

### 4.5 快捷键

| 按键 | 功能 |
|------|------|
| `Cmd/Ctrl + F` | 聚焦搜索框 |
| `Escape` | 关闭详情面板 |

### 4.6 响应式设计

- 画布自动铺满 `window.innerWidth × window.innerHeight`
- 窗口 resize 时重新计算力模拟中心点
- 面板使用 `position: fixed` + 边距定位

---

## 5. 数据模型

### 5.1 数据层架构

```
┌──────────────────────────────────────┐
│        unified_store (SQLite)         │  ← 统一数据源
│  entries | wiki_pages | metadata | … │
└──────────────┬───────────────────────┘
               │ build_graph() 派生
┌──────────────┴───────────────────────┐
│           data.json                   │  ← 图谱缓存
│  nodes[] + links[]                    │
└──────────────────────────────────────┘
```

### 5.2 GraphData Schema

```typescript
interface GraphData {
  nodes: Node[];
  links: Link[];
}

interface Node {
  id: string;           // 唯一标识（由内容哈希稳定生成）
  label: string;        // 显示名称
  category: string;     // 分类标识（映射到颜色）
  description: string;  // 详细描述
}

interface Link {
  source: string;       // 源节点 ID
  target: string;       // 目标节点 ID
  label: string;        // 关系描述
}
```

### 5.3 分类色映射

```javascript
const categoryColors = {
  "核心身份": "#ff6b6b",
  "人物关系": "#ffa502",
  "项目/任务": "#2ed573",
  "行为准则": "#1e90ff",
  "能力/工具": "#a55eea",
  "环境配置": "#778ca3",
  // 未知分类自动分配 #95a5a6
};
```

---

## 6. 部署

### 6.1 Docker Compose 部署（推荐）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，设置 HERMES_HOME / OPENCLAW_HOME / HONCHO_HOME 等路径

# 2. 一键启动
docker-compose up -d
# 浏览器打开 http://localhost:3002

# 3. 热挂载记忆文件（volumes 映射）
# docker-compose.yml 中配置：
#   volumes:
#     - ${HERMES_HOME}/memories:/data/hermes/memories:ro
#     - ${OPENCLAW_HOME}/memories:/data/openclaw/memories:ro
#     - ${HONCHO_HOME}/memories:/data/honcho/memories:ro
# 记忆文件变更后，点击前端 🔄 刷新按钮即可同步

# 4. 环境变量注入
# 所有 SELFMIND_* 和 *_HOME 环境变量通过 .env 文件注入容器
# Docker Compose 自动读取 .env 文件
```

**docker-compose.yml 核心结构**：
```yaml
services:
  backend:
    build: .
    ports: ["3002:3002"]
    volumes:
      - ${HERMES_HOME}/memories:/data/hermes/memories:ro
      - ${OPENCLAW_HOME}/memories:/data/openclaw/memories:ro
      - ${HONCHO_HOME}/memories:/data/honcho/memories:ro
      - selfmind_data:/app/data
    env_file: .env
  frontend:
    image: nginx:alpine
    ports: ["80:80"]
    volumes:
      - ./static:/usr/share/nginx/html/static:ro
      - ./index.html:/usr/share/nginx/html/index.html:ro
volumes:
  selfmind_data:
```

### 6.2 本地运行（无 Docker）

```bash
pip install -r requirements.txt
python server.py
# 启动时自动初始化 SQLite 并通过 unified_sync 同步数据
# 浏览器打开 http://localhost:3002
```

### 6.3 环境要求

- Python 3.8+（本地运行）或 Docker + Docker Compose（推荐）
- 现代浏览器（支持 `backdrop-filter`）

### 6.3 记忆文件接入

默认读取 Hermes Agent 的记忆文件：
```
~/.hermes/memories/MEMORY.md
~/.hermes/memories/USER.md
```

OpenClaw 默认目录：
```
~/.openclaw/memories/MEMORY.md
~/.openclaw/memories/USER.md
```

Honcho 默认目录：
```
~/.honcho/memories/MEMORY.md
~/.honcho/memories/USER.md
```

可在 `config.json` 的 `source.profiles` 中扩展更多目录与文件名。

---

## 7. 路线图

### v0.1 — MVP
- [x] 后端解析 Hermes/OpenClaw/Honcho 记忆文件
- [x] 关键词规则分类和关系提取
- [x] D3.js 力导向图可视化
- [x] 节点筛选、搜索、详情查看
- [x] 图谱数据缓存和持久化
- [x] 浅色主题

### v0.2 — 增强交互
- [x] 模块化前端架构（9个静态文件，5个视图）
- [x] 统一 SQLite 数据层（unified_store + unified_sync）
- [x] Wiki 库视图（浏览、编辑 Wiki 页面）
- [x] 记忆健康度视图（6层指标分析）
- [x] 记忆沉淀视图（consolidate/forget 操作）
- [x] Handler Mixin 模块化后端（stats/mutations/engines/v1）
- [x] 新增 API：wiki, stats, poll, evolution, consolidate, forget

### v0.3 — Agent DNA + 统一管道（当前版本）
- [x] 统一数据管道（unified_store + unified_sync 取代 legacy metadata_db/memory_store）
- [x] Docker Compose 部署（热挂载记忆文件 + 环境变量注入）
- [x] 图谱逐级展开交互（聚合态 → 展开态，点击分类节点展开子节点）
- [x] Agent DNA 双螺旋可视化视图（dna.js + dna.css）
- [x] Wiki 卡片预览加大（380×280px）+ Markdown 表格渲染
- [x] 定位升级：从「记忆可视化工具」到「Agent DNA 测序仪」
- [ ] 节点右键菜单（编辑 / 删除 / 新建关联）
- [ ] 记忆条目的增删改（回写到 .md 文件）
- [ ] 多主题切换（浅色 / 深色）
- [ ] 图谱布局保存（记住节点位置）

### v0.4 — 扩展能力
- [ ] 支持更多 Agent 框架的记忆格式
- [ ] AI 分析视图增强（深度分析、趋势预测）
- [ ] 记忆演变时间线视图（evolution 数据可视化）
- [ ] 导出为图片 / PDF

### v1.0 — 通用化
- [ ] 插件化记忆源适配器
- [ ] 多用户 / 多 Agent 记忆对比
- [ ] 实时监听记忆文件变更，自动刷新
- [ ] 嵌入式模式（iframe / Web Component）

---

## 8. 非功能需求

| 维度 | 要求 |
|------|------|
| 性能 | 200 节点以内流畅交互（60fps） |
| 启动 | 冷启动 < 3 秒（有缓存时） |
| 依赖 | 最小化：Python 标准库（后端） |
| 兼容 | Chrome / Firefox / Safari / Edge 最新版 |
| 安全 | Docker 容器隔离，仅暴露 localhost 端口；记忆文件只读挂载 |
| 可扩展 | 记忆源可替换，前端可定制主题，Docker Compose 可扩展服务 |
