# SelfMind 开发任务（苏格拉底 → DSH）

> 来源：苏格拉底（Hermes Agent），2026-10-26
> 监督：苏格拉底负责 git log / cargo test / python test 验证 + 向坦哥微信汇报
> 代码库：~/Documents/selfmind/

---

## 项目背景

SelfMind 是智能体记忆追踪与观测系统，当前用 SQLite 存储（768MB，606条 entries）。
坦哥要求：SelfMind 的 Proactive Engine + ProbeDB 存储迁移都交给 DSH 开发。

## 任务一：Proactive Engine 集成

当前状态：苏格拉底已写独立脚本 `~/.hermes/scripts/selfmind_proactive.py`，跑在 cron 里。
需要 DSH 做：把 Proactive Engine 集成进 SelfMind 代码库作为正式模块。

### 5.3 认知缺口预警（已跑通，需整合）
- 调用 `/api/analyze/should-know-gaps`
- 红/黄标 → 格式化推送
- 24h 去重

### 5.4 记忆衰减预警（已跑通，需整合）
- 调用 `/api/meta/health` + `/api/meta/entries`
- decay < 0.3 预警，< 0.2 严重
- 24h 去重

### 5.5 知识刷新提醒（待开发）
- 检测某个领域（secondary_cat）长期未更新
- 超过 N 天未新增条目或未触发 recall → 提醒调研
- 需要定义"领域"的粒度和刷新周期

## 任务二：ProbeDB 存储迁移

详见 `probedb/docs/selfmind-integration-requirements.md`

3个阻断项必须先补：
1. CREATE INDEX 支持
2. 表别名（JOIN 解析）
3. 参数化查询（? 占位符）

补完后迁移 `selfmind_app/unified_store.py`（SQLite → ProbeDB）

---

## SelfMind 代码结构

```
selfmind_app/
├── unified_store.py    # 存储层（迁移目标）
├── should_know.py      # 认知缺口检测
├── analyzer.py         # 分析引擎
├── consolidator.py     # 巩固引擎
├── forgetter.py        # 遗忘引擎
├── http_handler.py     # HTTP API（1092行，路由层）
├── config.py           # 配置
├── handlers/           # HTTP handler mixins
│   ├── stats_mixin.py
│   ├── mutations_mixin.py
│   ├── engines_mixin.py
│   └── v1_mixin.py
└── providers/          # 数据源
```

## 验收标准

1. Proactive Engine 作为 SelfMind 内部模块可运行
2. `cargo test`（ProbeDB 侧）全绿
3. `python -m pytest tests/`（SelfMind 侧）全绿
4. unified_store.py 用 ProbeDB 跑通 entries 表 CRUD
5. 14个 INDEX 创建不报错
6. JOIN 带别名能跑
7. 参数化查询可用

## 关联文档
- SelfMind 研发计划：`aiknowledge/selfmind/REQUIREMENT.md`
- SelfMind 项目追踪：`aiknowledge/selfmind/selfmind-development.md`
- ProbeDB 需求文档（给 DSH）：`probedb/docs/selfmind-integration-requirements.md`