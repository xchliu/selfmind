# SelfMind 演进路线图

> 基于 AI Memory Survey 论文框架 (4W: When/What/How/Which)

---

## 📍 当前状态 (v0.1)

| 维度 | 现状 |
|------|------|
| **数据来源** | Hermes MEMORY.md + USER.md (183 节点) |
| **存储** | Raw text (MD 文件) |
| **遗忘机制** | forgetter.py 已实现，但未触发 |
| **关系** | 结构定义存在，但 **边数为 0** |
| **记忆类型** | procedural/semantic/episodic/social |

---

## 🎯 演进路线 (分阶段)

### Phase 1: 修复核心问题 (1-2周)

> 确保基础功能正常工作

| 任务 | 优先级 | 论文对应 |
|------|--------|----------|
| **修复边关系** | P0 | How: Graph 存储是关系推理的基础 |
| **激活遗忘引擎** | P0 | When: 生命周期管理核心 |
| **完善访问统计** | P1 | When: 遗忘曲线依赖访问数据 |

#### 1.1 修复边关系 (P0)

**问题**: 467 条边定义，但实际为 0

**方案**:
```python
# 在 parser.py 中增强关系提取
- 复用 relation_keywords 配置
- 识别 "§" 分段间的引用关系
- 建立记忆间的时间顺序边（before/after）
```

#### 1.2 激活遗忘引擎 (P0)

**问题**: 访问次数全是 0，遗忘曲线未触发

**方案**:
```python
# 在 http_handler.py 中添加访问追踪
- 每次 GET /api/memories 记录 access_time
- forgetter.py 的 decay 计算基于访问间隔
- 新增 "回忆" API: POST /api/memories/{id}/recall
```

---

### Phase 2: 对齐论文框架 (2-4周)

> 实现 4W 完整能力

#### 2.1 What: 完善记忆类型

| 类型 | 实现方式 | 优先级 |
|------|----------|--------|
| **Procedural** | ✅ 已有 146 条 | - |
| **Declarative** | ✅ episodic/semantic | - |
| **Metacognitive** | 🔜 新增"自我反思"类 | P1 |
| **Personalized** | ✅ social/key_people | - |

**Metacognitive 实现**:
```
新增 primary: "metacognitive"
记录: "我擅长什么、不擅长什么、踩过什么坑"
来源: 每次任务完成后让用户确认学习到什么
```

#### 2.2 How: 混合存储架构

| 存储方式 | 用途 | 实现方式 |
|----------|------|----------|
| **Raw text** | 完整信息 | ✅ MD 文件 |
| **Graph** | 关系推理 | 🔜 修复边 (Phase 1) |
| **Vector** | 语义检索 | 🔜 下一阶段 |

**向量检索设计**:
```python
# 可选方案
- 轻量: 用 sentence-transformers 做 embedding
- 或直接用 LLM 提取 embedding 存在 metadata 中
- API: POST /api/search - 语义相似度召回
```

#### 2.3 When: 完整生命周期

| 阶段 | 实现 | 优先级 |
|------|------|--------|
| **Transient** | 上下文窗口（LLM） | N/A |
| **Session** | 当前会话记忆 | 🔜 |
| **Persistent** | 长期记忆 + 遗忘 | 🔜 Phase 1 |

**Session 记忆设计**:
```
- 临时记忆区 (session memories)
- 会话结束时可选择: 遗忘 / 固化到长期 / 总结
- 结构: {type: "session", content: "...", session_id: "xxx"}
```

---

### Phase 3: 多智能体支持 (4-8周)

> 论文重点警告的三个问题

#### 3.1 Memory Misalignment 对齐

**问题**: 多 agent 对全局状态理解偏离

**方案**:
```
- 引入 "全局状态记忆" (Global Memory)
- 每次多 agent 协作后同步状态
- 检测: 当节点间关系出现矛盾时预警
```

#### 3.2 Redundancy Cycle 去重

**问题**: 重复解决已被解决的问题

**方案**:
```
- 在 consolidator.py 中增加 "经验沉淀" 检测
- 新任务来时先查相似历史解法
- 统计: "已解决 N 次" vs "未解决"
```

#### 3.3 Collective Intelligence 沉淀

**问题**: 经验锁在私有记忆中

**方案**:
```
- 提取高频技能为 "可共享知识"
- 生成知识卡片 (wiki)
- 贡献者: [我] vs [团队]
```

---

### Phase 4: 高级特性 (8-12周)

#### 4.1 多模态支持 (Which)
- 图像记忆 (截图、照片)
- 语音记忆 (会议录音)
- 位置记忆 (GPS 轨迹)

#### 4.2 外部数据源扩展
- 已支持: Hermes / OpenClaw / Honcho
- 计划: GitHub commits, Slack messages, Notion

#### 4.3 可视化增强
- 时间轴播放 (当前已有)
- 记忆流可视化
- AI 洞察面板

---

## 📊 里程碑

```
v0.1 (当前) ─────────────────────────────────────
         │
v0.2 ────┼── 边关系修复 + 遗忘引擎激活
         │
v1.0 ────┼── Metacognitive + 向量检索 + Session 记忆
         │
v1.5 ────┼── 多智能体支持 (去重/对齐/沉淀)
         │
v2.0 ────┴── 多模态 + 外部数据源 + 高级可视化
```

---

## 🔧 技术债务

| 事项 | 原因 |
|------|------|
| 边数为 0 | 关系提取逻辑未完整实现 |
| 遗忘未触发 | 访问追踪未接入 |
| 浅色主题 patch 混乱 | 之前零散修改，需整体重写 |
| 无向量检索 | 优先级排后 |

---

## 📚 参考

- AI Memory Survey: https://mp.weixin.qq.com/s/XybAsd0wJ5o9ya4jlpadDg
- 4W 框架: When (生命周期) / What (类型) / How (存储) / Which (模态)
