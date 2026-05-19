# SelfMind Auto-Fetch 技术设计

## 战略定位

SelfMind = AI的大脑。三层架构：
- **感知层**：客观事实（可拉取、可共享、可压缩）
- **认知层**：理论推断（可推导、可质疑、标注置信度）
- **意识层**：个人理解（标注agent视角，跨agent可读但知主观）

auto-fetch是**感知层**的第一个模块——自动扫描用户本地数据痕迹，快速构建记忆骨架，解决冷启动问题。

## 设计原则

1. **全盘扫描，不逐个对接** — 扫描用户本地已有的数据痕迹，不需要OAuth
2. **中国用户优先** — 微信/企微/钉钉/飞书比Gmail/Notion重要
3. **增量机制** — 首次全盘扫描，后续只拉变化
4. **零第三方依赖** — DocumentImporter模式，只用Python stdlib
5. **LLM提取** — 不是存原始文本，而是调LLM提取结构化记忆条目

## 分层实现路线

### 第一层：文档扫描接入（最快落地，1-2天）

复用已有的DocumentImporter模块，接入unified_sync循环。

**数据流：**
```
~/Documents/ 目录扫描
  → DocumentImporter.scan_directory() 发现 .txt/.md 文件
  → 增量检查：与scan_state表对比，只处理新增/修改文件
  → DocumentImporter.extract_memories() 调LLM提取结构化条目
  → 写入entries表 (type=document, source=文件路径)
```

**改动点：**
1. unified_store.py — 新增 scan_state 表（记录已扫描文件的content_hash和modified时间）
2. unified_sync.py — 新增 sync_documents() 函数，调用DocumentImporter
3. server.py — periodic_sync循环中加入document扫描步骤
4. config.py — 新增 documents 配置块（扫描目录列表、LLM配置）

**scan_state表设计：**
```sql
CREATE TABLE IF NOT EXISTS scan_state (
    source TEXT PRIMARY KEY,           -- 文件路径
    content_hash TEXT NOT NULL,        -- SHA256 of file content
    scan_time TEXT NOT NULL,           -- 最后扫描时间
    status TEXT DEFAULT 'done',        -- done/skipped/error
    entries_extracted INTEGER DEFAULT 0 -- 提取的记忆条目数
);
```

**配置示例：**
```json
{
  "documents": {
    "scan_dirs": [
      "~/Documents/aiworkspace/",
      "~/Documents/selfmind/docs/"
    ],
    "extensions": ["txt", "md"],
    "max_file_size": 500000,
    "interval": 3600
  },
  "llm": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "",
    "model": "gpt-4o-mini",
    "max_tokens": 4096
  }
}
```

### 第二层：本地数据痕迹扫描（3-5天）

新增独立Scanner类，每种数据类型一个。

**Scanner基类设计：**
```python
class DataScanner(ABC):
    """感知层扫描器基类 — 扫描本地数据痕迹，提取客观事实"""

    @abstractmethod
    def scan(self, since: datetime = None) -> list[ScanResult]:
        """扫描数据痕迹，返回结构化事实条目"""

    @abstractmethod
    def source_name(self) -> str:
        """数据源名称，如 'git_activity'"""

@dataclass
class ScanResult:
    """感知层事实条目 — 客观、可验证、可共享"""
    content: str            # 事实内容（简洁描述）
    label: str              # 短标签
    primary: str            # TAXONOMY一级分类
    secondary: str          # TAXONOMY二级分类
    source: str             # 数据来源路径/命令
    source_type: str        # git/calendar/chat/document
    timestamp: datetime     # 事实发现时间
    confidence: float = 1.0 # 感知层事实confidence=1.0
```

**GitActivityScanner：**
- 扫描~/Documents/aiworkspace/下所有git仓库
- git log提取最近7天的提交（作者=当前用户）
- 提取：项目名、活跃频率、最近提交内容概要
- 分类：working/active + spatial/filesystem

**CalendarScanner：**
- 扫描本地ics文件（macOS Calendar导出）
- 提取：会议主题、参与者、时间、频率
- 分类：working/active + social/key_people

**ChatExportScanner（中国用户核心）：**
- 扫描微信/企微/钉钉导出的txt文件
- 微信导出格式：Chat>XXX.txt（时间戳+发送者+内容）
- 提取：联系人、沟通频率、关键话题、重要约定
- 分类：social/key_people + episodic/milestone

### 第三层：平台对接（远期，待前两层验证后）

- 企微API（需要OAuth + 企业管理员授权）
- 钉钉API（需要OAuth）
- 飞书API（需要OAuth）
- 这一步复杂度高，等前两层跑通证明价值后再做

## 统一接入架构

所有Scanner通过auto_fetch_coordinator统一调度：

```python
class AutoFetchCoordinator:
    """感知层自动扫描协调器"""

    def __init__(self, store: UnifiedStore, config: dict):
        self.store = store
        self.scanners: list[DataScanner] = []
        self._register_scanners(config)

    def _register_scanners(self, config: dict):
        """根据配置注册启用的Scanner"""
        if config.get("documents", {}).get("enabled"):
            self.scanners.append(DocumentScanner(config))
        if config.get("git", {}).get("enabled"):
            self.scanners.append(GitActivityScanner(config))
        if config.get("calendar", {}).get("enabled"):
            self.scanners.append(CalendarScanner(config))
        if config.get("chat", {}).get("enabled"):
            self.scanners.append(ChatExportScanner(config))

    def run_scan(self) -> dict:
        """执行全量/增量扫描，写入感知层"""
        stats = {"total_scanned": 0, "total_extracted": 0, "by_source": {}}
        for scanner in self.scanners:
            since = self._get_last_scan_time(scanner.source_name())
            results = scanner.scan(since=since)
            for result in results:
                self._write_perception_entry(result)
                stats["total_extracted"] += 1
            stats["by_source"][scanner.source_name()] = len(results)
            stats["total_scanned"] += 1
            self._update_scan_state(scanner.source_name())
        return stats

    def _write_perception_entry(self, result: ScanResult):
        """写入感知层事实到entries表"""
        entry_id = f"perception:{result.source_type}:{sha256(result.content.encode())[:8]}"
        self.store.upsert_entry({
            "id": entry_id,
            "content": result.content,
            "content_preview": result.content[:120],
            "type": f"perception_{result.source_type}",
            "source": result.source,
            "primary_cat": result.primary,
            "secondary_cat": result.secondary,
            "label": result.label,
            "confidence": result.confidence,  # 感知层=1.0
            "status": "active",
        })
```

**server.py接入：**
```python
# 在periodic_sync循环中加auto-fetch步骤
def periodic_sync():
    while True:
        time.sleep(300)
        # Step 1: Resync existing sources (memory/wiki/honcho/skills)
        unified_sync(store, config)
        # Step 2: Auto-fetch perception layer (NEW)
        if coordinator:
            fetch_stats = coordinator.run_scan()
            print(f"[Auto-fetch] {fetch_stats}")
        # Step 3: Recall scan
        recall_scanner.scan()
        # Step 4: Decay + graph rebuild
        store.compute_decay_scores()
        build_graph_from_store(store, config)
```

## API端点设计

```
GET  /api/auto-fetch/status     — 查看扫描状态和各源统计
POST /api/auto-fetch/trigger    — 手动触发全盘扫描
GET  /api/auto-fetch/sources    — 查看已配置的数据源列表
POST /api/auto-fetch/config     — 动态添加/修改数据源配置
```

## 增量机制

1. scan_state表记录每个源的最近扫描时间
2. 文件类：对比content_hash，只处理新增/修改的文件
3. git类：git log --since=上次扫描时间
4. 日历类：只拉since之后的事件
5. 聊天类：按时间戳过滤，只处理新消息

## 感知层 vs 认知层 vs 意识层的entries区分

| 字段 | 感知层 | 认知层 | 意识层 |
|------|--------|--------|--------|
| type | perception_* | inference_* | understanding_* |
| confidence | 1.0 | 0.5-0.9 | 0.3-0.8 |
| observer | null | null | agent_id |
| source | 数据路径 | 推理引擎 | agent对话 |

现有entries（memory/wiki/honcho_obs/honcho_conc/skill）保持不变，
感知层新增类型：perception_document / perception_git / perception_calendar / perception_chat

## 实现顺序

1. [Day 1] scan_state表 + DocumentScanner接入unified_sync
2. [Day 2] AutoFetchCoordinator + server.py接入 + config扩展
3. [Day 3] GitActivityScanner实现
4. [Day 4] CalendarScanner + ChatExportScanner实现
5. [Day 5] API端点 + 前端展示 + 全量测试