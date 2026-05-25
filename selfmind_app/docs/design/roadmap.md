# SelfMind 研发路线

## Phase 1：理论奠基（当前）

理论先行，先定义清楚再动手写代码。

| 序号 | 内容 | 状态 | 产出 |
|------|------|------|------|
|| 1.1 | 元记忆原子定义 | done | wiki/selfmind/theory/meta-memory-atomic-definition.md |
| 1.2 | 四种记忆类型差异性定义 | next | 待讨论：衰减速率是否不同？strength起点是否不同？ |
| 1.3 | 关系（edge）原子形态 | next | 待讨论：类型、属性、强度 |
| 1.4 | strength 计算模型 | next | 待讨论：多因子公式 |
|| 1.5 | 修订能量景观论文 | planned | wiki/selfmind/theory/selfmind-theory-paper.md 需对齐原子定义 |

## Phase 2：数据结构设计

基于原子定义重新设计数据库 schema。

| 序号 | 内容 | 状态 |
|------|------|------|
| 2.1 | 元记忆表设计（本质层+状态层） | planned |
| 2.2 | 关系表设计（edge原子形态） | planned |
| 2.3 | 去掉不属于原子的字段（置信度等） | planned |
| 2.4 | 迁移方案：旧 entries → 新 schema | planned |

当前 entries 表的问题：
- 置信度、认知层级等字段不属于记忆原子（原则三：Agent评价不属于记忆）
- 0 条边，图谱是散点不是网络
- 衰减公式直接套用艾宾浩斯，缺乏理论依据
- 理论与实现的断裂——论文用(s,c,l,t)四元组，代码用(importance,decay_score,access_count)

详见 docs/design/schema.md

## Phase 3：机制实现

| 序号 | 内容 | 状态 |
|------|------|------|
| 3.1 | strength 更新引擎 | planned — 多因子：衰减/唤起/连接/冲突 |
| 3.2 | 遗忘引擎 | planned — 状态流转：活跃→衰减→归档→淘汰 |
| 3.3 | 巩固引擎 | planned — 合并/强化 |
| 3.4 | 分析引擎 | planned |

## Phase 4：可视化与观测

| 序号 | 内容 | 状态 |
|------|------|------|
| 4.1 | 重建图谱可视化（基于新元记忆+关系模型） | planned |
| 4.2 | strength 实时观测面板 | planned |
| 4.3 | 记忆生命周期追踪 | planned |
| 4.4 | Agent DNA 视图 | planned |

## 关键原则

1. 理论先行——没有稳定的原子定义前，不推进 schema 重建和引擎实现
2. strength 是综合指标——多因子计算模型待设计，不能简单拍参数
3. Agent 评价维度不属于记忆——置信度等留在机制理论的计算层，不进原子存储
4. wiki 放思考和理念，docs/ 放技术设计和 API 文档