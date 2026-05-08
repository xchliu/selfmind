> **⚠️ 过时文档 — HISTORICAL ARCHIVE**
>
> 本文档描述的是 SelfMind **统一数据管道之前的旧架构中的字段不一致问题**（parser / metadata_db / wiki_parser 独立解析、多ID体系、多分类体系、字段名映射不一致等）。
> 这些不一致问题已在 2026-05 统一数据管道重构中大幅解决。
>
> **请参阅以下新架构文档：**
> - `docs/ARCHITECTURE_V2.md` — 统一数据管道架构
> - `docs/MULTI_SOURCE_ARCHITECTURE.md` — 多数据源架构设计
>
> 本文档仅作历史参考保留，不应作为当前实现的依据。文中记录的不一致编号(#1–#16)可能已不再适用。
>
> ---归档日期：2026-05-08---

# SelfMind 字段对比表与不一致清单

## 二、字段对比表 (parser vs metadata_db vs wiki_parser vs analyzer vs forgetter)

### 2.1 ID格式对比

| 模块 | ID前缀 | 生成算法 | 示例 | 范围 |
|------|--------|----------|------|------|
| **parser.py (memory)** | `n_` | md5(section_text)[:8] | n_a1b2c3d4 | 记忆节点 |
| **parser.py (primary)** | `p_` | 硬编码 p_{primary_key} | p_social | 一级分类 |
| **parser.py (secondary)** | `s_` | 硬编码 s_{pk}_{sk} | s_social_key_people | 二级分类 |
| **parser.py (skill_category)** | `sc_` | md5(category)[:8] | sc_e5f6g7h8 | 技能分类 |
| **parser.py (skill_subcategory)** | `ss_` | md5(cat/subcat)[:8] | ss_i9j0k1l2 | 技能子分类 |
| **parser.py (skill)** | `sk_` | md5(skill_name)[:8] | sk_m3n4o5p6 | 技能 |
| **parser.py (center)** | 由config定义 | config.center_node.id | self | 中心节点 |
| **metadata_db.py** | `{src[:3]}_` | 自增序号 {idx:03d} | mem_001, usr_002 | 全部条目 |
| **wiki_parser.py (page)** | `w_` | md5(page_name)[:8] | w_q7r8s9t0 | Wiki页面 |
| **wiki_parser.py (tag)** | `wt_` | md5(tag_text)[:8] | wt_u1v2w3x4 | Wiki标签 |
| **wiki_parser.py (center)** | `wiki_center` | 硬编码 | wiki_center | 中心节点 |
| **memory_store.py** | `mem_` | uuid4().hex[:8] | mem_a1b2c3d4 | 导入的记忆 |
| **analyzer.py (tag node)** | `tag_` | 硬编码 tag_{tag} | tag_python | 知识图谱标签 |
| **analyzer.py (cat node)** | `cat_` | 硬编码 cat_{category} | cat_note | 知识图谱分类 |

**不一致#1**: parser用md5(content)确定性ID，metadata_db用序号递增ID，memory_store用uuid随机ID。
  同一条记忆在不同系统中ID完全不同，无法直接关联。

**不一致#2**: parser的`n_`前缀 vs memory_store的`mem_`前缀 vs metadata_db的`mem_`前缀(碰巧相同但算法不同)。

### 2.2 分类/Category字段对比

| 模块 | 分类体系 | 字段名 | 分类值 |
|------|----------|--------|--------|
| **parser.py** | 8主类×24子类 TAXONOMY | primary, secondary | autobiographical/identity, social/key_people 等 |
| **metadata_db.py** | 从文本TAG_RE提取 | category, subcategory | TAG标签值如 social/key_people 或 identity(无/secondary) |
| **wiki_parser.py** | YAML type字段 + 目录映射 | type (→category) | entity, concept, comparison, query, summary, wiki_tag, wiki_center |
| **analyzer.py** | 独立分类体系 | category | insight, goal, note, relationship, log, project, question |
| **forgetter.py** | 独立分类体系 | category (复用analyzer) | insight, goal, note, relationship, log |
| **config.py categories** | 旧版9类配置 | category | identity, person, project, principle, tool, environment, memory, skill, skill_category |
| **memory_store.py** | 复用parser分类 | primary, secondary | working/active(默认), 继承parser分类 |

**不一致#3**: parser使用认知心理学8类体系(autobiographical等), config.py保留旧版9类体系(identity等),
  analyzer/forgetter使用完全不同的7类体系(insight, goal, note等)。三套分类互不兼容!

**不一致#4**: parser字段叫 primary/secondary, metadata_db字段叫 category/subcategory,
  wiki_parser字段叫 type, analyzer/forgetter字段叫 category。同一个概念用4个不同字段名。

**不一致#5**: metadata_db的TAG_RE解析 `\[(\w+)(?:/(\w+))?(?:/(\w+))?\]` 可提取3段标签，
  但parser的classify_entry()使用 `\[(\w+)/(\w+)\]` 和 `\[(\w+)/(\w+)/(\w+)\]`。
  解析逻辑相似但不完全相同(metadata_db的TAG_RE更宽松, 不限制第二段必须在TAXONOMY中)。

### 2.3 Node完整字段对比

| 字段 | parser node | metadata_db row | wiki_parser node | analyzer期望 | forgetter期望 |
|------|-------------|-----------------|------------------|-------------|---------------|
| id | ✓ n_xxxx | ✓ src_001 | ✓ w_xxxx | ✓ | ✓ |
| label | ✓ | - | ✓ | - (用title) | - (用title) |
| title | - | - | ✓ | ✓ | ✓ |
| category | ✓ memory/primary/secondary/skill* | ✓ 标签值 | ✓ type值 | ✓ insight/goal/note | ✓ 同analyzer |
| primary | ✓ | - | ✓ (=type) | ✓ | ✓ |
| secondary | ✓ | - | ✓ (=空) | ✓ | ✓ |
| description | ✓ | ✓ content_preview | ✓ | - (用content) | - (用content) |
| content | - | - | ✓ (完整body) | ✓ | ✓ |
| group | ✓ (=category或primary) | - | ✓ (=type) | - | - |
| access_count | ✓ (来自analytics) | ✓ | - | ✓ (用interactions) | ✓ (用interactions) |
| importance | ✓ (来自analytics) | ✓ | - | ✓ | ✓ |
| decay_score | - (注入自metadata_db) | ✓ | - | - | ✓ |
| status | - (注入自metadata_db) | ✓ | - | - | ✓ |
| pinned | - (注入自metadata_db) | ✓ | - | ✓ | ✓ |
| createdAt | ✓ (http_handler注入) | ✓ created_at | ✓ | ✓ created_at | ✓ created_at |
| updatedAt | ✓ (http_handler注入) | ✓ last_accessed | ✓ | ✓ updated_at | ✓ updated_at |
| tags | - | - | ✓ | ✓ | ✓ |
| text | ✓ (原始section) | - | ✓ (完整body) | - | - |
| node_id | ✓ (=id) | - | - | - | - |
| source_profile | ✓ | ✓ source | - | - | - |
| source_file | ✓ | - | ✓ path | - | - |
| content_hash | - | ✓ SHA256 | - | - | - |
| content_preview | - | ✓ [:100] | ✓ [:200] | - | - |

**不一致#6**: analyzer和forgetter将parser输出的字段名做了映射:
  - label → title (forgetter/analyzer)
  - description → content (forgetter/analyzer)
  - access_count → interactions (forgetter)
  - createdAt → created_at (analyzer/forgetter)
  - updatedAt → updated_at (analyzer/forgetter)
  这些映射是隐式的(在get_nodes_as_memories()中), 没有统一规范。

**不一致#7**: metadata_db用SHA256做content_hash, parser用md5[:8]做node_id。
  两者都对文本做哈希但算法和长度完全不同，无法交叉查找。

**不一致#8**: content_preview截断长度不一致:
  metadata_db截取[:100]字符, wiki_parser截取[:200]字符, parser截取description[:150]字符。

**不一致#9**: wiki_parser node有tags字段但parser node没有tags字段。
  parser entry有text字段但wiki_parser page的完整内容在不同字段(content vs content_preview)。

### 2.4 存储格式对比

| 存储 | 格式 | 位置 | 去重逻辑 |
|------|------|------|----------|
| data.json | JSON nodes/links | ~/Documents/selfmind/data/ | parser按label去重 |
| selfmind.db | SQLite 3表 | ~/Documents/selfmind/data/ | metadata_db按SHA256 content_hash去重 |
| wiki_data.json | JSON nodes/links | ~/Documents/selfmind/data/ | wiki_parser按page name去重 |
| memories_store.json | JSON entries | ~/Documents/selfmind/ | memory_store按id(uuid)不去重 |

**不一致#10**: parser去重逻辑用label做key，metadata_db去重逻辑用SHA256(content)做key。
  同一条记忆可能因为label相同而被parser合并，但content_hash不同而metadata_db保留两条。
  反之亦然。

**不一致#11**: data.json中的memory节点ID(n_xxxx)与metadata_db中的条目ID(mem_001)完全不同，
  http_handler._merge_metadata()通过content_preview[:80]的前缀匹配来关联两者，
  这是一个脆弱的匹配方式(前80字符去**后的模糊匹配)。

### 2.5 分隔符与解析逻辑对比

| 模块 | 分隔符 | 标签解析 | 输入处理 |
|------|--------|----------|----------|
| parser.py | § (config.section_separator) | [primary/secondary] 或 [level/primary/secondary] | 多profile遍历 + fallback文件 |
| metadata_db.py | § (硬编码) | [\w+/(\w+)?/(\w+)?] (TAG_RE, 1-3段) | 单文件，无profile概念 |
| wiki_parser.py | YAML frontmatter (---) | frontmatter中的type字段 + [[wikilink]] | 目录扫描，_SCAN_DIRS限定 |

**不一致#12**: metadata_db硬编码§分隔符，而parser从config读取。
  如果用户修改config.json中的section_separator，parser会使用新分隔符，
  但metadata_db仍然按§分割，导致解析结果不一致。

**不一致#13**: metadata_db的TAG_RE只提取标签文本，不验证标签是否在TAXONOMY中；
  parser的classify_entry()严格验证primary_key必须在TAXONOMY中。
  导致metadata_db可能存储"无效"的分类值。

### 2.6 时间字段对比

| 模块 | 创建时间字段 | 更新时间字段 | 格式 |
|------|-------------|-------------|------|
| parser.py | - (无时间) | - (无时间) | - |
| http_handler注入 | createdAt | updatedAt | %Y-%m-%dT%H:%M:%S |
| metadata_db | created_at | last_accessed | %Y-%m-%dT%H:%M:%S |
| wiki_parser | created (from YAML) | updated (from YAML) | YAML自由格式 |
| analyzer | created_at | updated_at | ISO8601 (expect Z suffix) |
| forgetter | created_at | updated_at | ISO8601 (expect Z suffix) |
| memory_store | createdAt | updatedAt | %Y-%m-%dT%H:%M:%S (UTC) |

**不一致#14**: 同一概念的时间字段名不一致:
  createdAt vs created_at vs created vs last_accessed vs updatedAt vs updated_at vs updated

**不一致#15**: 时间格式不一致: http_handler用无Z后缀的本地时间，
  analyzer/forgetter期望Z后缀并用fromisoformat解析，
  memory_store用UTC时间但无Z后缀，
  wiki_parser的时间来自YAML frontmatter，格式不确定。

### 2.7 关系/链接字段对比

| 模块 | 链接类型 | source字段 | target字段 | label字段 |
|------|----------|------------|------------|-----------|
| parser.py | has_memory_type, contains, mentions, co_occurs, related, shares_tag | ✓ | ✓ | ✓ | ✓ |
| wiki_parser.py | contains, references, tagged | ✓ | ✓ | ✓ | ✓ |
| analyzer.py | has_tag, in_category (edges) | source | target | type |

**不一致#16**: parser链接叫label("contains"), analyzer链接叫type("has_tag"),
  字段名不同但语义类似。前端graph.js统一读label字段。

## 三、完整不一致清单 (编号汇总)

| # | 不一致点 | 严重程度 | 说明 |
|---|----------|----------|------|
| 1 | ID生成算法不一致 | **高** | parser用md5[:8]确定性ID, metadata_db用序号递增, memory_store用uuid[:8]随机ID。同一条记忆三个不同ID。 |
| 2 | ID前缀碰撞 | **中** | memory_store的`mem_`前缀与metadata_db的`mem_`前缀(=source[:3])碰巧相同，但后续算法完全不同(uuid vs 序号)。 |
| 3 | 三套分类体系 | **高** | parser(8×24认知心理学), config.py(9类旧版), analyzer/forgetter(7类note/insight/goal)。互不兼容，映射缺失。 |
| 4 | 分类字段名不一致 | **高** | primary/secondary vs category/subcategory vs type vs category。同一概念4个字段名。 |
| 5 | 标签解析逻辑差异 | **中** | metadata_db TAG_RE更宽松(不验证TAXONOMY), parser classify_entry严格验证。导致不同分类结果。 |
| 6 | 字段名映射隐式 | **高** | analyzer/forgetter将parser字段做隐式映射(label→title, description→content, access_count→interactions)。如果parser改字段名，引擎静默失败。 |
| 7 | 哈希算法不一致 | **中** | metadata_db用SHA256全长度, parser用md5[:8]。无法交叉查找。 |
| 8 | 截断长度不一致 | **低** | content_preview截取长度: metadata_db[:100], wiki[:200], parser[:150]。 |
| 9 | tags字段缺失 | **中** | parser memory节点无tags字段, 但analyzer/forgetter期望tags字段做隐私衰减检测。metadata_db也无tags字段。 |
| 10 | 去重逻辑不一致 | **高** | parser按label去重, metadata_db按SHA256(content)去重。可能导致一边合并一边保留。 |
| 11 | 跨存储关联脆弱 | **高** | _merge_metadata()用content_preview[:80]前缀模糊匹配关联parser节点与metadata_db条目。内容变更极易断链。 |
| 12 | 分隔符硬编码不一致 | **中** | metadata_db硬编码§, parser从config读取。修改config分隔符会导致metadata_db解析失败。 |
| 13 | 分类验证不一致 | **中** | metadata_db接受任意标签值, parser只接受TAXONOMY中的值。metadata_db可能存储parser无法识别的分类。 |
| 14 | 时间字段名不一致 | **中** | createdAt vs created_at vs created vs last_accessed(4种命名同一概念)。 |
| 15 | 时间格式不一致 | **中** | 无Z后缀本地时间 vs 期望Z后缀 vs YAML自由格式 vs UTC无Z。analyzer/forgetter的fromisoformat可能解析失败。 |
| 16 | 链接字段名不一致 | **低** | parser链接label vs analyzer链接type。前端统一读label，analyzer的type被忽略。 |

## 四、核心数据流关系图 (简化版)

```
                    ┌──────────────┐
                    │  MEMORY.md   │  (§分隔的记忆文件)
                    │  USER.md     │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
     parser.py       metadata_db.py    analytics.py
     §分隔+TAXONOMY   §分隔+TAG_RE     state.db扫描
     md5[:8] ID       SHA256 hash      regex匹配
              │            │            │
              │            │            │
              ▼            ▼            ▼
     ┌─────────────────────────────────────────┐
     │         http_handler.py 合并             │
     │  parser graph + timestamps + metadata   │
     │  (content_preview[:80]模糊匹配)         │
     └────────────────┬────────────────────────┘
                      │
                      ▼
              ┌───────────────┐
              │  data.json    │  ← 前端 /api/data → graph.js
              │  nodes+links  │
              └───────┬───────┘
                      │
              ┌───────┼───────┐
              │       │       │
              ▼       ▼       ▼
         analyzer  forgetter  wiki_parser
         (读data)  (读data)   (读wiki目录)
              │       │       │
              │       │       ▼
              │       │  ┌──────────────┐
              │       │  │ wiki_data.json│ ← 前端 /api/wiki/data → wiki.js
              │       │  └──────────────┘
              │       │
              ▼       ▼
         /api/analyze/*  /api/forget/*
         → views.js      → views.js


    ┌──────────────┐         ┌──────────────────┐
    │ wiki目录/*.md │ ──────→ │ wiki_parser.py    │
    │ YAML+MD      │         │ w_xxxx ID         │
    └──────────────┘         │ wt_xxxx ID        │
                             └────────┬─────────┘
                                      │
                                      ▼
                             ┌──────────────────┐
                             │ wiki_data.json   │
                             └──────────────────┘

    ┌──────────────┐         ┌──────────────────┐
    │ 文档导入     │ ──────→ │ memory_store.py   │
    │ /api/documents│         │ mem_uuid ID       │
    └──────────────┘         │ memories_store.json│
                             └──────────────────┘
                                    │
                                    │ sync
                                    ▼
                             ┌──────────────────┐
                             │ ~/.hermes/       │
                             │ memories/        │
                             │ MEMORY.md        │ ← 回到parser输入源!闭环
                             └──────────────────┘