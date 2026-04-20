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
| **巩固** | | ✅ 去重、合并、提炼 |
| **遗忘** | | ✅ 衰减、淘汰、归档 |
| **审查** | | ✅ 可视化、人工干预 |
| **关联发现** | | ✅ 跨条目模式识别 |

---

## 二、架构总览

```
┌─────────────────────────────────────────────────┐
│                  用户界面层                       │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ 记忆图谱  │  │ 健康仪表盘│  │ 审查/干预面板 │  │
│  │ (现有D3)  │  │ (新增)    │  │ (新增)        │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
├─────────────────────────────────────────────────┤
│                  API 层 (REST)                   │
├─────────────────────────────────────────────────┤
│                  核心引擎层                       │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ 巩固引擎  │  │ 遗忘引擎  │  │ 分析引擎      │  │
│  │ Consolidator│ Forgetter │  │ Analyzer      │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
├─────────────────────────────────────────────────┤
│                  数据层                           │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ MEMORY.md │  │ 记忆元数据 │  │ 历史快照      │  │
│  │ USER.md   │  │ (SQLite)  │  │ (版本控制)    │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
└─────────────────────────────────────────────────┘
```

---

## 三、三大核心引擎

### 3.1 巩固引擎 (Consolidator)

**对标：人类睡眠中的记忆巩固过程**

功能：
1. **去重** — 检测语义相似的条目，合并为一条
2. **提炼** — 从多条情景记忆中抽象出语义记忆（规律/模式）
3. **关联** — 发现条目间隐含的关系，建立新连接
4. **压缩** — 在保留核心语义的前提下缩短表述

流程：
```
读取 MEMORY.md
  → 语义聚类（embedding 相似度）
  → 冲突检测（矛盾的条目）
  → LLM 生成合并/提炼方案
  → 生成 diff 预览
  → 人工确认 或 自动执行（可配置）
  → 写回 MEMORY.md + 记录变更日志
```

触发方式：
- **定时**：每天凌晨（Agent 的"睡眠时间"）
- **阈值**：记忆条数超过阈值
- **手动**：用户在 UI 点击"整理"

### 3.2 遗忘引擎 (Forgetter)

**对标：艾宾浩斯遗忘曲线 + 适应性遗忘**

每条记忆维护元数据：
```json
{
  "id": "mem_001",
  "content": "...",
  "created_at": "2025-04-01",
  "last_accessed": "2025-04-18",
  "access_count": 7,
  "importance": 0.8,       // 0-1，初始由 Agent 评估
  "decay_score": 0.65,     // 实时计算的衰减分数
  "category": "procedural",
  "status": "active"       // active | fading | archived | deleted
}
```

衰减公式（简化版）：
```
decay_score = importance × (access_frequency × recency_weight)

其中：
- recency_weight = e^(-λ × days_since_last_access)
- access_frequency = log(1 + access_count) / log(1 + max_access_count)
- λ = 衰减速率（可配置，默认 0.05）
```

状态流转：
```
active → fading（衰减分低于阈值，标黄提醒）
fading → archived（持续低分，移入归档）
fading → active（被重新访问，分数回升）
archived → deleted（用户确认 或 超时自动清除）
```

**安全机制**：
- `importance >= 0.9` 的条目不会自动遗忘（核心记忆保护）
- 所有遗忘操作可回滚（快照）
- 用户可"钉住"任何条目，永不遗忘

### 3.3 分析引擎 (Analyzer)

**对标：元认知——对自身记忆的认知**

输出指标：
- **记忆健康度** — 活跃率、冗余率、冲突率、覆盖度
- **认知偏差检测** — 是否过度集中在某些领域
- **增长趋势** — 记忆量随时间变化
- **使用热力图** — 哪些记忆被频繁调用
- **建议** — "3 条记忆可以合并"、"2 条可能已过时"

---

## 四、数据层设计

### 4.1 保留 MEMORY.md 作为主存储

**为什么不迁移到数据库？**
- Agent 直接读写 .md，改数据库要改 Agent 代码
- 纯文本可读性好，用户可手动编辑
- Git 友好，易追踪变更

### 4.2 新增 SQLite 元数据库 (selfmind.db)

```sql
-- 记忆条目的元数据（不重复存内容，content_hash 关联 MEMORY.md）
CREATE TABLE memory_meta (
    id TEXT PRIMARY KEY,
    content_hash TEXT UNIQUE,      -- MEMORY.md 中对应条目的哈希
    source TEXT,                    -- 'memory' | 'user' | 'skill'
    category TEXT,
    subcategory TEXT,
    created_at DATETIME,
    last_accessed DATETIME,
    access_count INTEGER DEFAULT 0,
    importance REAL DEFAULT 0.5,
    decay_score REAL DEFAULT 1.0,
    status TEXT DEFAULT 'active',   -- active|fading|archived|deleted
    pinned BOOLEAN DEFAULT FALSE
);

-- 巩固/遗忘操作日志
CREATE TABLE operations_log (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    operation TEXT,                 -- consolidate|forget|restore|pin
    target_ids TEXT,                -- JSON array of memory IDs
    before_snapshot TEXT,           -- 变更前内容
    after_snapshot TEXT,            -- 变更后内容
    auto_or_manual TEXT,           -- 'auto' | 'manual'
    confirmed BOOLEAN DEFAULT FALSE
);

-- 记忆快照（版本控制）
CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    memory_md TEXT,
    user_md TEXT
);
```

### 4.3 与 Hermes state.db 集成

现有 `analytics.py` 已经读取 Hermes 的 `state.db` 来计算访问频率。V2 继续利用这个数据源，作为 `last_accessed` 和 `access_count` 的输入。

---

## 五、前端新增模块

### 5.1 记忆健康仪表盘

```
┌─────────────────────────────────────────┐
│  记忆健康度: 78/100  ████████░░          │
│                                         │
│  活跃: 42  │  衰退中: 8  │  归档: 15    │
│                                         │
│  ⚠️ 3 条可合并  │  ⚠️ 2 条可能过时       │
│  📊 认知分布: 过度偏向 procedural        │
└─────────────────────────────────────────┘
```

### 5.2 审查面板

- 巩固建议列表：显示 diff，一键确认/拒绝
- 衰退预警：即将被遗忘的条目，可钉住或确认删除
- 操作历史：所有自动操作的审计日志

### 5.3 图谱增强

- 节点大小 → 重要性分数
- 节点透明度 → 衰减分数（越淡越接近遗忘）
- 节点边框颜色 → 状态（绿=活跃，黄=衰退，灰=归档）

---

## 六、与 Agent 的接口协议

SelfMind 不修改 Agent 代码，通过以下方式协作：

1. **读取**：直接读 MEMORY.md / USER.md（已有）
2. **写回**：巩固后写回 MEMORY.md（需要原子操作 + 备份）
3. **元数据同步**：读 Hermes state.db 获取访问数据（已有）
4. **未来可选**：Agent 新增一个 `memory_meta` 工具，写入时同时更新 selfmind.db

---

## 七、实施路线

### Phase 1：基础设施（1-2 周）
- [ ] SQLite 元数据库设计 + 初始化
- [ ] 从现有 MEMORY.md 生成初始元数据
- [ ] 快照/版本控制机制
- [ ] 基础 API 扩展

### Phase 2：巩固引擎（2-3 周）
- [ ] 语义相似度计算（embedding）
- [ ] 冲突检测逻辑
- [ ] LLM 驱动的合并/提炼
- [ ] Diff 预览 + 确认流程
- [ ] 定时触发（cron 或内置调度）

### Phase 3：遗忘引擎（1-2 周）
- [ ] 衰减分数计算
- [ ] 状态流转逻辑
- [ ] 钉住/保护机制
- [ ] 回滚能力

### Phase 4：前端升级（2-3 周）
- [ ] 健康仪表盘
- [ ] 审查面板
- [ ] 图谱视觉增强（透明度、大小映射）

### Phase 5：智能化（持续）
- [ ] 关联发现（跨条目模式识别）
- [ ] 认知偏差检测
- [ ] 自适应衰减速率

---

## 八、竞品差异化

| 特性 | Mem0 | Zep | MemGPT | Honcho | **SelfMind V2** |
|------|------|-----|--------|--------|-----------------|
| 记忆可视化 | ❌ | ❌ | ❌ | ❌ | ✅ 知识图谱 |
| 离线巩固 | ❌ | 部分 | ❌ | ✅ | ✅ |
| 认知遗忘曲线 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 人工审查干预 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 记忆健康度评估 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 透明可解释 | ❌ | 部分 | 部分 | 部分 | ✅ 全流程可审计 |
| Agent 无侵入 | — | — | ❌ 深度耦合 | ❌ 需集成 | ✅ 只读写文件 |

**核心差异：所有竞品都是"给开发者用的 SDK"，SelfMind 是"给用户看的、可干预的记忆管理系统"。**

---

## 九、设计哲学

> "未经审视的记忆不值得保留。"

1. **透明优先** — 所有自动操作可见、可审计、可回滚
2. **人在回路** — 关键决策（删除、大规模合并）需要人确认
3. **渐进增强** — 每个 Phase 独立可用，不需要全部完成才能上线
4. **Agent 无侵入** — 不改 Agent 代码，通过文件协议协作
5. **认知科学驱动** — 不是拍脑袋设计，对标人类记忆机制
