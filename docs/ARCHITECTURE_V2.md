# SelfMind V2 — AI 记忆基础设施架构方案

> 从"可视化工具"升级为 Agent 的"睡眠系统"

## 一、核心定位

**SelfMind = Agent 的离线记忆管理系统**

| 职责 | Agent（在线/白天） | SelfMind（离线/睡眠） |
|------|-------------------|---------------------|
| 注意力门控 | ✅ 判断该不该记 | |
| 快速编码 | ✅ 即时写入 MEMORY.md | |
| 提取/检索 | ✅ 按需调用 | |
| 即时更新 | ✅ 发现矛盾时修正 | |
| **巩固** | | ❌ NOT implemented（代码存在但未接入运行循环） |
| **遗忘** | | 🔄 PARTIALLY implemented（decay_score计算已实现，遗忘执行未实际运行） |
| **审查** | ✅ 可视化、人工干预 | |
| **关联发现** | ❌ NOT implemented | |

---

## 二、架构总览

```
┌─────────────────────────────────────────────────┐
│                  用户界面层                       │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ 记忆图谱  │  │ 健康仪表盘│  │ 审查/干预面板 │  │
│  │ (现有D3)  │  ✅ 衰减曲线 │  │ (新增)        │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
├─────────────────────────────────────────────────┤
│                  API 层 (REST)                   │
│  /api/decay-trend ✅  /api/recall/scan ✅        │
│  /api/memories ✅    /api/documents/scan ✅      │
├─────────────────────────────────────────────────┤
│                  核心引擎层                       │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ 巩固引擎  │  │ 遗忘引擎  │  │ 分析引擎      │  │
│  │Consolidator│ Forgetter │  │ Analyzer      │  │
│  │ ❌ NOT impl│ 🔄 PARTIAL │  │ ❌ NOT impl   │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
├─────────────────────────────────────────────────┤
│                  数据管道层                       │
│  ┌──────────────────────────────────────────┐   │
│  │ unified_sync.py → unified_store.py       │   │
│  │ （直接编排，NOT through Provider interface）│   │
│  │ Sources: MEMORY.md + Honcho API + Wiki   │   │
│  └──────────────────────────────────────────┘   │
├─────────────────────────────────────────────────┤
│                  数据层 (SQLite)                  │
│  entries / entry_history / snapshots             │
│  operations_log / decay_history / agent_recall_log│
└─────────────────────────────────────────────────┘
```

---

## 三、三大核心引擎（实际实现状态）

### 3.1 巩固引擎 (Consolidator) — ❌ NOT implemented

**代码文件存在**：`consolidator.py` + `engines_mixin.py` 中有 API handler

但实际状态：
- `find_duplicates_from_graph()` — 使用 SequenceMatcher 文本相似度，但未接入运行循环
- `llm_consolidate()` — 依赖外部 LLM API，有代码但未实际触发
- `find_conflicts()` — handler 返回 `"not yet implemented"`
- `run_full_scan()` — 只对 graph data.json 操作，不写入 unified_store
- **结论**：代码框架存在，但没有定时触发机制，没有与 unified_store 的写入闭环，没有实际运行

### 3.2 遗忘引擎 (Forgetter) — 🔄 PARTIALLY implemented

**实际已实现的部分**：
- `compute_decay_scores()` — 在 `unified_store.py` 中，计算每条 entry 的衰减分数
  - 公式：`new_decay = importance × (e^(-λ × days_since_first_seen) × (1 + 0.1 × recall_count))`
  - λ = 0.05（可配置）
  - 记录每次衰减变化到 `decay_history` 表
- `get_decay_history()` — 查询单条 entry 的衰减历史
- `get_overall_decay_trend()` — 查询全局衰减趋势（按天聚合）
- `/api/decay-trend` — 前端衰减曲线可视化 ✅

**未实现的部分**：
- 状态流转（active → fading → archived）未在 unified_store 中实现
- 钉住/保护机制仅在 metadata_db 中存在，unified_store 中有字段但无自动流转逻辑
- `ForgetterEngine` 类存在但操作 data.json 而非 unified_store
- 回滚能力未实现（快照存在但无恢复命令）

### 3.3 分析引擎 (Analyzer) — ❌ NOT implemented

**代码文件存在**：`analyzer.py` + `engines_mixin.py` 中有 API handler

但实际状态：
- `analyze_patterns` handler — 返回 `"not yet implemented"`
- `extract_insights_from_graph()` / `analyze_importance_from_graph()` — 对 data.json 操作
- 没有记忆健康度评分、认知偏差检测、增长趋势分析等核心功能
- **结论**：代码框架存在，核心分析能力未实现

---

## 四、数据层设计（实际 DB Schema）

### 4.1 数据管道架构

**核心原则**：`unified_sync.py` 是唯一的数据入口，直接编排各数据源的同步流程，NOT through Provider interface。

```
unified_sync(store, config)
  ├── 解析 MEMORY.md / USER.md → entries
  ├── 解析 Wiki pages → entries  
  ├── 调 Honcho API → entries (honcho_obs/honcho_conc)
  ├── 解析 Skills → entries
  ├── store.bulk_upsert(entries)  ← 唯一写入路径
  ├── store.compute_decay_scores()
  └── store.create_snapshot()
```

Provider interface (`providers/base.py` → `MemoryProvider`) 存在但未被 unified_sync 使用，属于遗留代码。

### 4.2 SQLite 元数据库 (selfmind.db) — 6 张表

```sql
-- 1. entries: 统一记忆条目表（所有数据源写入此表）
CREATE TABLE entries (
    id TEXT PRIMARY KEY,                       -- deterministic: type:source:sha256[:8]
    content_hash TEXT NOT NULL,                -- SHA256 full for dedup
    content TEXT NOT NULL,                     -- full text
    content_preview TEXT,                      -- first 120 chars for display
    type TEXT NOT NULL DEFAULT 'memory',       -- memory/wiki/honcho_obs/honcho_conc/skill
    source TEXT NOT NULL,                      -- file path or API endpoint
    source_profile TEXT DEFAULT 'hermes',      -- config profile name

    -- Classification
    primary_cat TEXT,                          -- e.g. autobiographical, semantic
    secondary_cat TEXT,                        -- e.g. identity, domain
    label TEXT,                                -- short display label
    tags TEXT DEFAULT '[]',                    -- JSON array of tags

    -- Honcho-specific fields
    observer TEXT,                             -- who observed (e.g. liuxiaocheng)
    observed TEXT,                             -- who was observed (e.g. hermes)
    honcho_level TEXT,                         -- explicit/inductive/deductive/contradiction
    honcho_doc_id TEXT,                        -- Honcho document ID

    -- Lifecycle management (evolution-aware)
    importance REAL DEFAULT 0.5,
    decay_score REAL DEFAULT 0.25,
    emotional_weight REAL,                     -- 情感权重（预留）
    access_count INTEGER DEFAULT 0,
    version INTEGER DEFAULT 1,                 -- incremented on content changes
    first_seen_at TEXT,                        -- when this content first appeared
    last_recalled TEXT,                        -- last time recalled by an agent
    created_at TEXT,                           -- when this DB row was created
    updated_at TEXT,                           -- last field update
    status TEXT DEFAULT 'active',              -- active/inactive/archived
    pinned INTEGER DEFAULT 0
);

-- 2. entry_history: 内容变更版本历史
CREATE TABLE entry_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL,                    -- FK → entries.id
    version INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    content TEXT NOT NULL,
    content_preview TEXT,
    primary_cat TEXT,
    secondary_cat TEXT,
    label TEXT,
    tags TEXT,
    timestamp TEXT NOT NULL,                  -- when this version was recorded
    trigger TEXT DEFAULT 'sync',              -- sync/manual/edit
    FOREIGN KEY (entry_id) REFERENCES entries(id)
);

-- 3. snapshots: 源文件完整内容快照
CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    memory_md TEXT,                            -- full MEMORY.md content
    user_md TEXT,                              -- full USER.md content
    trigger TEXT DEFAULT 'sync',               -- sync/manual/startup
    stats TEXT                                 -- JSON: {added, updated, inactive, total}
);

-- 4. operations_log: 所有变更操作审计日志
CREATE TABLE operations_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    operation TEXT NOT NULL,                   -- add/update/inactivate/archive/pin/unpin/version_change
    target_ids TEXT,                           -- JSON array of entry IDs
    detail TEXT,                               -- JSON: {before, after, reason}
    auto_or_manual TEXT DEFAULT 'auto'
);

-- 5. decay_history: 衰减分数变化历史（支持曲线可视化）
CREATE TABLE decay_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    decay_score REAL NOT NULL,
    trigger TEXT DEFAULT 'auto',
    FOREIGN KEY (entry_id) REFERENCES entries(id)
);

-- 6. agent_recall_log: Agent 回访记录（recall capture）
CREATE TABLE agent_recall_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL,                    -- FK → entries.id
    agent_id TEXT NOT NULL,                    -- which agent (hermes, aris, etc.)
    timestamp TEXT NOT NULL,
    source TEXT DEFAULT 'session_log',         -- how we detected it
    confidence REAL DEFAULT 1.0,              -- match confidence (0-1)
    context_snippet TEXT DEFAULT '',           -- what context triggered it
    match_method TEXT DEFAULT 'keyword',       -- hash, keyword, semantic
    FOREIGN KEY (entry_id) REFERENCES entries(id)
);
```

### 4.3 关键索引

```sql
CREATE INDEX idx_entries_type ON entries(type);
CREATE INDEX idx_entries_status ON entries(status);
CREATE INDEX idx_entries_primary ON entries(primary_cat);
CREATE INDEX idx_entries_source ON entries(source);
CREATE INDEX idx_entries_content_hash ON entries(content_hash);
CREATE INDEX idx_entries_observer ON entries(observer);
CREATE INDEX idx_entries_honcho_level ON entries(honcho_level);
CREATE INDEX idx_history_entry ON entry_history(entry_id);
CREATE INDEX idx_history_timestamp ON entry_history(timestamp);
CREATE INDEX idx_decay_hist_entry ON decay_history(entry_id);
CREATE INDEX idx_decay_hist_timestamp ON decay_history(timestamp);
CREATE INDEX idx_recall_entry ON agent_recall_log(entry_id);
CREATE INDEX idx_recall_agent ON agent_recall_log(agent_id);
CREATE INDEX idx_recall_timestamp ON agent_recall_log(timestamp);
```

### 4.4 与 Hermes state.db 集成

现有 `analytics.py` 已经读取 Hermes 的 `state.db` 来计算访问频率。V2 继续利用这个数据源，作为 `access_count` 和 `last_accessed` 的输入。`recall_capture/scanner.py` 进一步实现了从 session log 中自动检测 Agent 对记忆的回访。

---

## 五、前端新增模块

### 5.1 记忆健康仪表盘 ✅

```
┌─────────────────────────────────────────┐
│  记忆健康度: 78/100  ████████░░          │
│                                         │
│  活跃: 42  │  衰退中: 8  │  归档: 15    │
│                                         │
│  ⚠️ 3 条可合并  │  ⚠️ 2 条可能过时       │
│  📊 衰减曲线: /api/decay-trend ✅       │
└─────────────────────────────────────────┘
```

### 5.2 审查面板

- 巩固建议列表：显示 diff，一键确认/拒绝（❌ handler返回"not yet implemented"）
- 衰退预警：即将被遗忘的条目，可钉住或确认删除
- 操作历史：所有自动操作的审计日志 ✅（operations_log）

### 5.3 图谱增强

- 节点大小 → 重要性分数 ✅
- 节点透明度 → 衰减分数 ✅
- 节点边框颜色 → 状态（绿=活跃，黄=衰退，灰=归档）

---

## 六、数据管道与 Agent 接口

SelfMind 的数据管道通过 `unified_sync.py` 直接编排，不通过 Provider interface：

```
unified_sync(store, config)
  → 解析 MEMORY.md/USER.md → entries
  → 解析 Wiki pages → entries
  → sync_honcho() → Honcho API → entries (honcho_obs/honcho_conc)
  → store.bulk_upsert()
  → store.compute_decay_scores()
  → store.create_snapshot()
```

与 Agent 的协作方式：
1. **读取**：直接读 MEMORY.md / USER.md（已有）
2. **写回**：mutations_mixin.py 提供 /api/memories/sync 接口，将 approved entries 写回 Agent 系统
3. **元数据同步**：unified_sync 每 5 分钟自动执行（定时同步）
4. **Recall Capture**：recall_capture/scanner.py 从 session log 检测 Agent 回访，写入 agent_recall_log
5. **Manual Import**：document_importer.py + /api/documents/scan 支持 PDF/MD 等文档导入

---

## 七、实施路线（更新版）

### Phase 1：基础设施 ✅ 已完成
- [x] SQLite 元数据库设计 + 初始化（6张表）
- [x] 从现有 MEMORY.md 生成初始元数据（unified_sync）
- [x] 快照/版本控制机制（snapshots + entry_history）
- [x] 基础 API 扩展（/api/memories, /api/decay-trend, /api/recall/stats）
- [x] 数据管道统一（unified_sync.py + unified_store.py）
- [x] Honcho 数据 sync 接入
- [x] Recall Capture（agent_recall_log + scanner.py）
- [x] Manual Import（document_importer.py + /api/documents/scan）

### Phase 2：巩固引擎 🔄 代码框架存在，未接入运行
- [x] 基础文本相似度检测（SequenceMatcher）
- [ ] 语义相似度计算（embedding）— 未实现
- [x] LLM 驱动的合并/提炼（代码存在，依赖外部API）
- [ ] 冲突检测逻辑 — handler 返回 "not yet implemented"
- [ ] Diff 预览 + 确认流程 — 未实现
- [ ] 定时触发（cron 或内置调度）— 未实现
- [ ] 与 unified_store 写入闭环 — 未实现

### Phase 3：遗忘引擎 🔄 部分实现
- [x] 衰减分数计算（unified_store.compute_decay_scores）
- [x] 衰减历史记录（decay_history 表）
- [x] 衰减曲线可视化（/api/decay-trend + 前端）
- [ ] 状态流转逻辑（active → fading → archived）— 未实现
- [ ] 钉住/保护机制自动流转 — 未实现
- [ ] 回滚能力（快照恢复命令）— 未实现

### Phase 4：前端升级 ✅ 大部分完成
- [x] 健康仪表盘（衰减曲线可视化）
- [x] 图谱视觉增强（透明度、大小映射）
- [ ] 审查面板（巩固建议列表）— 未实现
- [ ] 浅色主题重写 — 未实现
- [ ] 节点交互优化 — 未实现

### Phase 5：智能化 ❌ 未实现
- [ ] 关联发现（跨条目模式识别）
- [ ] 认知偏差检测
- [ ] 自适应衰减速率

---

## 八、竞品差异化

| 特性 | Mem0 | Zep | MemGPT | Honcho | **SelfMind V2** |
|------|------|-----|--------|--------|-----------------|
| 记忆可视化 | ❌ | ❌ | ❌ | ❌ | ✅ 知识图谱 |
| 离线巩固 | ❌ | 部分 | ❌ | ✅ | ❌ 代码存在但未运行 |
| 认知遗忘曲线 | ❌ | ❌ | ❌ | ❌ | 🔄 衰减计算+曲线可视化 |
| 人工审查干预 | ❌ | ❌ | ❌ | ❌ | 🔄 审计日志存在，审查面板未实现 |
| 记忆健康度评估 | ❌ | ❌ | ❌ | ❌ | ❌ 未实现 |
| 透明可解释 | ❌ | 部分 | 部分 | 部分 | ✅ 全流程可审计 |
| Agent 无侵入 | — | — | ❌ 深度耦合 | ❌ 需集成 | ✅ 只读写文件 |
| 衰减曲线可视化 | ❌ | ❌ | ❌ | ❌ | ✅ |
| Recall Capture | ❌ | ❌ | ❌ | ❌ | ✅ |
| Manual Import | ❌ | ❌ | ❌ | ❌ | ✅ |

**核心差异：所有竞品都是"给开发者用的 SDK"，SelfMind 是"给用户看的、可干预的记忆管理系统"。**

---

## 九、设计哲学

> "未经审视的记忆不值得保留。"

1. **透明优先** — 所有自动操作可见、可审计、可回滚
2. **人在回路** — 关键决策（删除、大规模合并）需要人确认
3. **渐进增强** — 每个 Phase 独立可用，不需要全部完成才能上线
4. **Agent 无侵入** — 不改 Agent 代码，通过文件协议协作
5. **认知科学驱动** — 不是拍脑袋设计，对标人类记忆机制
6. **记录演变** — SelfMind 记录 EVOLUTION（entry_history + decay_history），not just current state