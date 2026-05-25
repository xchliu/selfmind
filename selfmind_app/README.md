# SelfMind

智能体记忆追踪与观测系统。

## 定位

SelfMind 聚焦智能体记忆，走独立产品路线，用 Nous 团队验证。

理论先行：先定义记忆的基本数据结构（元记忆原子），再定义机制理论，最后实现和迭代系统。

## 核心概念

- **元记忆（meta-memory）**：智能体记忆的原子形态。可以是事实、事件、总结、观察
- **strength**：元记忆唯一核心状态，综合指标而非单维度。类似人类的"我还记不记得xxx"
- **本质与状态分离**：记忆的本质（内容、类型、来源）不变，状态（strength）随时间演进
- **记忆与 Agent 解耦**：Agent 的理解能力变化不是记忆的变化

详细定义见 [docs/theory/meta-memory-atomic-definition.md](docs/theory/meta-memory-atomic-definition.md)

## 文档结构

```
docs/
  theory/                    # 理论定义（wiki同步）
    meta-memory-atomic-definition.md   # 元记忆原子形态
    energy-landscape-model.md          # 能量景观论文（待修订）
  design/                    # 技术设计
    schema.md                # 数据库 schema 定义与演进计划
    architecture.md          # 系统架构
    roadmap.md               # 研发路线
  selfmind-series/           # 公众号系列文章草稿
    04/
      draft-v1.md
```

Wiki 位置：~/Documents/aiworkspace/wiki/ （放思考和理念，不放技术设计）

## 当前状态

- Phase 1 理论奠基：元记忆原子定义已完成 foundational discussion
- v1.x 可视化基本闭环（图谱/Wiki/衰减曲线/sparkline/Docker）
- v2.0 记忆 CRUD 进行中（小亚负责 UI 闭环）

## 研发路线

| Phase | 内容 | 状态 |
|-------|------|------|
| 1 | 理论奠基：原子定义→类型差异→关系原子→strength模型→论文修订 | 进行中 |
| 2 | 数据结构：基于原子定义重新设计 schema | 待开始 |
| 3 | 机制实现：strength更新引擎→遗忘引擎→巩固引擎 | 待开始 |
| 4 | 可视化与观测：重建图谱→strength面板→生命周期追踪 | 待开始 |

详细路线见 [docs/design/roadmap.md](docs/design/roadmap.md)