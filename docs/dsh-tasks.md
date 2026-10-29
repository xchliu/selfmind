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

---

## 任务三：Phase 6 记忆生命周期管理 ← 新（2026-10-29）

> 背景：坦哥与苏格拉底讨论衰减预警数据后，指出 SelfMind 当前只在做"存"——入库就完了。需要一个完整的存→理→提→跟四层生命周期。
> 详细需求见 `aiknowledge/selfmind/REQUIREMENT.md` Phase 6。

### 6.1 Schema 扩展（依赖 Phase 2）

在 `meta_memories` 表中新增字段（与 Phase 2 新 schema 同步推进）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `entry_type` | TEXT | person/task/preference/project/open_issue/knowledge/skill |
| `deadline` | TEXT(ISO date) | 截止日期，task/open_issue 必填 |
| `priority` | TEXT | high/medium/low |
| `owner` | TEXT | 关联人员 ID |
| `lifecycle_status` | TEXT | active/in_progress/done/archived |

### 6.2 入库自动分类

`unified_store` 写入入口增加分类逻辑：
- MEMORY.md 中 `[XX] open_userid=...` → `entry_type=person`
- 含截止日/状态列 → `entry_type=task`
- 含"偏好/风格/方式"关键词 → `entry_type=preference`
- 含"已联系/待解决/失效/key 已" → `entry_type=open_issue`
- Wiki 项目文档 → `entry_type=project`
- 现有 `skill` 条目 → `entry_type=skill`

### 6.3 按类型差异化衰减曲线

替换当前统一的线性衰减，`forgetter.py` 改造为按 `entry_type` 分策略：

| entry_type | 半衰期 | 到期行为 |
|-----------|--------|---------|
| person | 180d | 不自动过期 |
| preference | 90d | 不自动过期，引用即重置到 1.0 |
| project | 60d | 归档时标记 inactive |
| task | 14d | 到期未闭环→自动升级→超时归档 |
| open_issue | 7d | 定期追问直到显式关闭 |
| knowledge | 90d | 不自动过期 |
| skill | ∞ | 不衰减 |

### 6.4 多通道 Recall 感知

Recall 触发不再只走 API 查询一条路，新增：

| 通道 | 实现方式 | 优先级 |
|------|---------|--------|
| Skill 加载 | `skill_view()` 调用时自动触发对应条目 recall | P0 |
| 对话引用 | Hermes 侧检测对话中出现的记忆关键词，回调 SelfMind recall API | P0 |
| 任务执行 | cron 执行引用某条记忆时触发 recall | P1 |
| 关联激活 | 同一 owner 或同一 project 条目被 recall 时连带激活 | P1 |

### 6.5 升级衰减预警 → 多场景提醒引擎

在 Phase 5.4 基础上，从单一"decay < 0.3"升级为多场景：

| 场景 | 触发条件 | 优先级 |
|------|---------|--------|
| 📅 截止日提醒 | task deadline 前 7d/3d/1d | P0 |
| ⚠️ 异常提醒 | task 过 deadline 但 status 未更新 | P0 |
| 🔗 关联提醒 | 对话提及某人时，自动关联该人的 open_issue | P0 |
| 📉 衰减预警 | 按类型差异化阈值（person<0.15 / task<0.3 / open_issue<0.2） | P1 |
| 🧠 冷知识提醒 | 人员档案超过 90d 未互动 | P1 |

### 6.6 闭环追踪

新增提醒状态机：`pending → delivered → acknowledged → resolved`
- 提醒后 N 天无响应 → 升级提醒（参考 Phase 5 推送通道）
- task 过期 + 用户确认"不管了" → `lifecycle_status=archived`
- open_issue 的解决自动关联到对应 person 的 recall

---

## 验收标准（追加）

8. Phase 6.1: `meta_memories` 表含全部新增字段，`unified_store` 读写正常
9. Phase 6.2: 新入库条目自动打上 `entry_type`，现有条目支持回填
10. Phase 6.3: `forgetter.py` 按类型分策略衰减，`cargo test` / `python -m pytest` 覆盖各类型
11. Phase 6.4: Skill 加载 + 对话引用触发 recall，decay 值可观测回升
12. Phase 6.5: 多场景提醒可配置化，至少完成截止日 + 异常 + 衰减三个场景
13. Phase 6.6: 提醒状态机完整，`lifecycle_status` 流转可追溯