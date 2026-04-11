"""SelfMind Parser — Cognitive Psychology-Based Memory Taxonomy

Implements an 8-primary / 24-subcategory memory classification system
inspired by cognitive psychology research on human memory types:

  autobiographical (自传体记忆) — identity, growth, principles
  semantic         (语义记忆)   — domain, technical, methodology
  episodic         (情景记忆)   — success, failure, milestone
  procedural       (程序性记忆) — development, operations, creative, research, communication, tools
  social           (社会认知)   — key_people, relationships, preferences
  working          (工作记忆)   — active, backlog, archived
  spatial          (空间记忆)   — system, filesystem, services
  emotional        (情绪记忆)   — user_mood, likes_dislikes, trust
"""

import re
from datetime import datetime
from hashlib import md5
from pathlib import Path

from selfmind_app.config import get_enabled_profiles

# ────────────────────────────────────────────────────────────────────
# 1. TAXONOMY — 8 primary categories × 24 subcategories
# ────────────────────────────────────────────────────────────────────

TAXONOMY: dict[str, dict] = {
    "autobiographical": {
        "display_name": "自传体记忆",
        "subcategories": {
            "identity": {
                "display_name": "身份认同",
                "keywords": ["我是", "名字", "角色", "身份", "小苏", "苏格拉底", "助手"],
            },
            "growth": {
                "display_name": "成长轨迹",
                "keywords": ["进化", "成长", "升级", "版本", "提升"],
            },
            "principles": {
                "display_name": "行为准则",
                "keywords": ["红线", "安全", "原则", "不回答", "边界", "底线", "不对外"],
            },
        },
    },
    "semantic": {
        "display_name": "语义记忆",
        "subcategories": {
            "domain": {
                "display_name": "行业知识",
                "keywords": ["战略", "规划", "A轮", "融资", "商业", "银行", "行业"],
            },
            "technical": {
                "display_name": "技术概念",
                "keywords": ["架构", "算法", "协议", "技术", "API"],
            },
            "methodology": {
                "display_name": "方法论",
                "keywords": ["方法论", "最佳实践", "框架", "思维"],
            },
        },
    },
    "episodic": {
        "display_name": "情景记忆",
        "subcategories": {
            "success": {
                "display_name": "成功经验",
                "keywords": ["成功", "有效", "解决了"],
            },
            "failure": {
                "display_name": "失败教训",
                "keywords": ["教训", "不要", "避免", "注意", "踩坑", "不耐烦"],
            },
            "milestone": {
                "display_name": "关键事件",
                "keywords": ["里程碑", "转折", "重要"],
            },
        },
    },
    "procedural": {
        "display_name": "程序性记忆",
        "subcategories": {
            "development": {
                "display_name": "开发技能",
                "keywords": ["开发", "编程", "代码", "coding", "development", "programming"],
            },
            "operations": {
                "display_name": "运维技能",
                "keywords": ["部署", "运维", "devops", "docker", "k8s", "运营"],
            },
            "creative": {
                "display_name": "创作技能",
                "keywords": ["创作", "设计", "creative", "写作", "绘画"],
            },
            "research": {
                "display_name": "研究技能",
                "keywords": ["研究", "调研", "research", "论文", "分析"],
            },
            "communication": {
                "display_name": "沟通技能",
                "keywords": ["沟通", "表达", "汇报", "演示", "社交媒体", "email"],
            },
            "tools": {
                "display_name": "工具使用",
                "keywords": [
                    "日历", "Mac", "CLI", "浏览器", "工具", "MCP",
                    "企微", "公众号", "配置", "设置", "启动", "流程",
                ],
            },
        },
    },
    "social": {
        "display_name": "社会认知",
        "subcategories": {
            "key_people": {
                "display_name": "核心人物",
                "keywords": ["坦哥", "晓晨", "和栋", "邹总", "张总", "群成员", "刘小成"],
            },
            "relationships": {
                "display_name": "关系网络",
                "keywords": ["关系", "团队", "组织", "同事", "上级", "下属"],
            },
            "preferences": {
                "display_name": "沟通偏好",
                "keywords": ["风格", "沟通方式", "习惯", "语气", "称呼"],
            },
        },
    },
    "working": {
        "display_name": "工作记忆",
        "subcategories": {
            "active": {
                "display_name": "活跃项目",
                "keywords": ["项目", "SelfMind", "记忆图谱", "网站", "正在"],
            },
            "backlog": {
                "display_name": "待办事项",
                "keywords": ["待办", "计划", "TODO", "todo", "下一步", "backlog"],
            },
            "archived": {
                "display_name": "历史项目",
                "keywords": ["已完成", "归档", "历史", "曾经", "过去"],
            },
        },
    },
    "spatial": {
        "display_name": "空间记忆",
        "subcategories": {
            "system": {
                "display_name": "系统环境",
                "keywords": ["系统", "环境", "OS", "端口"],
            },
            "filesystem": {
                "display_name": "文件地图",
                "keywords": ["路径", "目录", "文件", "存放"],
            },
            "services": {
                "display_name": "服务拓扑",
                "keywords": ["服务", "接口", "端点", "URL", "webhook"],
            },
        },
    },
    "emotional": {
        "display_name": "情绪记忆",
        "subcategories": {
            "user_mood": {
                "display_name": "用户情绪",
                "keywords": ["情绪", "心情", "焦虑", "高兴", "生气", "沮丧"],
            },
            "likes_dislikes": {
                "display_name": "偏好厌恶",
                "keywords": ["喜欢", "讨厌", "偏好", "希望"],
            },
            "trust": {
                "display_name": "信任关系",
                "keywords": ["信任", "可靠", "信赖", "可信", "不信任"],
            },
        },
    },
}

# Mapping from skill directory categories to procedural subcategories
SKILL_DIR_TO_PROCEDURAL: dict[str, str] = {
    "mlops": "development",
    "software-development": "development",
    "github": "development",
    "devops": "operations",
    "creative": "creative",
    "media": "creative",
    "research": "research",
    "social-media": "communication",
    "email": "communication",
    # Everything else falls to "tools"
}


# ────────────────────────────────────────────────────────────────────
# 2. Entry classification
# ────────────────────────────────────────────────────────────────────

def classify_entry(text: str) -> tuple[str, str]:
    """Classify a memory entry into (primary_key, secondary_key).

    1. First checks for an explicit [primary/secondary] tag in the text.
    2. Falls back to keyword matching across all subcategories.
    3. Defaults to ("working", "active") if nothing matches.
    """
    # Strategy 1: Explicit tag — supports both formats:
    #   [primary/secondary]             e.g. [social/key_people]
    #   [level/primary/secondary]       e.g. [primary/social/key_people]
    tag3 = re.search(r"\[(\w+)/(\w+)/(\w+)\]", text)
    if tag3:
        # 3-part: first segment is a level indicator (primary/secondary), ignore it
        primary_key = tag3.group(2).lower()
        secondary_key = tag3.group(3).lower()
        if primary_key in TAXONOMY:
            if secondary_key in TAXONOMY[primary_key]["subcategories"]:
                return (primary_key, secondary_key)

    tag2 = re.search(r"\[(\w+)/(\w+)\]", text)
    if tag2:
        primary_key = tag2.group(1).lower()
        secondary_key = tag2.group(2).lower()
        if primary_key in TAXONOMY:
            if secondary_key in TAXONOMY[primary_key]["subcategories"]:
                return (primary_key, secondary_key)

    # Strategy 2: Keyword matching — score each subcategory
    best_primary = None
    best_secondary = None
    best_score = 0

    text_lower = text.lower()

    for primary_key, primary_info in TAXONOMY.items():
        for secondary_key, secondary_info in primary_info["subcategories"].items():
            keywords = secondary_info.get("keywords", [])
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > best_score:
                best_score = score
                best_primary = primary_key
                best_secondary = secondary_key

    if best_primary and best_secondary and best_score > 0:
        return (best_primary, best_secondary)

    # Default fallback
    return ("working", "active")


# ────────────────────────────────────────────────────────────────────
# 3. Memory parsing
# ────────────────────────────────────────────────────────────────────

def stable_id(text: str) -> str:
    """Generate a stable short ID from text content."""
    return "n_" + md5(text.encode()).hexdigest()[:8]


def extract_label(text: str, max_len: int = 20) -> str:
    """Extract a clean, short label from a memory section."""
    stripped = text.strip()

    # Remove any taxonomy tag prefix for labelling (2-part or 3-part)
    stripped = re.sub(r"^\[\w+/\w+/\w+\]\s*", "", stripped)
    stripped = re.sub(r"^\[\w+/\w+\]\s*", "", stripped)

    label_prefixes = ["群成员信息", "群成员"]

    kv = re.match(r"^[*\s]*([^:：]{2,30})[：:]\s*(.+)", stripped, re.DOTALL)
    if kv:
        key = re.sub(r"\*", "", kv.group(1)).strip()
        value = re.sub(r"\*", "", kv.group(2)).strip().split("\n")[0].strip()

        if any(key == prefix for prefix in label_prefixes):
            name_part = re.split(r"[（\(—\-–]", value)[0].strip()
            if name_part:
                return name_part[:max_len]

        if re.match(r"^[A-Za-z\s]+$", key) and len(value) <= max_len and value:
            return value[:max_len]

        generic_keys = ["角色", "名称", "姓名", "名字", "身份"]
        if key in generic_keys and value:
            name_part = re.split(r"[（\(—\-–,，]", value)[0].strip()
            if name_part:
                return name_part[:max_len]

        if 2 <= len(key) <= max_len:
            return key[:max_len]

        return (value if len(value) <= max_len else key)[:max_len]

    bold = re.search(r"\*\*(.+?)\*\*", stripped)
    if bold:
        label = bold.group(1).strip()
        if label:
            return label[:max_len]

    first_line = stripped.split("\n")[0]
    clean = re.sub(r"[*#\-]", "", first_line).strip()
    return clean[:max_len] + ("..." if len(clean) > max_len else "")


def parse_memory_file(filepath: Path, separator: str) -> list[str]:
    """Parse a memory file into raw sections split by separator."""
    if not filepath.exists():
        return []
    content = filepath.read_text(encoding="utf-8")
    return [section.strip() for section in content.split(separator) if section.strip()]


def parse_memories(config: dict) -> list[dict]:
    """Parse all memory files and return classified entries.

    Each entry dict contains:
      text, label, primary, secondary, description, node_id, source_profile, source_file
    """
    source_cfg = config.get("source", {})
    profiles = source_cfg.get("profiles", {})
    separator = config.get("section_separator", "§")

    entries: list[dict] = []
    seen_labels: dict[str, int] = {}  # label → index in entries (dedup)

    for profile_name in get_enabled_profiles(config):
        profile = profiles.get(profile_name, {})
        home = Path(profile.get("home", "")).expanduser()
        memory_files = profile.get("memory_files", [])
        fallback_files = profile.get("memory_files_fallback", [])

        source_sections: list[tuple[str, str]] = []

        for rel_path in memory_files:
            file_path = home / rel_path
            if file_path.exists():
                parsed = parse_memory_file(file_path, separator)
                source_sections.extend((section, rel_path) for section in parsed)

        if not source_sections:
            for rel_path in fallback_files:
                file_path = home / rel_path
                if file_path.exists():
                    parsed = parse_memory_file(file_path, separator)
                    source_sections.extend((section, rel_path) for section in parsed)

        for section_text, source_file in source_sections:
            if len(section_text.strip()) < 5:
                continue

            node_id = stable_id(section_text)
            label = extract_label(section_text)
            primary, secondary = classify_entry(section_text)
            description = re.sub(r"\*\*", "", section_text).strip()[:150]

            # Dedup by label — keep richer description
            if label in seen_labels:
                idx = seen_labels[label]
                if len(description) > len(entries[idx]["description"]):
                    entries[idx]["description"] = description
                    entries[idx]["node_id"] = node_id
                continue

            seen_labels[label] = len(entries)
            entries.append({
                "text": section_text,
                "label": label,
                "primary": primary,
                "secondary": secondary,
                "description": description,
                "node_id": node_id,
                "source_profile": profile_name,
                "source_file": source_file,
            })

    return entries


# ────────────────────────────────────────────────────────────────────
# 4. Skill collection
# ────────────────────────────────────────────────────────────────────

def collect_skills(config: dict | None = None) -> list[dict]:
    """Scan ~/.hermes/skills/ for SKILL.md files and parse them.

    Returns a list of dicts:
      name, description, category, subcategory, tags, related_skills, path
    Supports up to 3-level directory structure: category/subcategory/skill
    """
    skills_dir = Path.home() / ".hermes" / "skills"
    if not skills_dir.exists():
        return []

    skill_files = list(skills_dir.rglob("SKILL.md"))
    skills: list[dict] = []

    for sf in skill_files:
        try:
            content = sf.read_text(encoding="utf-8")
            name = sf.parent.name
            desc = ""
            tags: list[str] = []
            related_skills: list[str] = []

            # Determine category and subcategory from directory structure
            rel = sf.parent.relative_to(skills_dir)
            parts = rel.parts
            if len(parts) == 3:
                cat = parts[0]
                subcat = parts[1]
            elif len(parts) == 2:
                cat = parts[0]
                subcat = parts[1] if parts[1] != name else None
            else:
                cat = "uncategorized"
                subcat = None

            # Parse YAML frontmatter
            fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
            if fm_match:
                fm = fm_match.group(1)
                in_tags = False
                in_related = False
                for line in fm.split("\n"):
                    stripped = line.strip()
                    # Reset list parsing on new key
                    if stripped and not stripped.startswith("-") and not stripped.startswith("#"):
                        if not stripped.startswith("- "):
                            in_tags = False
                            in_related = False

                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip().strip("'\"")
                    elif line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip().strip("'\"")
                    elif "tags:" in stripped and "[" in stripped:
                        tag_match = re.search(r"\[(.+?)\]", stripped)
                        if tag_match:
                            tags = [t.strip().strip("'\"") for t in tag_match.group(1).split(",")]
                    elif "tags:" in stripped:
                        in_tags = True
                        in_related = False
                    elif "related_skills:" in stripped and "[" in stripped:
                        rs_match = re.search(r"\[(.+?)\]", stripped)
                        if rs_match:
                            related_skills = [r.strip().strip("'\"") for r in rs_match.group(1).split(",")]
                    elif "related_skills:" in stripped:
                        in_related = True
                        in_tags = False
                    elif in_tags and stripped.startswith("- "):
                        tags.append(stripped[2:].strip().strip("'\""))
                    elif in_related and stripped.startswith("- "):
                        related_skills.append(stripped[2:].strip().strip("'\""))

            skills.append({
                "name": name,
                "description": desc[:150] if desc else f"Skill: {name}",
                "category": cat,
                "subcategory": subcat,
                "tags": tags,
                "related_skills": related_skills,
                "path": str(sf.parent),
            })
        except (OSError, UnicodeDecodeError):
            continue

    return skills


# ────────────────────────────────────────────────────────────────────
# 5. Graph builder
# ────────────────────────────────────────────────────────────────────

def _map_skill_to_procedural(category_dir: str) -> str:
    """Map a skill directory category to a procedural subcategory."""
    return SKILL_DIR_TO_PROCEDURAL.get(category_dir, "tools")


def build_graph(config: dict) -> dict:
    """Build the complete hierarchical knowledge graph.

    Node hierarchy:
      center (Me)
        └─ primary (8 categories)
             └─ secondary (subcategories, only if populated)
                  └─ memory (individual entries)
                  └─ skill_category → skill_subcategory → skill
    """
    nodes: list[dict] = []
    links: list[dict] = []
    node_ids: set[str] = set()
    link_keys: set[str] = set()

    def add_node(
        node_id: str,
        label: str,
        category: str,
        description: str = "",
        primary: str = "",
        secondary: str = "",
        group: str = "",
    ) -> None:
        if node_id not in node_ids:
            nodes.append({
                "id": node_id,
                "label": label,
                "category": category,
                "description": description,
                "primary": primary,
                "secondary": secondary,
                "group": group or category,
            })
            node_ids.add(node_id)

    def add_link(source: str, target: str, label: str = "") -> None:
        if source in node_ids and target in node_ids:
            key = f"{source}->{target}"
            if key not in link_keys:
                links.append({"source": source, "target": target, "label": label})
                link_keys.add(key)

    # ── Center node ──
    center_cfg = config.get("center_node", {
        "id": "self",
        "label": "Me",
        "category": "identity",
        "description": "Center node — the owner of this memory graph",
    })
    center_id = center_cfg["id"]
    add_node(
        center_id,
        center_cfg["label"],
        "center",
        center_cfg.get("description", ""),
        primary="",
        secondary="",
        group="center",
    )

    # ── Primary category nodes ──
    primary_node_ids: dict[str, str] = {}
    for primary_key, primary_info in TAXONOMY.items():
        p_id = f"p_{primary_key}"
        primary_node_ids[primary_key] = p_id
        add_node(
            p_id,
            primary_info["display_name"],
            "primary",
            description=f"{primary_info['display_name']} ({primary_key})",
            primary=primary_key,
            secondary="",
            group=primary_key,
        )
        add_link(center_id, p_id, "has_memory_type")

    # ── Parse memories ──
    entries = parse_memories(config)

    # Collect which secondaries are actually populated
    populated_secondaries: dict[str, set[str]] = {}
    for entry in entries:
        pk, sk = entry["primary"], entry["secondary"]
        populated_secondaries.setdefault(pk, set()).add(sk)

    # ── Secondary category nodes (only for populated subcategories) ──
    secondary_node_ids: dict[str, str] = {}  # "primary/secondary" → node_id
    for pk, sk_set in populated_secondaries.items():
        for sk in sk_set:
            combo_key = f"{pk}/{sk}"
            s_id = f"s_{pk}_{sk}"
            secondary_node_ids[combo_key] = s_id
            sub_info = TAXONOMY[pk]["subcategories"].get(sk, {})
            display = sub_info.get("display_name", sk)
            add_node(
                s_id,
                display,
                "secondary",
                description=f"{display} ({sk})",
                primary=pk,
                secondary=sk,
                group=pk,
            )
            add_link(primary_node_ids[pk], s_id, "contains")

    # ── Memory nodes ──
    for entry in entries:
        pk, sk = entry["primary"], entry["secondary"]
        combo_key = f"{pk}/{sk}"
        parent_id = secondary_node_ids.get(combo_key, primary_node_ids.get(pk, center_id))

        add_node(
            entry["node_id"],
            entry["label"],
            "memory",
            description=entry["description"],
            primary=pk,
            secondary=sk,
            group=pk,
        )
        add_link(parent_id, entry["node_id"], "contains")

    # ── Cross-references between memory nodes ──
    for entry in entries:
        nid = entry["node_id"]
        if nid not in node_ids:
            continue
        text = entry["text"]
        for other in entries:
            if other["node_id"] == nid:
                continue
            other_label = other["label"]
            if len(other_label) >= 2 and other_label in text:
                add_link(nid, other["node_id"], "mentions")

    # ── Skill nodes (hierarchical under procedural) ──
    skills = collect_skills(config)
    skill_name_to_id: dict[str, str] = {}

    # Ensure procedural primary node exists
    procedural_p_id = primary_node_ids.get("procedural", "p_procedural")

    # Ensure procedural secondary nodes exist for skill-mapped subcategories
    # Collect which procedural secondaries are needed by skills
    needed_proc_secondaries: set[str] = set()
    for skill in skills:
        proc_sub = _map_skill_to_procedural(skill["category"])
        needed_proc_secondaries.add(proc_sub)

    for proc_sub in needed_proc_secondaries:
        combo_key = f"procedural/{proc_sub}"
        if combo_key not in secondary_node_ids:
            s_id = f"s_procedural_{proc_sub}"
            sub_info = TAXONOMY["procedural"]["subcategories"].get(proc_sub, {})
            display = sub_info.get("display_name", proc_sub)
            secondary_node_ids[combo_key] = s_id
            add_node(
                s_id,
                display,
                "secondary",
                description=f"{display} ({proc_sub})",
                primary="procedural",
                secondary=proc_sub,
                group="procedural",
            )
            add_link(procedural_p_id, s_id, "contains")

    # Level: skill_category nodes (directory-level categories under the appropriate procedural secondary)
    skill_cat_ids: dict[str, str] = {}  # category_dir → node_id

    # Level: skill_subcategory nodes
    skill_subcat_ids: dict[str, str] = {}  # "category/subcategory" → node_id

    for skill in skills:
        cat_name = skill["category"]
        subcat_name = skill.get("subcategory")
        proc_sub = _map_skill_to_procedural(cat_name)
        combo_key = f"procedural/{proc_sub}"
        proc_secondary_nid = secondary_node_ids.get(combo_key, procedural_p_id)

        # Create skill_category node if needed
        if cat_name not in skill_cat_ids:
            cat_id = "sc_" + md5(cat_name.encode()).hexdigest()[:8]
            add_node(
                cat_id,
                cat_name,
                "skill_category",
                description=f"技能分类: {cat_name}",
                primary="procedural",
                secondary=proc_sub,
                group="procedural",
            )
            skill_cat_ids[cat_name] = cat_id
            add_link(proc_secondary_nid, cat_id, "contains")

        # Create skill_subcategory node if needed
        parent_id = skill_cat_ids[cat_name]
        if subcat_name:
            subcat_key = f"{cat_name}/{subcat_name}"
            if subcat_key not in skill_subcat_ids:
                subcat_id = "ss_" + md5(subcat_key.encode()).hexdigest()[:8]
                add_node(
                    subcat_id,
                    subcat_name,
                    "skill_subcategory",
                    description=f"子分类: {cat_name}/{subcat_name}",
                    primary="procedural",
                    secondary=proc_sub,
                    group="procedural",
                )
                skill_subcat_ids[subcat_key] = subcat_id
                add_link(parent_id, subcat_id, "contains")
            parent_id = skill_subcat_ids[subcat_key]

        # Create skill node (leaf)
        skill_id = "sk_" + md5(skill["name"].encode()).hexdigest()[:8]
        add_node(
            skill_id,
            skill["name"],
            "skill",
            description=skill["description"],
            primary="procedural",
            secondary=proc_sub,
            group="procedural",
        )
        skill_name_to_id[skill["name"]] = skill_id
        add_link(parent_id, skill_id, "contains")

    # ── Cross-link skills via related_skills ──
    for skill in skills:
        skill_id = skill_name_to_id.get(skill["name"])
        if not skill_id:
            continue
        for related_name in skill.get("related_skills", []):
            related_id = skill_name_to_id.get(related_name)
            if related_id and related_id != skill_id:
                add_link(skill_id, related_id, "related")

    # ── Cross-link skills sharing tags ──
    tag_to_skills: dict[str, list[str]] = {}
    for skill in skills:
        skill_id = skill_name_to_id.get(skill["name"])
        if not skill_id:
            continue
        for tag in skill.get("tags", []):
            tag_key = tag.lower().strip()
            if tag_key:
                tag_to_skills.setdefault(tag_key, []).append(skill_id)

    for _tag_key, sids in tag_to_skills.items():
        if 2 <= len(sids) <= 6:
            for i in range(len(sids)):
                for j in range(i + 1, len(sids)):
                    add_link(sids[i], sids[j], "shares_tag")

    # ── Build result ──
    used_sources: list[str] = []
    source_cfg = config.get("source", {})
    profiles = source_cfg.get("profiles", {})
    for profile_name in get_enabled_profiles(config):
        profile = profiles.get(profile_name, {})
        home = profile.get("home", "")
        used_sources.append(f"{profile_name}:{home}")

    source_text = ", ".join(used_sources) if used_sources else "none"

    return {
        "lastUpdated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "source": source_text,
        "sources": used_sources,
        "nodes": nodes,
        "links": links,
    }
