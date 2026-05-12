# Agent DNA 设计

## 定位

Agent DNA 不是 SelfMind 的 DNA，而是 agent 在使用过程中沉淀下来的独特记忆模式和行为特征。

SelfMind 是 agent 的 DNA 测序仪——它不承载 DNA 本身，而是记录、分析、可视化 DNA 的演变过程。

## 闭环流程

实时态（Hermes 工作） → 产生新的记忆/行为
         ↓
SelfMind 采集 → 记录过程态（版本、强度、时间线）
         ↓
SelfMind 分析 → 哪些记忆在衰减？哪些模式重复出现？哪些过时了？
         ↓
SelfMind 训练 → 生成训练结果（建议强化/归档/更新的记忆）
         ↓
反哺实时态 → Hermes 更新高频区（soul.md/MEMORY.md）
         ↓
实时态（Hermes 工作） → 带着更新后的记忆继续工作...

## 分层关系

1. 高频内化层 — Hermes 的 soul.md / 记忆文件
   用户 profile、偏好、工作模式直接在 persona 里，每次对话自动加载，零延迟。

2. 低频参考层 — SelfMind + 查询接口
   查存量记忆的演变历史和关联关系，Hermes 在需要时主动查询。

3. 实时演变层 — SelfMind 数据管道
   统一采集、演变追踪、衰减管理。记录 memory 和 user 文件的变化过程。

不同 agent（Hermes、OpenClaw、亚里士多德等）使用久了会形成不同的记忆基因组合。

## Agent DNA 结构设计

每条记忆条目包含 4 个核心字段：

| 字段 | 含义 | 说明 |
|---|---|---|
| first_seen_at | 产生时间 | 首次采集时间（数据源没有则用采集时间替代） |
| version | 版本号 | 每次内容变化 +1 |
| updated_at | 更新时间 | 最近一次内容/分类/重要性变化的时间 |
| decay_score | 记忆强度(0~1) | 高频使用则高，长期未用则衰减 |

DNA 双螺旋模型：

- 一条链：过程态 — 记录演变（first_seen_at / version / updated_at / decay_score）
- 另一条链：关系态 — 记录连接（primary_cat / secondary_cat / source / type）
- 碱基对：记忆条目内容本身

## 页面设计

打开 Agent DNA 页面时展示：

- 双螺旋可视化结构
- 每条记忆在螺旋上为一个节点
- 节点颜色 = 记忆强度（绿=强，黄=中，红=弱）
- 节点大小 = 重要性
- 点击节点显示记忆详情 + 演变时间线
- 顶部显示当前分析的 agent 名称

## 演进规划

- 当前：数据管道已统一，演变追踪已实现
- 下一阶段：Agent DNA 可视化页面
- 未来：记忆反哺机制（SelfMind 分析结果自动反馈给 agent）