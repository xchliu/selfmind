> **⚠️ 过时文档 — HISTORICAL ARCHIVE**
>
> 本文档描述的是 SelfMind **统一数据管道之前的旧架构**（parser / metadata_db / wiki_parser 独立解析、多存储多ID体系）。
> 该架构已于 2026-05 统一数据管道重构中被取代，文中所述的不一致问题大部分已在新架构中解决。
>
> **请参阅以下新架构文档：**
> - `docs/ARCHITECTURE_V2.md` — 统一数据管道架构
> - `docs/MULTI_SOURCE_ARCHITECTURE.md` — 多数据源架构设计
>
> 本文档仅作历史参考保留，不应作为当前实现的依据。
>
> ---归档日期：2026-05-08---

# SelfMind 数据管道完整架构分析

## 一、数据流全景图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        外部数据源 (INPUT SOURCES)                            │
│                                                                             │
│  ~/.hermes/memories/MEMORY.md  ──§分隔──┐                                  │
│  ~/.hermes/memories/USER.md    ──§分隔──┤  记忆文件 (多profile)             │
│  ~/.openclaw/memories/MEMORY.md ──§分隔─┤                                  │
│  Honcho API (remote)           ──JSON──┘                                  │
│                                                                             │
│  ~/.hermes/skills/*/SKILL.md   ──YAML+MD── 技能文件                         │
│                                                                             │
│  ~/Documents/aiworkspace/wiki/ ──MD+YAML── Wiki库                          │
│    (entities|concepts|comparisons|queries|projects)//*.md                   │
│                                                                             │
│  ~/.hermes/state.db           ──SQLite── 会话历史 (analytics用)             │
│                                                                             │
│  /path/to/docs/               ──任意文件── 文档导入源                        │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        解析层 (PARSER LAYER)                                │
│                                                                             │
│  ┌─────────────────── parser.py ──────────────────────┐                    │
│  │ parse_memories():  §分隔 → classify_entry()        │                    │
│  │   → 8主类×24子类 TAXONOMY 关词匹配 + [tag]标签      │                    │
│  │   → stable_id() = "n_" + md5[:8]                   │                    │
│  │   → extract_label() 从KV/加粗/首行提取              │                    │
│  │ collect_skills():  rglob SKILL.md → YAML frontmatter│                    │
│  │   → "sk_" + md5[:8]                                 │                    │
│  │ build_graph():  center→primary→secondary→memory     │                    │
│  │   → + skill_category→skill_subcategory→skill        │                    │
│  │   → + analytics (access_counts, importance, co_occ) │                    │
│  └─────────────────────────────────────────────────────┘                    │
│                                                                             │
│  ┌─────────────────── metadata_db.py ─────────────────┐                    │
│  │ _parse_entries():  §分隔 → TAG_RE [word(/word)?]   │                    │
│  │   → SHA256 content_hash                            │                    │
│  │   → ID = "{src[:3]}_{idx:03d}" 如 "mem_001"        │                    │
│  │ sync_from_memory_files() → SQLite selfmind.db      │                    │
│  │ compute_decay_scores() → 衰减公式                  │                    │
│  └─────────────────────────────────────────────────────┘                    │
│                                                                             │
│  ┌─────────────────── wiki_parser.py ─────────────────┐                    │
│  │ scan_wiki_pages():  rglob .md → YAML frontmatter   │                    │
│  │   → parse_frontmatter() → title,type,tags,sources   │                    │
│  │   → extract_wikilinks() → [[link]] 引用             │                    │
│  │ build_wiki_graph():  wiki_center→page→tag           │                    │
│  │   → "w_" + md5(name)[:8], "wt_" + md5(tag)[:8]     │                    │
│  └─────────────────────────────────────────────────────┘                    │
│                                                                             │
│  ┌─────────────────── analytics.py ───────────────────┐                    │
│  │ analyze_memories():  读取 state.db 会话历史         │                    │
│  │   → access_counts (label→regex→message匹配)         │                    │
│  │   → co_occurrences (session内共现)                  │                    │
│  │   → importance (priority_weight + log(freq))        │                    │
│  └─────────────────────────────────────────────────────┘                    │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        存储层 (STORAGE LAYER)                               │
│                                                                             │
│  data/data.json        ← parser.build_graph() + metadata合并               │
│    格式: {lastUpdated, source, nodes[], links[], analytics}                │
│    node字段: id, label, category, description, primary, secondary,         │
│              group, access_count, importance, createdAt, updatedAt,         │
│              decay_score, status, pinned                                    │
│                                                                             │
│  data/selfmind.db      ← metadata_db.MetadataDB (SQLite)                   │
│    表: memory_meta (id, content_hash, source, category, subcategory,       │
│         created_at, last_accessed, access_count, importance,               │
│         decay_score, status, pinned, content_preview)                      │
│    表: operations_log, snapshots                                            │
│                                                                             │
│  data/wiki_data.json   ← wiki_parser.build_wiki_graph()                    │
│    格式: {lastUpdated, source, nodes[], links[]}                            │
│    node字段: id, label, category, description, primary, secondary,         │
│              group, tags, created, updated                                  │
│                                                                             │
│  memories_store.json   ← memory_store.MemoryStore (JSON)                   │
│    格式: {entries[], meta}                                                  │
│    entry字段: id(mem_uuid), text, label, primary, secondary,               │
│               description, source_file, status, createdAt, updatedAt,      │
│               syncedTo                                                     │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        分析引擎层 (ENGINE LAYER)                            │
│                                                                             │
│  ┌── analyzer.py ────────────────────────────────────┐                     │
│  │ 输入: data/data.json (nodes/links格式)             │                     │
│  │ 也支持旧格式 data.json (memories[]列表格式)        │                     │
│  │ 功能:                                              │                     │
│  │   load_graph_data → get_nodes_as_memories()        │                     │
│  │     filter category=="memory" only                 │                     │
│  │     map: id→id, label→label, description→content   │                     │
│  │     primary→primary, secondary→secondary           │                     │
│  │     createdAt→created_at, updatedAt→updated_at     │                     │
│  │   analyze_importance_from_graph() → 重要性分布     │                     │
│  │   extract_insights_from_graph() → 孤立/枢纽/均衡  │                     │
│  │   analyze_patterns() → 时间/标签/内容模式          │                     │
│  │     (使用旧memories[]格式, 期望tags,category字段)  │                     │
│  │   update_knowledge_graph() → 构建nodes+edges       │                     │
│  │     ID: "tag_{tag}", "cat_{category}"              │                     │
│  └─────────────────────────────────────────────────────┘                     │
│                                                                             │
│  ┌── forgetter.py ───────────────────────────────────┐                     │
│  │ 输入: data/data.json (nodes/links格式)             │                     │
│  │ 也支持旧格式 data.json (memories[]列表格式)        │                     │
│  │ 功能:                                              │                     │
│  │   load_graph_data → get_nodes_as_memories()        │                     │
│  │     filter category=="memory" only                 │                     │
│  │     map: id→id, label→title, description→content   │                     │
│  │     createdAt→created_at, updatedAt→updated_at     │                     │
│  │     access_count→interactions                      │                     │
│  │   analyze_forget_from_graph() → 遗忘候选列表      │                     │
│  │   calculate_forget_score() → 综合遗忘分数         │                     │
│  │     = time_decay*0.4 + access_decay*0.3            │                     │
│  │       + importance_factor*0.2*privacy_factor       │                     │
│  │   run_forgetting() → 软删除(forgotten)或硬删除     │                     │
│  └─────────────────────────────────────────────────────┘                     │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        API + 前端消费层 (CONSUMER LAYER)                    │
│                                                                             │
│  server.py → http_handler.py → Mixins                                       │
│                                                                             │
│  API端点 → 前端文件:                                                        │
│  /api/data          → graph.js  loadData()         [记忆图谱页面]          │
│  /api/wiki/data     → wiki.js   loadWikiData()     [Wiki图谱页面]          │
│  /api/wiki/pages    → wiki.js   loadWikiPages()    [Wiki库列表页面]        │
│  /api/memories      → views.js  loadMemories()     [记忆管理面板]          │
│  /api/meta/entries  → views.js                     [元数据管理面板]        │
│  /api/meta/health   → views.js                     [健康度面板]            │
│  /api/forget/analyze→ views.js                     [遗忘引擎面板]          │
│  /api/analyze/*     → views.js                     [分析引擎面板]          │
│  /api/v1/status     → graph.js  loadSourceStatus() [数据源状态面板]        │
│  /api/v1/changes    → views.js                     [变更追踪面板]          │
│  /api/consolidate/* → views.js                     [整合引擎面板]          │
│  /api/iq            → graph.js                     [IQ评分面板]            │
│  /api/skills        → graph.js                     [技能库面板]            │
│  /api/documents/*   → views.js                     [文档导入面板]          │
└─────────────────────────────────────────────────────────────────────────────┘


== 数据合并流程 (http_handler.py) ==

  parser.build_graph(config)
      │
      ▼  输出: {nodes[], links[], analytics}
      │
  _apply_node_timestamps()   ← 对比 previous data.json, 继承 createdAt/updatedAt
      │
      ▼
  _merge_metadata()          ← 从 selfmind.db 按 content_preview[:80] 匹配
      │                         注入: decay_score, status, pinned
      │                         匹配策略: exact → fallback by primary/secondary
      ▼
  写入 data/data.json


== metadata_db 同步流程 (server.py 启动时) ==

  MEMORY.md / USER.md
      │
      ▼  §分隔 + TAG_RE标签解析
      │
  metadata_db.sync_from_memory_files()
      │  SHA256哈希 → content_hash
      │  ID = "{source[:3]}_{idx:03d}"
      ▼
  写入 data/selfmind.db
      │
  metadata_db.compute_decay_scores()
      ▼
  更新 decay_score 字段