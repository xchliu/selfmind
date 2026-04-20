# SelfMind — Product Requirements Document

> AI Agent Memory Visualization · v0.2.0

---

## 1. 项目概述

### 1.1 什么是 SelfMind

SelfMind 是一个 **AI Agent 记忆可视化工具**，将 AI 助手的持久化记忆（用户画像、环境知识、行为准则、人物关系等）以交互式知识图谱的形式呈现。

它解决的核心问题是：**AI Agent 的记忆是黑箱的**。用户无法直观地看到 AI 记住了什么、记忆之间有什么关联、哪些记忆是核心的。SelfMind 把这个黑箱打开，变成一张可交互的图。

### 1.2 目标用户

- **AI Agent 开发者** — 调试和理解 Agent 的记忆状态
- **AI Agent 用户** — 查看 AI 记住了什么，管理自己的"数字画像"
- **AI 研究者** — 研究 Agent 记忆的结构化组织方式

### 1.3 设计理念

| 原则 | 说明 |
|------|------|
| **零配置** | 指向记忆文件，启动即用 |
| **轻量级** | 单 HTML 前端 + 模块化 Python 后端，无需构建工具 |
| **可读性优先** | 清晰的浅色主题，信息层次分明 |
| **交互驱动** | 拖拽、筛选、搜索、高亮关联 |

---

## 2. 系统架构

### 2.1 技术栈

```
┌─────────────────────────────────────────────┐
│                  Frontend                    │
│  Single HTML · D3.js (Force Graph)          │
│  Vanilla JS · CSS3 (Backdrop Filter)        │
└──────────────────┬──────────────────────────┘
                   │ HTTP API
┌──────────────────┴──────────────────────────┐
│                  Backend                     │
│  Python stdlib HTTPServer                    │
│  Modular parser + profile config             │
└──────────────────┬──────────────────────────┘
                   │ File I/O
┌──────────────────┴──────────────────────────┐
│              Data Sources                    │
│  Hermes/OpenClaw/Honcho MEMORY.md + USER.md  │
│  data.json (cached graph data)              │
└─────────────────────────────────────────────┘
```

### 2.2 文件结构

```
selfmind/
├── index.html          # 前端单页应用（HTML + CSS + JS 一体）
├── server.py           # 后端入口（启动 HTTP 服务）
├── selfmind_app/
│   ├── config.py       # 配置加载、source profiles、旧配置迁移
│   ├── parser.py       # 记忆解析与图谱构建
│   └── http_handler.py # API 路由处理
├── config.json         # 运行配置
├── data.json           # 图谱数据缓存
├── PRD.md              # 产品需求文档（本文件）
├── README.md           # 项目说明
├── requirements.txt    # Python 依赖
├── LICENSE             # 开源协议
├── CONTRIBUTING.md     # 贡献指南
└── CHANGELOG.md        # 版本日志
```

### 2.3 数据流

```
1. 启动: server.py 载入配置并初始化 HTTP 服务
2. 解析: 按 § 分隔符拆分记忆条目
3. 分析: 通过关键词规则完成分类与关系提取
4. 缓存: 生成 data.json 持久化
5. 渲染: 前端加载 data.json，D3.js 渲染力导向图
6. 交互: 用户可搜索、筛选、拖拽、查看详情
```

---

## 3. 后端设计 (server.py)

### 3.1 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 返回 index.html 前端页面 |
| `GET` | `/api/data` | 返回图谱数据（优先读缓存） |
| `GET` | `/api/config` | 返回当前配置 |
| `POST` | `/api/refresh` | 重新解析记忆文件，更新图谱 |
| `POST` | `/api/save` | 将当前图谱数据保存到 data.json |
| `POST` | `/api/config` | 保存配置 |

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

## 4. 前端设计 (index.html)

### 4.1 整体布局

```
┌──────────────────────────────────────────────────┐
│ [Logo] SelfMind · Memory Graph    [🔄] [💾] [📊] │  ← 顶部栏
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

### 4.2 视觉规范

#### 4.2.1 配色方案（浅色主题）

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

#### 4.2.2 毛玻璃效果

所有浮动面板统一使用 `backdrop-filter: blur()` 毛玻璃效果：

```css
background: rgba(255, 255, 255, 0.85~0.95);
backdrop-filter: blur(15~25px);
border: 1px solid rgba(0, 0, 0, 0.08~0.1);
border-radius: 10~14px;
box-shadow: 0 2px 8~20px rgba(0, 0, 0, 0.06~0.08);
```

#### 4.2.3 字体

```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
```

### 4.3 组件详细设计

#### 4.3.1 顶部栏 (Top Bar)

- **位置**：固定顶部，`z-index: 100`
- **高度**：56px
- **背景**：白色毛玻璃 `rgba(255,255,255,0.95)` → `rgba(255,255,255,0.85)`
- **下边框**：`rgba(0, 0, 0, 0.08)`
- **左侧**：
  - Logo 文字 `🧠 SelfMind` — 渐变色 `#333 → #1e90ff`
  - 副标题 `Memory Graph` — `#999`，13px
- **右侧按钮组**：
  - 🔄 刷新（重新解析记忆文件）— hover 绿色发光
  - 💾 保存（持久化当前图谱）— hover 蓝色发光
  - 🔍 搜索框（点击展开）

#### 4.3.2 搜索框 (Search Box)

- **默认状态**：收起，仅显示搜索图标
- **展开状态**：`width: 200px`，输入框获得焦点
- **背景**：`rgba(0, 0, 0, 0.03)`
- **边框**：`rgba(0, 0, 0, 0.1)`
- **功能**：实时过滤节点（匹配名称 / 描述）

#### 4.3.3 筛选栏 (Filter Bar)

- **位置**：顶部栏下方，水平居中
- **背景**：白色毛玻璃 + 阴影
- **标签**：圆角药丸形 chip
  - 默认：浅色底 + 灰色文字
  - 选中：对应分类色背景 + 白色文字 + 微弱发光
  - 悬停：加深背景
- **首项**：「全部」显示所有节点
- **动态生成**：根据当前数据中的分类自动生成

#### 4.3.4 力导向图 (Force Graph)

基于 D3.js v7 `forceSimulation`：

**力模型参数**：
| 力 | 参数 | 值 |
|----|------|-----|
| `forceLink` | distance | `120` |
| `forceManyBody` | strength | `-300` |
| `forceCenter` | — | 画布中心 |
| `forceCollide` | radius | `35` |

**节点**：
| 属性 | 规则 |
|------|------|
| 半径 | identity 节点 22，其他节点 14 |
| 颜色 | 按分类映射 |
| 描边 | 白色 2px |
| 发光 | 按分类应用 `glow` SVG filter |
| 标签 | 节点下方 12px，深灰色 `#444`，白色文字阴影 |

**交互**：
| 操作 | 效果 |
|------|------|
| 悬停节点 | 高亮该节点 + 所有直连节点和连线，其余淡化 |
| 点击节点 | 打开详情面板 |
| 拖拽节点 | 移动节点位置 |
| 鼠标滚轮 | 缩放画布 |
| 拖拽空白区 | 平移画布 |

#### 4.3.5 统计面板 (Stats Panel)

- **位置**：右下角，可切换显隐
- **内容**：
  - 📊 总节点数
  - 🔗 总连线数
  - 📂 各分类节点统计
- **分隔线**：`rgba(0, 0, 0, 0.08)`

#### 4.3.6 详情面板 (Detail Panel)

- **位置**：左下角
- **触发**：点击任意节点
- **关闭**：点击面板外区域
- **内容**：
  - 🏷️ 节点名称（大字 · `#222`）
  - 📂 分类标签（药丸形 · 对应分类色）
  - 📝 描述文本（`#666` · 1.6 行高）
  - 🔗 关联节点数量（`#888`）

#### 4.3.7 Toast 通知

三种类型统一规范：

| 类型 | 边框色 | 文字色 | 用途 |
|------|--------|--------|------|
| ✅ success | `rgba(46,213,115,0.25)` | `#1aad50` | 保存成功 |
| ❌ error | `rgba(255,71,87,0.25)` | `#e63946` | 操作失败 |
| ℹ️ info | `rgba(30,144,255,0.25)` | `#1a7de0` | 提示信息 |

- 出现位置：顶部居中
- 动画：从上滑入 → 3 秒后淡出

### 4.4 快捷键

| 按键 | 功能 |
|------|------|
| `Cmd/Ctrl + F` | 聚焦搜索框 |
| `Escape` | 关闭详情面板 |

### 4.5 响应式设计

- 画布自动铺满 `window.innerWidth × window.innerHeight`
- 窗口 resize 时重新计算力模拟中心点
- 面板使用 `position: fixed` + 边距定位

---

## 5. 数据模型 (data.json)

### 5.1 Schema

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

### 5.2 分类色映射

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

### 6.1 本地运行

```bash
pip install -r requirements.txt
python server.py
# 浏览器打开 http://localhost:3002
```

### 6.2 环境要求

- Python 3.8+
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

### v0.1 — MVP（当前版本）
- [x] 后端解析 Hermes/OpenClaw/Honcho 记忆文件
- [x] 关键词规则分类和关系提取
- [x] D3.js 力导向图可视化
- [x] 节点筛选、搜索、详情查看
- [x] 图谱数据缓存和持久化
- [x] 浅色主题

### v0.2 — 增强交互
- [ ] 节点右键菜单（编辑 / 删除 / 新建关联）
- [ ] 记忆条目的增删改（回写到 .md 文件）
- [ ] 多主题切换（浅色 / 深色）
- [ ] 图谱布局保存（记住节点位置）

### v0.3 — 扩展能力
- [ ] 支持更多 Agent 框架的记忆格式
- [ ] 时间线视图（按记忆创建时间排列）
- [ ] 记忆健康度分析（冗余检测、冲突检测）
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
| 安全 | 仅本地运行，不暴露公网 |
| 可扩展 | 记忆源可替换，前端可定制主题 |
