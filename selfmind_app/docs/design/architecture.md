# SelfMind 系统架构

## 当前架构（v1.x）

```
                    SelfMind App
                         |
         ┌───────────────┼───────────────┐
         |               |               |
    HTTP Handler    Unified Store    Recall Capture
    (routes/API)    (SQLite SSR)    (agent recall detection)
         |               |               |
    handlers/       memory_store.py   scanner/adapter/matcher
    v1_mixin        unified_sync.py
    stats_mixin     wiki_parser.py
    engines_mixin   parser.py
    mutations_mixin
         |
    ┌────┼────┐
    |    |    |
 Engine Layer (空壳)
 consolidator.py  — 巩固引擎（未实现）
 forgetter.py     — 遗忘引擎（未实现）
 analyzer.py      — 分析引擎（未实现）
```

## 数据流

```
Source Files (MEMORY.md/USER.md/skills/wiki/honcho)
        ↓ sync
   Unified Store (SQLite)
        ↓ query
   HTTP Handler → Frontend (graph/wiki/health)
```

### 核心模块职责

| 模块 | 职责 | 状态 |
|------|------|------|
| unified_store.py | SQLite 单点真相，entries + history + snapshots + operations_log + decay_history + recall_log | 已实现 |
| unified_sync.py | 多数据源同步（memory/wiki/honcho/skills） | 已实现 |
| memory_store.py | Agent 同步（Hermes/Aris/Plato/Grace/OpenClaw） | 已实现 |
| recall_capture/ | Agent 回忆检测（scanner + adapter + matcher） | 已实现 |
| consolidator.py | 巩固引擎（合并/强化） | 空壳 |
| forgetter.py | 遗忘引擎（衰减/状态流转） | 空壳 |
| analyzer.py | 分析引擎 | 空壳 |
| http_handler.py | API 路由 | 已实现 |
| handlers/ | API mixin（v1/stats/engines/mutations） | 已实现 |

## 未来架构（v2.0+）

理论奠基完成后，架构将基于元记忆原子形态重新设计：

```
                    SelfMind App
                         |
         ┌───────────────┼───────────────┐
         |               |               |
    HTTP Handler    Meta-Memory Store  Recall Capture
    (routes/API)    (元记忆+关系SSR)    (recall→strength更新)
         |               |               |
    handlers/       meta_memory.py       scanner/adapter/matcher
    observation     edge.py              ↓
    lifecycle       strength_engine.py   strength update trigger
    visualization
         |
    ┌────┼────┐
    |    |    |
 Engine Layer (基于理论)
 strength_engine  — strength 多因子更新
 lifecycle_engine — 状态流转（活跃→衰减→归档→淘汰）
 consolidation    — 合并/强化
```

关键变化：
1. entries 表 → 元记忆表 + 关系表（基于原子定义）
2. 空壳引擎 → 基于理论的实现
3. strength 取代 decay_score + importance + access_count 的松散组合
4. 边从 0 → 有定义的边原子