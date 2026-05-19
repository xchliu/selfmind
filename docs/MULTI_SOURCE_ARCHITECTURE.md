# SelfMind 多源记忆聚合架构

> 支持多来源记忆的统一聚合与可视化（基于实际实现）

## 一、架构总览

```
┌──────────────────────────────────────────────────────────┐
│                        SelfMind                           │
│                   (记忆变化聚合平台)                        │
├──────────────────────────────────────────────────────────┤
│                                                           │
│   ┌──────────────────┐  ┌──────────────────┐             │
│   │    本地文件       │  │  远程/外部源      │             │
│   ├──────────────────┤  ├──────────────────┤             │
│   │ MEMORY.md        │  │   Honcho         │             │
│   │ USER.md          │  │  (PostgreSQL +   │             │
│   │ Wiki pages       │  │   REST fallback) │             │
│   │ Skills 目录      │  └──────────────────┘             │
│   │ Recall Capture   │                                   │
│   └─────────┬────────┘                                   │
│             │                                             │
│             ▼                                             │
│   ┌──────────────────────────────────────────────────┐   │
│   │  UnifiedSync (unified_sync.py)                   │   │
│   │  直接调用各源函数，不走 Provider Adapter 层       │   │
│   │  · parse_memory_file() → MEMORY.md/USER.md      │   │
│   │  · scan_wiki_directory()  → Wiki pages          │   │
│   │  · fetch_honcho_documents() → Honcho            │   │
│   │  · _scan_skills()         → Skills              │   │
│   │  · Recall scanner/matcher → Recall Capture      │   │
│   └──────────────────────────────────────────────────┘   │
│             │                                             │
│             ▼                                             │
│   ┌──────────────────────────────────────────────────┐   │
│   │         变化聚合引擎 + 可视化                      │   │
│   └──────────────────────────────────────────────────┘   │
│                                                           │
│   ┌──────────────────────────────────────────────────┐   │
│   │  Provider Adapter Layer (DORMANT SHELL)          │   │
│   │  providers/base.py 定义了 MemoryProvider ABC     │   │
│   │  但 unified_sync.py 不使用此接口                  │   │
│   │  当前为未激活的预留层，不影响实际数据流            │   │
│   └──────────────────────────────────────────────────┘   │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

## 二、核心组件

### 2.1 数据源层

| 来源 | 类型 | 实现状态 | 说明 |
|------|------|----------|------|
| **MEMORY.md / USER.md** | 本地文件 | ✅ 已实现 | Hermes Agent 的长期记忆，通过 `parse_memory_file()` 解析 §-delimited 条目，支持 `[category/sub]` 标签 |
| **Wiki pages** | 本地文件 | ✅ 已实现 | `scan_wiki_directory()` 扫描 wiki/ 子目录（entities/concepts/comparisons/queries/projects/summaries/raw），YAML frontmatter + Markdown body |
| **Honcho** | 远程服务 | ✅ 已实现 | 直连 PostgreSQL documents 表（inductive/deductive/contradiction 层级），REST API fallback via `fetch_honcho_documents()` |
| **Skills directory** | 本地文件 | ✅ 已实现 | 扫描 `~/.hermes/skills/` 目录，解析各 skill 的 SKILL.md 文件 |
| **Recall Capture** | 混合 | ✅ 已实现 | `scanner.py` 扫描 Hermes session JSONL 日志，`matcher.py` 做子串关键词匹配，写入 `agent_recall_log` 表，影响衰减公式 |
| ~~Mem0~~ | ~~远程服务~~ | ❌ 未实现 | ~~商业记忆 API~~ — 仅存在于文档，代码中无实现 |
| ~~Hindsight~~ | ~~远程服务~~ | ❌ 未实现 | ~~记忆追踪服务~~ — 仅存在于文档，代码中无实现 |

### 2.2 Provider Adapter Layer（休眠外壳）

> ⚠️ **重要说明**：此层当前为休眠状态（dormant shell）。

`providers/base.py` 定义了 `MemoryProvider` ABC 接口：

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

但 **`unified_sync.py` 并未使用此接口**。实际数据流直接调用各源特定函数：

| 函数 | 来源 | 说明 |
|------|------|------|
| `parse_memory_file()` | MEMORY.md / USER.md | §-delimited 解析，[category/sub] 标签提取 |
| `scan_wiki_directory()` | Wiki pages | 扫描 wiki/ 下 7 个子目录，YAML frontmatter 解析 |
| `fetch_honcho_documents()` | Honcho | PostgreSQL 直连优先，REST API fallback |
| `_scan_skills()` | Skills | 扫描 ~/.hermes/skills/ 下 SKILL.md |
| Recall scanner/matcher | Recall Capture | JSONL 日志扫描 → 子串匹配 → agent_recall_log 表 |

Provider 层是架构上的预留接口，未来若需统一适配可激活，但当前所有数据流绕过此层。

### 2.3 UnifiedSync — 实际编排器

**核心职责**：编排所有数据源，支持可配置的启用/禁用开关。

```python
class UnifiedSync:
    """
    unified_sync.py 中的核心类
    
    每个数据源有独立的 enabled/disabled 标志：
    - memory_enabled: 控制 MEMORY.md/USER.md 同步
    - wiki_enabled:   控制 Wiki 页面扫描
    - honcho_enabled: 控制 Honcho 数据拉取
    - skills_enabled: 控制 Skills 目录扫描
    - recall_enabled: 控制 Recall Capture
    
    同步流程：
    1. 检查各源 enabled 标志
    2. 直接调用对应函数（不走 Provider Adapter）
    3. 将结果统一写入数据库
    4. 返回同步统计信息
    """
```

#### 手动导入

`_import_memory()` 端点允许导入任意 Markdown 文件，解析并入库。

### 2.4 Recall Capture 详解

Recall Capture 是一个独立的子系统，影响记忆衰减：

- **scanner.py**：扫描 Hermes session JSONL 日志文件
- **matcher.py**：对日志内容做子串关键词匹配
- 匹配结果写入 `agent_recall_log` 表
- 被访问的记忆条目影响衰减公式计算（近期被引用的记忆衰减更慢）

## 三、数据模型

### 3.1 统一记忆项

```python
@dataclass
class MemoryItem:
    id: str                           # 全局唯一 ID
    source: str                       # 来源: memory/user/wiki/honcho/skills/recall
    source_id: str                    # 原始来源的 ID
    content: str                      # 记忆内容
    content_hash: str                 # 内容哈希（去重用）
    created_at: datetime              # 创建时间
    updated_at: datetime              # 更新时间
    accessed_at: datetime             # 最后访问时间
    access_count: int                 # 访问次数
    importance: float                 # 重要性 0-1
    category: str                     # 分类
    tags: List[str]                   # 标签（如 [category/sub] 格式）
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
| **来源权重** | 预设来源优先级 (Honcho > Memory.md > Wiki) | 优先级明确的场景 |
| **内容长度** | 保留内容更丰富的版本 | 信息量差异 |
| **人工确认** | 弹窗让用户选择 | 重要决策 |

> 注：Mem0 和 Hindsight 不在来源权重中，因为它们未被实现。

### 4.2 去重规则

- 完全相同 `content_hash` → 保留最新
- 语义相似 > 0.9 → 触发合并流程
- 同一 `source_id` 不同来源 → 标记为冲突

## 五、与现有架构的关系

```
┌──────────────────────────────────────────────────────────┐
│                    SelfMind 完整架构                       │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────┐      ┌─────────────────────────┐   │
│  │  多源聚合层      │ ←──→ │  巩固/遗忘引擎 (V2)     │   │
│  │ (本文档)        │      │  (Consolidator/Forgetter)│   │
│  └────────┬────────┘      └─────────────────────────┘   │
│           │                                                │
│           ▼                                                │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              变化聚合引擎 + 可视化                   │  │
│  └─────────────────────────────────────────────────────┘  │
│                      │                                     │
│                      ▼                                     │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              API 层 + 前端 UI                        │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Recall Capture → agent_recall_log → 衰减公式      │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

**多源聚合层**位于：
- **上游**：对接各数据源的原始数据（Memory/Wiki/Honcho/Skills/Recall）
- **下游**：为巩固/遗忘引擎提供统一的记忆输入
- **同级**：与可视化模块直接交互，展示聚合结果
- **旁路**：Recall Capture 通过 agent_recall_log 影响衰减公式

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
    {"name": "memory", "status": "connected", "item_count": 180},
    {"name": "wiki", "status": "connected", "item_count": 42},
    {"name": "honcho", "status": "connected", "item_count": 45},
    {"name": "skills", "status": "connected", "item_count": 8},
    {"name": "recall", "status": "connected", "item_count": 15}
  ]
}
```

### 6.2 触发同步

```
POST /api/v1/sync

Body:
{
  "sources": ["memory", "wiki", "honcho", "skills", "recall"],  // 指定来源，不指定则全部
  "force": false                       // 是否强制全量同步
}
```

### 6.3 手动导入

```
POST /api/v1/import_memory

Body:
{
  "file_path": "/path/to/arbitrary.md",  // 任意 Markdown 文件路径
  "source_label": "custom_import"         // 来源标签
}
```

调用 `_import_memory()` 端点，解析任意 md 文件并入库。

### 6.4 冲突解决

```
POST /api/v1/resolve

Body:
{
  "conflict_id": "cf_001",
  "decision": "keep_latest",  // keep_latest / keep_source / manual
  "selected_item_id": "mem_456"  // manual 时必填
}
```

## 七、实施状态

### Phase 1: 基础架构 ✅ 已完成
- [x] 定义统一 MemoryItem 数据模型
- [x] 实现 MEMORY.md/USER.md 解析（parse_memory_file，§-delimited，[category/sub] 标签）
- [x] 基础聚合引擎（拉取 + 简单去重）
- [x] 实现 Honcho 数据拉取（PostgreSQL 直连 + REST fallback）
- [x] API 端点：/changes

### Phase 2: 扩展数据源 ✅ 已完成
- [x] 实现 Wiki 页面扫描（scan_wiki_directory，7 个子目录）
- [x] 实现 Skills 目录扫描（~/.hermes/skills/ + SKILL.md）
- [x] 实现 Recall Capture（scanner.py + matcher.py + agent_recall_log）
- [x] 各源可配置 enabled/disabled 标志（UnifiedSync）

### Phase 3: Provider Adapter 层 ⏸️ 休眠
- [x] 定义 MemoryProvider ABC 接口（providers/base.py）
- [ ] 实际接入 Provider 接口（当前 unified_sync.py 绕过此层直接调用函数）
- [ ] 此层为 dormant shell，待未来需要统一适配时激活

### Phase 4: 冲突处理 🔲 待实现
- [ ] 冲突检测逻辑
- [ ] 多种解决策略
- [ ] 人工确认流程
- [ ] /resolve API

### Phase 5: 可视化增强 🔲 待实现
- [ ] 多源切换 UI
- [ ] 变化流展示
- [ ] 冲突标记
- [ ] 来源筛选

---

## 八、配置示例

```yaml
# UnifiedSync 配置（unified_sync.py 使用）
sync:
  memory_enabled: true       # MEMORY.md / USER.md
  wiki_enabled: true         # Wiki 页面
  honcho_enabled: true       # Honcho (PostgreSQL + REST)
  skills_enabled: true       # ~/.hermes/skills/ 目录
  recall_enabled: true       # Recall Capture (JSONL 日志扫描)

honcho:
  # PostgreSQL 直连（优先）
  db_host: "localhost"
  db_port: 5432
  db_name: "honcho"
  db_user: "${HONCHO_DB_USER}"
  db_password: "${HONCHO_DB_PASSWORD}"
  # REST API fallback
  endpoint: "http://localhost:8000"
  api_key: "${HONCHO_API_KEY}"

wiki:
  base_path: "./wiki"
  subdirs:
    - entities
    - concepts
    - comparisons
    - queries
    - projects
    - summaries
    - raw

skills:
  base_path: "~/.hermes/skills"
  skill_file: "SKILL.md"

recall:
  log_dir: "~/.hermes/hermes-agent"
  log_pattern: "*.jsonl"
  match_method: "substring"

aggregation:
  conflict_strategy: "timestamp"  # timestamp / source_priority / manual
  source_priority:
    - honcho
    - memory
    - wiki
    - skills
    - recall
  dedup_threshold: 0.9

# Provider Adapter Layer — 当前休眠，以下为预留配置
# providers:
#   (dormant — 不参与实际数据流)
```

---

## 九、注意事项

1. **增量 vs 全量**：首次同步全量，之后增量拉取
2. **频率控制**：避免频繁调用 Honcho API，增加缓存层
3. **错误隔离**：单个数据源失败不影响整体（各源 enabled/disabled 独立控制）
4. **隐私**：Honcho 的数据不持久化到本地文件
5. **可扩展性**：新增数据源只需在 UnifiedSync 中增加对应函数调用和 enabled 标志
6. **Provider 层状态**：Provider Adapter Layer 当前为 dormant shell，不要误以为它参与了数据流；实际路径是 UnifiedSync → 直接函数调用
7. **Recall Capture 影响**：Recall 不仅采集数据，还通过 agent_recall_log 影响记忆衰减公式，近期被引用的记忆衰减更慢