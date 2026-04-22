# SelfMind 多源记忆聚合架构

> 支持多来源记忆的统一聚合与可视化

## 一、架构总览

```
┌─────────────────────────────────────────────────────┐
│                   SelfMind                         │
│              (记忆变化聚合平台)                      │
├─────────────────────────────────────────────────────┤
│                                                     │
│   ┌─────────────┐          ┌─────────────┐        │
│   │  本地文件    │          │  远程 Provider│        │
│   ├─────────────┤          ├─────────────┤        │
│   │ MEMORY.md   │          │   Honcho    │        │
│   │ USER.md     │          │   Mem0      │        │
│   │ (Hermes)   │          │ Hindsight   │        │
│   └──────┬──────┘          └──────┬──────┘        │
│          │                        │                │
│          ▼                        ▼                │
│   ┌──────────────────────────────────────────┐     │
│   │         Provider Adapter Layer          │     │
│   │  ┌─────────┐ ┌─────────┐ ┌─────────┐   │     │
│   │  │  File   │ │ Honcho  │ │  Mem0   │   │     │
│   │  │ Adapter │ │ Adapter │ │ Adapter │   │     │
│   │  └─────────┘ └─────────┘ └─────────┘   │     │
│   └──────────────────────────────────────────┘     │
│                       │                            │
│                       ▼                            │
│   ┌──────────────────────────────────────────┐     │
│   │        变化聚合引擎 + 可视化              │     │
│   └──────────────────────────────────────────┘     │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## 二、核心组件

### 2.1 数据源层

| 来源 | 类型 | 说明 |
|------|------|------|
| **MEMORY.md** | 本地文件 | Hermes Agent 的长期记忆 |
| **USER.md** | 本地文件 | 用户画像与偏好 |
| **Honcho** | 远程服务 | 用户/Agent 记忆层 |
| **Mem0** | 远程服务 | 商业记忆 API |
| **Hindsight** | 远程服务 | 记忆追踪服务 |

### 2.2 Provider Adapter Layer

每个数据源对应一个 Adapter，实现统一接口：

```python
class MemoryProvider(ABC):
    @abstractmethod
    def fetch_memories(self, since: datetime = None) -> List[MemoryItem]:
        """获取记忆列表，可选时间范围"""
        
    @abstractmethod
    def get_changes(self, since: datetime) -> List[MemoryChange]:
        """获取增量变化"""
        
    @abstractmethod
    def get_metadata(self) -> ProviderMetadata:
        """获取 Provider 元信息（名称、版本、记录数）"""
```

#### File Adapter

- 监听 MEMORY.md / USER.md 变化
- 使用 content_hash 检测变更
- 解析 Markdown 结构为 MemoryItem

#### Honcho Adapter

- 调用 Honcho API 获取记忆
- 支持时间范围过滤
- 处理 Honcho 特有的记忆结构

#### Mem0 Adapter

- 调用 Mem0 API (OpenAI 兼容)
- 处理用户/Agent 两种记忆类型
- 支持语义搜索

### 2.3 变化聚合引擎

**核心职责**：将多源记忆的变化聚合并统一展示

```python
class AggregationEngine:
    def aggregate_changes(self, providers: List[MemoryProvider]) -> AggregatedChanges:
        """
        1. 并行拉取各 Provider 增量
        2. 统一格式转换
        3. 时间排序
        4. 去重（基于 content_hash）
        5. 冲突检测
        """
        
    def detect_conflicts(self, changes: List[MemoryChange]) -> List[Conflict]:
        """检测跨源冲突"""
        
    def merge_strategy(self, conflicts: List[Conflict]) -> MergeDecision:
        """冲突解决策略：时间戳优先 / 来源权重 / 人工确认"""
```

## 三、数据模型

### 3.1 统一记忆项

```python
@dataclass
class MemoryItem:
    id: str                           # 全局唯一 ID
    source: str                       # 来源: file/hermes/honcho/mem0
    source_id: str                    # 原始来源的 ID
    content: str                      # 记忆内容
    content_hash: str                 # 内容哈希（去重用）
    created_at: datetime              # 创建时间
    updated_at: datetime              # 更新时间
    accessed_at: datetime             # 最后访问时间
    access_count: int                 # 访问次数
    importance: float                 # 重要性 0-1
    category: str                     # 分类
    tags: List[str]                   # 标签
    metadata: Dict[str, Any]          # 来源特定的额外信息
```

### 3.2 变化事件

```python
@dataclass
class MemoryChange:
    change_id: str
    item_id: str
    source: str
    change_type: str                  # created/updated/deleted
    before: Optional[MemoryItem]
    after: Optional[MemoryItem]
    timestamp: datetime
```

## 四、融合策略

### 4.1 多源冲突解决

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| **时间戳优先** | 以最新更新时间为准 | 内容更新类冲突 |
| **来源权重** | 预设来源优先级 (Honcho > Mem0 > File) | 优先级明确的场景 |
| **内容长度** | 保留内容更丰富的版本 | 信息量差异 |
| **人工确认** | 弹窗让用户选择 | 重要决策 |

### 4.2 去重规则

- 完全相同 `content_hash` → 保留最新
- 语义相似 > 0.9 → 触发合并流程
- 同一 `source_id` 不同来源 → 标记为冲突

## 五、与现有架构的关系

```
┌─────────────────────────────────────────────────────────┐
│                      SelfMind 完整架构                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────┐      ┌─────────────────────────┐  │
│  │  多源聚合层      │ ←──→ │  巩固/遗忘引擎 (V2)     │  │
│  │ (本文档)        │      │  (Consolidator/Forgetter)│  │
│  └────────┬────────┘      └─────────────────────────┘  │
│           │                                                │
│           ▼                                                │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              变化聚合引擎 + 可视化                   │ │
│  └─────────────────────────────────────────────────────┘ │
│                      │                                    │
│                      ▼                                    │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              API 层 + 前端 UI                        │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**多源聚合层**位于：
- **上游**：对接各 Provider 的原始数据
- **下游**：为巩固/遗忘引擎提供统一的记忆输入
- **同级**：与可视化模块直接交互，展示聚合结果

## 六、API 设计

### 6.1 获取聚合变化

```
GET /api/v1/changes?since=2025-04-01T00:00:00Z

Response:
{
  "changes": [
    {
      "change_id": "ch_001",
      "item_id": "mem_123",
      "source": "honcho",
      "change_type": "updated",
      "timestamp": "2025-04-22T10:30:00Z",
      "diff": {...}
    }
  ],
  "providers": [
    {"name": "hermes", "status": "connected", "item_count": 180},
    {"name": "honcho", "status": "connected", "item_count": 45}
  ]
}
```

### 6.2 触发同步

```
POST /api/v1/sync

Body:
{
  "providers": ["hermes", "honcho"],  // 指定来源，不指定则全部
  "force": false                       // 是否强制全量同步
}
```

### 6.3 冲突解决

```
POST /api/v1/resolve

Body:
{
  "conflict_id": "cf_001",
  "decision": "keep_latest",  // keep_latest / keep_source / manual
  "selected_item_id": "mem_456"  // manual 时必填
}
```

## 七、实施计划

### Phase 1: 基础架构（1 周）
- [x] 定义统一 MemoryItem 数据模型
- [x] 实现 File Adapter（读取 MEMORY.md/USER.md）
- [x] 基础聚合引擎（拉取 + 简单去重）
- [x] API 端点：/changes
- [x] 实现 Honcho Adapter
- [x] 实现 Mem0 Adapter（可选）
- [ ] 并行拉取优化
- [ ] Provider 状态监控

### Phase 2: 多 Provider 支持（1 周）
- [ ] 实现 Honcho Adapter
- [ ] 实现 Mem0 Adapter（可选）
- [ ] 并行拉取优化
- [ ] Provider 状态监控

### Phase 3: 冲突处理（1 周）
- [ ] 冲突检测逻辑
- [ ] 多种解决策略
- [ ] 人工确认流程
- [ ] /resolve API

### Phase 4: 可视化增强（1 周）
- [ ] 多源切换 UI
- [ ] 变化流展示
- [ ] 冲突标记
- [ ] 来源筛选

---

## 八、配置示例

```yaml
# config/providers.yaml
providers:
  hermes:
    type: file
    enabled: true
    paths:
      - ~/.hermes/memories/MEMORY.md
      - ~/.hermes/memories/USER.md
    
  honcho:
    type: api
    enabled: true
    endpoint: "http://localhost:8000"
    api_key: "${HONCHO_API_KEY}"
    
  mem0:
    type: api
    enabled: false
    endpoint: "https://api.mem0.ai/v1"
    user_id: "${MEM0_USER_ID}"

aggregation:
  conflict_strategy: "timestamp"  # timestamp / source_priority / manual
  source_priority:
    - honcho
    - mem0
    - hermes
  dedup_threshold: 0.9
```

---

## 九、注意事项

1. **增量 vs 全量**：首次同步全量，之后增量拉取
2. **频率控制**：避免频繁调用远程 API，增加缓存层
3. **错误隔离**：单个 Provider 失败不影响整体
4. **隐私**：远程 Provider 的数据不持久化到本地文件
5. **可扩展性**：新增 Provider 只需实现 Adapter 接口
