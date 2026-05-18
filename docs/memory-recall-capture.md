# SelfMind 记忆唤起捕获模块 (Memory Recall Capture)

## 核心思想

记忆衰减应该反映 **agent的真实推理行为**，而不是SelfMind自身的操作。
SelfMind只是展示层——它需要知道哪些记忆在agent推理中被"唤起"了。

## 数据流

```
Hermes推理 → session日志(.jsonl) → RecallScanner扫描 → 匹配SelfMind entries → 记录recall → 更新衰减
```

解耦设计：SelfMind被动监听，不侵入Hermes。

## 模块架构

```
selfmind_app/recall_capture/
├── __init__.py          # 导出RecallScanner, HermesAdapter
├── adapter.py           # AgentAdapter抽象基类 + HermesAdapter实现
├── matcher.py           # 三层匹配策略 (hash → keyword → semantic)
├── scanner.py           # RecallScanner主引擎 (扫描 + 匹配 + 记录)
```

### AgentAdapter抽象层

```python
class AgentAdapter(abc.ABC):
    @abc.abstractmethod
    def scan_recent_activity(self, since_timestamp) -> list[RecallEvent]
    
    @abc.abstractmethod
    def get_agent_id(self) -> str
```

- HermesAdapter: 读 `~/.hermes/sessions/*.jsonl`，解析assistant turn
- 未来扩展: ClaudeAdapter, GPTAdapter, 自定义AgentAdapter

### 三层匹配策略

| 层级 | 方法 | 准确度 | 速度 |
|------|------|--------|------|
| 1 | content_hash精确匹配 | 1.0 | 最快 |
| 2 | 关键词模糊匹配 | 0.3-0.8 | 中等 |
| 3 | 语义向量匹配 | 0.5-0.9 | 最慢(TODO) |

关键词匹配流程:
- 从SelfMind entries的content_preview提取关键词 → 建倒排索引
- 从session snippet提取关键词 → 查倒排索引
- 匹配2+关键词 或 单关键词高置信 → 认为命中

### RecallScanner流程

```
1. 各adapter扫描since_timestamp后的agent活动
2. 加载SelfMind entries构建matcher
3. 匹配events到entries
4. 记录recall到agent_recall_log表
5. 更新衰减分数 (recall影响recency)
6. 保存扫描时间戳
```

## 数据库

### agent_recall_log表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| entry_id | TEXT FK | 对应SelfMind entry |
| agent_id | TEXT | agent标识 (hermes, aris...) |
| timestamp | TEXT | 呶起时间 |
| source | TEXT | 检测方式 (session_log) |
| confidence | REAL | 匹配置信度 (0-1) |
| context_snippet | TEXT | 触发上下文片段 |
| match_method | TEXT | hash/keyword/semantic |

### 衰减公式 (改用recall数据)

```
# 有recall记录的entry:
days_since_recall = (now - last_recall_timestamp) / 86400
recall_recency = exp(-0.05 × days_since_recall)    # 衰减慢，5%每天
recall_freq = min(1.0, 0.3 + 0.1 × recall_count)   # 多次唤起更强
decay = importance × (0.3 + 0.5 × recall_freq × recall_recency + 0.3 × type_factor)

# 无recall记录的entry (回落到传统衰减):
days = (now - updated_at) / 86400
recency = exp(-0.03 × days)                          # 衰减快，3%每天
freq = 0.3                                           # 低基线
decay = importance × (0.3 + 0.4 × freq × recency + 0.3 × type_factor)
```

关键差异:
- **有recall**: 衰减系数0.05/天(慢)，权重0.5(高)，频率随唤起次数提升
- **无recall**: 衰减系数0.03/天(快)，权重0.4(低)，频率固定0.3
- 被唤起的记忆衰减回升，多次唤起持续强化

## API端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/recall/stats` | GET | 获取recall统计 (总数/按agent/最后扫描时间) |
| `/api/recall/scan` | GET | 手动触发一次recall扫描 |
| `/api/meta/entries/{id}/recall-history` | GET | 查某个entry的recall历史 |

## 自动扫描

server.py后台线程，每5分钟执行:
1. unified_sync (数据同步)
2. recall_scanner.scan() (唤起扫描)
3. store.compute_decay_scores() (衰减重算)
4. build_graph_from_store (图谱重建)

## 未来扩展

- **语义向量匹配**: 用embedding做相似度检索，替代关键词匹配
- **小亚Adapter**: ArisAdapter读取小亚的session日志
- **Honcho直接对接**: Honcho注入上下文时主动通知SelfMind
- **recall可视化**: 前端展示每条记忆的唤起历史和衰减起伏曲线