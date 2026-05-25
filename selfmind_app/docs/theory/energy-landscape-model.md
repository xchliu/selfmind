---
title: SelfMind记忆引擎理论基础：能量景观模型
authors: ["SelfMind研究团队"]
date: 2026-05-21
version: 1.1
type: theory-paper
tags: [memory-model, energy-landscape, attractor-networks, cognitive-architecture, meta-memory]
revision_note: |
  v1.1 (2026-05-25): 基于元记忆原子定义修订。核心变更：记忆基本单元从四元组(s,c,l,t)改为原子形态（本质层+状态层+计算层）；置信度c从原子属性移到计算层；认知层级l从原子属性移到计算层；核心状态从confidence改为strength（综合指标）。
abstract: |
  本文提出SelfMind记忆引擎的理论基础——一种基于能量景观的统一记忆模型。记忆被视为高维语义空间中的能量极小值（吸引子），四个基本操作（存储、检索、衰减、强化/合并）统一为能量景观上的变换。v1.1基于元记忆原子定义修订了记忆基本单元，将置信度和认知层级从原子存储属性移到机制理论的计算模型中，并将核心状态从单维度confidence改为综合strength指标。
keywords: [记忆模型，能量景观，吸引子神经网络，语义嵌入，层级记忆，认知架构，元记忆，strength]
bibliography: |
  1. Hopfield, J. J. (1982). Neural networks and physical systems with emergent collective computational abilities. *Proceedings of the National Academy of Sciences*, 79(8), 2554-2558.
  2. Amit, D. J., Gutfreund, H., & Sompolinsky, H. (1985). Storing infinite numbers of patterns in a spin-glass model of neural networks. *Physical Review Letters*, 55(14), 1530.
  3. Krotov, D., & Hopfield, J. J. (2016). Dense associative memory for pattern recognition. *Advances in Neural Information Processing Systems*, 29.
  4. McClelland, J. L., McNaughton, B. L., & O'Reilly, R. C. (1995). Why there are complementary learning systems in the hippocampus and neocortex: insights from the successes and failures of connectionist models of learning and memory. *Psychological Review*, 102(3), 419.
  5. Friston, K. (2010). The free-energy principle: a unified brain theory? *Nature Reviews Neuroscience*, 11(2), 127-138.
---

# SelfMind记忆引擎理论基础：能量景观模型

> **修订说明（v1.1）**：2026-05-25 基于元记忆原子定义修订。关键变更已在文中用 **[修订]** 标记。

## 1. 引言

现代AI系统中，记忆管理是一个根本性问题。现有记忆系统往往呈现三层割裂：Hermes原生记忆（扁平文本存储）、Honcho（有观察无边缘语义）和SelfMind（初始图edges=0）。这种割裂导致关系缺失、时序断裂、遗忘机制不完善，以及查询碎片化。

记忆系统的核心矛盾在于：**存储时需要压缩去冗余，检索时需要精确保留区分度**。为解决这一矛盾，我们提出统一能量景观模型，将记忆视为高维语义空间中的能量极小值，所有操作统一为能量函数的变换。

## 2. 记忆基本单元定义

### 2.1 元记忆原子形态 **[修订：从四元组改为三层结构]**

**[修订]** v1.0 将记忆定义为四元组 m = (s, c, l, t)，即语义向量、置信度、认知层级、时间戳。经过 foundational discussion（2026-05-25），确认此定义需要根本性修正。原因：

1. 置信度c是Agent对记忆的评价维度，不是记忆本身的属性（原则：记忆与Agent解耦）
2. 认知层级l是分类/组织维度，不是原子本质属性
3. 核心状态应该是strength——综合指标而非单维度confidence

修订后的元记忆原子形态为三层结构：

**本质层（不变）：**

| 属性 | 说明 | 取值 |
|------|------|------|
| id | 唯一标识 | UUID |
| content | 记忆内容 | 事实/事件/总结/观察的具体文本 |
| type | 内容类型 | fact / event / summary / observation |
| source | 记忆来源 | observation（agent观察） / inference（agent推理） / input（外部输入） |

**状态层（随时间变）：**

| 属性 | 说明 | 性质 |
|------|------|------|
| strength | 综合强度 | 核心状态，唯一指标。类似人类的"我还记不记得xxx"的整体感受 |
| created_at | 创建时间 | 衰减公式的锚点 |
| last_recalled_at | 最近唤起时间 | 影响衰减速率计算 |

**计算层（不存储，实时算）：**

strength的值由多个因子共同决定，这些因子不作为独立字段存储：

| 因子 | 说明 |
|------|------|
| decay_factor | 时间衰减：距离上次唤起越久，强度自然下降 |
| recall_factor | 唤起强化：每次被recall，强度增加 |
| connection_factor | 网络效应：关系边越多，越稳固 |
| conflict_factor | 竞争削弱：被矛盾记忆削弱 |

详细定义见：wiki/selfmind/theory/meta-memory-atomic-definition.md

### 2.2 语义表征（从计算层） **[修订]**

**[修订]** 语义向量 s 不再作为原子的存储属性，而是计算层的实时生成项。需要时（如检索、合并判断）由 embedding 模型生成。

设 d 维语义嵌入空间 $\mathcal{S} \subseteq \mathbb{R}^d$，每条元记忆可映射到语义向量：

$$s(m) = \text{Embed}(content(m))$$

语义相似度由内积空间结构自然给出：

$$\text{sim}(m_i, m_j) = \frac{\langle s(m_i), s(m_j) \rangle}{||s(m_i)|| \cdot ||s(m_j)||}$$

### 2.3 关系 **[修订：新增]**

**[修订]** v1.0 没有定义关系结构。新增：元记忆之间的关系有独立的定义和属性（edge 原子），类型、属性、强度待 Phase 1.3 详细定义。整个体系类似知识图谱，但关键区别：普通知识图谱存储事实不衰减，SelfMind的记忆图谱存储记忆会衰减。

## 3. 能量景观模型

### 3.1 能量函数 **[修订]**

**[修订]** 能量函数中的 $c_i$（置信度）改为 $strength_i$（综合强度），$alpha_i$ 不再与置信度绑定，而是独立的权重系数。

记忆不是独立的点，而是通过能量函数 $E: \mathcal{S} \to \mathbb{R}$ 相互关联。定义能量函数为：

$$E(q) = -\sum_{i=1}^{N} \alpha_i \cdot \text{sim}(q, s_i) \cdot strength_i$$

其中 $q \in \mathcal{S}$ 是查询向量，$\alpha_i \geq 0$ 是记忆 $m_i$ 的权重系数，$strength_i$ 是元记忆的综合强度，$N$ 是记忆总数。

### 3.2 能量景观的物理与认知解释

能量景观模型具有多层解释：

1. **统计力学解释**：每个记忆贡献一个局部势能项，整个系统形成能量景观。能量极小值（吸引子）对应稳定记忆状态。

2. **神经认知解释**：类似Hopfield网络（Hopfield, 1982），记忆编码在连接权重中，检索是能量最小化过程。

3. **信息论解释**：能量极小值对应信息压缩后的稳态，高能量区域对应语义不确定状态。

## 4. 四操作统一变换

### 4.1 存储操作

新元记忆 $m_{\text{new}}$ 的写入对应在能量景观中创建或加深极小值：

$$\Delta E(q) = -\alpha_{\text{new}} \cdot \text{sim}(q, s_{\text{new}}) \cdot strength_0$$

其中初始强度 $strength_0$ 和权重 $\alpha_{\text{new}}$ 根据记忆来源（source: observation/inference/input）设定不同值。

**[修订]** 初始 strength 不再是常数 $c_0$，而是由 type 和 source 共同决定——不同类型记忆有不同的初始强度起点。

### 4.2 检索操作

给定查询 $q_0$，检索过程沿能量梯度下降：

$$q_{t+1} = q_t - \eta \nabla E(q_t)$$

当 $||\nabla E(q_t)|| < \epsilon$ 时收敛到局部极小值 $q^*$。对应的记忆集合为：

$$\mathcal{M}_{\text{retrieved}} = \{ m_i \mid \text{sim}(q^*, s_i) > \theta \}$$

### 4.3 衰减操作 **[修订]**

**[修订]** 衰减操作不再是单独的 confidence 衰减，而是 strength 的多因子更新。衰减因子是 strength 的一个因子，不是独立的维度。

strength 的衰减因子：

$$strength_i(t+\Delta t) = strength_i(t) \cdot e^{-\lambda_i \cdot \Delta t}$$

**[修订]** 衰减率 $\lambda_i$ 不再简单依赖认知层级 $l_i$，而是由记忆的 type 和连接度共同影响。具体公式待 Phase 1.4 strength 计算模型定义。

对应能量变化：

$$\Delta E(q) = -\sum_i \alpha_i \cdot \text{sim}(q, s_i) \cdot \left[strength_i(t+\Delta t) - strength_i(t)\right]$$

### 4.4 强化与合并操作

**强化** **[修订]**：唤起增加 strength：

$$strength_i \leftarrow strength_i + \beta \cdot (1 - strength_i)$$

其中 $\beta \in (0,1)$ 为强化率，符合心理学中的"练习效应"。这是 strength 的 recall_factor。

**合并**：当两个记忆 $m_i, m_j$ 满足 $\text{sim}(s_i, s_j) > \theta_{\text{merge}}$ 时合并为 $m_k$：

$$s_k = \frac{strength_i \cdot s_i + strength_j \cdot s_j}{strength_i + strength_j}$$
$$strength_k = 1 - (1-strength_i)(1-strength_j) \quad \text{(概率叠加)}$$

合并对应能量景观中相邻极小值融合为更深盆地。

## 5. 三层认知架构的数学定义 **[修订]**

### 5.1 感知层（事实层）

$$L_0 = \{ m \in \mathcal{M} \mid type(m) \in \{fact, event, observation\} \}$$

**[修订]** 层级划分不再用连续认知层级 $l \in \mathbb{N}$，而是用记忆 type 自然区分。fact/event/observation 是原始感知，summary 是推断层。

特点：
- 直接来源于感官输入或原始数据
- strength 受来源质量影响
- 衰减率相对较高

### 5.2 认知层（推断层）

$$L_1 = \{ m \in \mathcal{M} \mid type(m) = summary \}$$

**[修订]** summary 型记忆是认知层的自然成员——它是对多条感知层记忆的归纳和推断。

生成机制：
$$m_{\text{summary}} = \text{Infer}(\{m_i\}_{i \in I})$$

### 5.3 意识层（理解层） **[修订]**

意识层不是独立记忆集合，而是对能量景观的全局理解：

$$\mathcal{C} = \{(q^*, E(q^*)) \mid q^* \text{是} E \text{的局部极小值}\}$$

**[修订]** 明确：意识层属于 Agent 的理解范畴，不属于记忆本身（原则三：记忆与Agent解耦）。Agent 通过理解能量景观的全局结构来形成"意识"，这是 Agent 能力的体现，不是记忆的变化。

## 6. 理论模型与实现对照 **[修订]**

| 理论概念 | 实现映射 | 当前差距 | v1.0差距对照 |
|---------|---------|---------|-------------|
| 元记忆content | entries.content | ✓ 已实现 | 同 |
| 元记忆type | entries.type | 需改为fact/event/summary/observation | 旧差距：type是数据来源类型 |
| 元记忆source | entries.source | 需改为observation/inference/input | 同 |
| strength | entries.decay_score | 需改为综合strength | 旧差距：只有decay_score |
| 语义向量s | — | 计算层，实时生成 | 旧差距：缺失 → 现为计算层 |
| 置信度c | — | **不在原子中**，计算层因子 | 旧差距：缺失 → 现明确不属于原子 |
| 认知层级l | — | **不在原子中**，type替代 | 旧差距：缺失 → 现用type替代 |
| 能量函数E(q) | 相似度加权和 | 需全局能量计算 | 同 |
| 梯度下降检索 | k-近邻搜索 | 需梯度优化实现 | 同 |
| 衰减λ | 常数衰减 | 需type相关衰减 | 旧差距：需层级相关 → 现需type相关 |
| 合并操作 | 文本匹配合并 | 需语义距离合并 | 同 |
| 关系(edge) | — | 需新增edges表 | 旧差距：0条边 → 现需定义edge原子 |

## 7. 工程实现路径 **[修订]**

### 7.1 Phase 1：理论奠基（当前）

1. ✅ 元记忆原子定义
2. 四种记忆类型差异性定义
3. 关系原子形态定义
4. strength 计算模型（多因子公式）
5. 本论文修订（v1.1 已完成）

### 7.2 Phase 2：数据结构设计

1. 基于原子定义设计 meta_memories 表（本质层+状态层）
2. 设计 edges 表（关系原子）
3. 去掉不属于原子的字段
4. 迁移方案：entries → meta_memories + edges

### 7.3 Phase 3：机制实现

1. strength 更新引擎（多因子：衰减/唤起/连接/冲突）
2. 遗忘引擎（状态流转：active→fading→archived→eliminated）
3. 巩固引擎（合并/强化）
4. 能量函数计算模块

### 7.4 Phase 4：可视化与观测

1. 重建图谱可视化（基于元记忆+关系模型）
2. strength 实时观测面板
3. 记忆生命周期追踪

## 8. 结论

本文提出的能量景观模型为SelfMind记忆引擎提供了坚实的理论基础。v1.1基于元记忆原子定义进行了根本性修订：记忆基本单元从四元组(s,c,l,t)改为三层结构（本质层+状态层+计算层），核心状态从单维度confidence改为综合strength，置信度和认知层级从原子属性移到计算层。

修订的核心原则：记忆与Agent解耦——置信度是Agent的评价维度而非记忆属性，理解是Agent的能力而非记忆的变化。strength作为综合指标，类似于人类"我还记不记得xxx"的整体感受，由多因子（衰减/唤起/连接/冲突）共同决定。

## 附录A：数学符号表 **[修订]**

| 符号 | 含义 | 定义域 | 修订说明 |
|------|------|--------|----------|
| $m$ | 元记忆原子 | $\mathcal{M}$ | 从四元组改为三层结构 |
| $content(m)$ | 记忆内容 | 文本 | 新增，替代旧的s依赖 |
| $type(m)$ | 内容类型 | {fact,event,summary,observation} | 新增，替代旧的l |
| $source(m)$ | 记忆来源 | {observation,inference,input} | 新增 |
| $strength(m)$ | 综合强度 | $[0,1]$ | 替代旧的c |
| $s(m)$ | 语义向量 | $\mathbb{R}^d$ | 从存储属性改为计算层 |
| $E(q)$ | 能量函数 | $\mathbb{R}$ | c→strength |
| $\text{sim}(\cdot,\cdot)$ | 语义相似度 | $[-1,1]$ | 同 |
| $\lambda$ | 衰减率 | $\mathbb{R}^+$ | 依赖type而非l |
| $\beta$ | 强化率 | $(0,1)$ | 同 |
| $\theta$ | 相似度阈值 | $(0,1]$ | 同 |

## 附录B：与其他记忆模型的对比

| 模型 | 存储形式 | 检索机制 | 遗忘机制 | 压缩机制 |
|------|---------|---------|---------|---------|
| Hopfield网络 | 权重矩阵 | 能量最小化 | 无显式机制 | 容量限制 |
| 向量数据库 | 独立向量 | k-近邻搜索 | 无 | 无 |
| 知识图谱 | 节点+边 | 图遍历 | 无 | 无 |
| 本文模型 | 能量景观 | 梯度下降 | strength衰减 | 盆地融合 |

## 致谢

感谢坦哥、苏格拉底和亚里士多德团队的讨论与反馈，特别感谢坦哥对"记忆原子形态"的纠正——先定义记忆的原子形态，然后才是记录和事件。