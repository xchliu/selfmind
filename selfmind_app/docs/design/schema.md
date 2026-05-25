# SelfMind 数据库 Schema 定义与演进计划

## 当前 Schema（v1.x）

当前 entries 表定义在 `unified_store.py` 的 SCHEMA_SQL 中。

### entries 表

| 字段 | 类型 | 说明 | 原子归属 |
|------|------|------|----------|
| id | TEXT PK | 确定性ID: type:source:sha256[:8] | → 本质层 |
| content_hash | TEXT | SHA256 去重 | → 计算层 |
| content | TEXT | 记忆内容全文 | → 本质层 |
| content_preview | TEXT | 前120字符展示 | → 计算层 |
| type | TEXT | memory/wiki/honcho_obs/honcho_conc/skill | → 需改为原子type（fact/event/summary/observation） |
| source | TEXT | 文件路径或API端点 | → 本质层（来源） |
| source_profile | TEXT | agent profile | → 本质层（来源） |
| primary_cat | TEXT | 分类（如autobiographical） | → 疑问：分类是本质还是标签？ |
| secondary_cat | TEXT | 二级分类 | → 同上 |
| label | TEXT | 展示标签 | → 计算层 |
| tags | TEXT(JSON) | 标签数组 | → 计算层 |
| observer | TEXT | Honcho谁观察 | → 本质层（来源细节） |
| observed | TEXT | Honcho被观察者 | → 本质层（来源细节） |
| honcho_level | TEXT | explicit/inductive/deductive | → 疑问：Agent评价，不属于原子？ |
| honcho_doc_id | TEXT | Honcho文档ID | → 本质层（来源细节） |
| importance | REAL | 0-1重要性 | → **应删除**，不属于原子 |
| decay_score | REAL | 衰减分数 | → **应改为** strength |
| access_count | INT | 访问次数 | → **应删除**，属于计算层 |
| version | INT | 版本号 | → 计算层 |
| first_seen_at | TEXT | 首次出现时间 | → 本质层（created_at） |
| created_at | TEXT | 创建时间 | → 本质层 |
| updated_at | TEXT | 更新时间 | → 计算层 |
| last_accessed | TEXT | 最近访问 | → **应改为** last_recalled_at |
| last_recalled | TEXT | 最近回忆时间 | → 状态层 |
| last_synced_at | TEXT | 最近同步 | → 计算层 |
| status | TEXT | active/inactive/archived | → 状态层（需扩展：衰减/归档/淘汰） |
| pinned | INT | 是否固定 | → 计算层 |

### 辅助表

| 表 | 说明 | 状态 |
|----|------|------|
| entry_history | 内容版本变更记录 | 已实现 |
| snapshots | 同步时源文件完整快照 | 已实现 |
| operations_log | 所有变更操作日志 | 已实现 |
| decay_history | decay_score 变更历史 | 已实现 |
| agent_recall_log | Agent回忆检测日志 | 已实现 |

### 问题

1. **0 条边** — 没有 edges 表，图谱是散点不是网络
2. **字段归属混乱** — importance/access_count 不属于原子，honcho_level 是 Agent 评价维度
3. **type 语义不匹配** — 当前 type 是数据来源类型（memory/wiki/honcho_obs），不是记忆内容类型（fact/event/summary/observation）
4. **strength 语义缺失** — decay_score 只是衰减维度，不是综合 strength
5. **理论与实现断裂** — 论文用(s,c,l,t)四元组，代码用(importance,decay_score,access_count)

## 目标 Schema（v2.0，基于元记忆原子定义）

### meta_memories 表（元记忆原子）

**本质层（不变）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | UUID |
| content | TEXT | 记忆内容 |
| type | TEXT | fact / event / summary / observation |
| source | TEXT | observation / inference / input |
| source_detail | TEXT | 具体来源（agent名/文件路径/API端点） |
| created_at | TEXT | 创建时间 |

**状态层（随时间变）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| strength | REAL | 综合强度，核心状态 |
| last_recalled_at | TEXT | 最近唤起时间 |
| lifecycle_state | TEXT | active / fading / archived / eliminated |

### edges 表（关系原子）

类型、属性、强度待 Phase 1.3 定义后确定。

### 计算层（不存储，实时算或辅助表保留）

| 表/字段 | 说明 |
|---------|------|
| content_preview | 前120字符，展示用 |
| content_hash | SHA256 去重 |
| tags | 标签数组 |
| recall_log | 唤起事件记录 |
| strength_history | strength 变更历史 |
| operations_log | 操作日志 |

## 演进计划

Phase 2 开始时，基于原子定义完成 schema 设计后再执行迁移。

关键约束：理论先行，Phase 1 全部完成前不改 schema。

旧数据迁移策略待设计（entries → meta_memories + edges）。