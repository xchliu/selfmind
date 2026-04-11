import re
from datetime import datetime
from hashlib import md5
from pathlib import Path

from selfmind_app.config import get_enabled_profiles


def stable_id(text: str) -> str:
    """Generate a stable short ID from text content."""
    return "n_" + md5(text.encode()).hexdigest()[:8]


def extract_label(text: str, max_len: int = 20) -> str:
    """Extract a clean, short label from a memory section."""
    stripped = text.strip()
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


def classify_section(text: str, categories: dict) -> str:
    """Classify a memory section into a category based on keyword matching."""
    text_lower = text.lower()
    best_category = "memory"
    best_score = 0

    for category_name, category_info in categories.items():
        if category_name == "identity":
            continue
        keywords = category_info.get("keywords", [])
        score = sum(1 for keyword in keywords if keyword.lower() in text_lower)
        if score > best_score:
            best_score = score
            best_category = category_name

    return best_category


def detect_relation(text: str, relation_keywords: dict) -> str:
    """Detect the relationship type from text content."""
    text_lower = text.lower()
    for pattern, relation in relation_keywords.items():
        if any(keyword in text_lower for keyword in pattern.split("|")):
            return relation
    return "related"


def detect_connections(nodes: list, text: str) -> list:
    """Find references to other nodes within a section's text."""
    connections = []
    for node in nodes:
        label = node["label"]
        if len(label) >= 2 and label in text:
            connections.append(node["id"])
    return connections


def parse_memory_file(filepath: Path, separator: str) -> list[str]:
    """Parse a memory file into sections."""
    if not filepath.exists():
        return []
    content = filepath.read_text(encoding="utf-8")
    return [section.strip() for section in content.split(separator) if section.strip()]


def collect_sections(config: dict) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Read memory sections from enabled source profiles.

    Returns:
        (all_sections, used_sources)
        all_sections item format: (section_text, profile_name, source_file)
    """
    source_cfg = config.get("source", {})
    profiles = source_cfg.get("profiles", {})
    separator = config["section_separator"]

    all_sections: list[tuple[str, str, str]] = []
    used_sources: list[str] = []

    for profile_name in get_enabled_profiles(config):
        profile = profiles.get(profile_name, {})
        home = Path(profile.get("home", "")).expanduser()
        memory_files = profile.get("memory_files", [])
        fallback_files = profile.get("memory_files_fallback", [])

        source_sections: list[tuple[str, str, str]] = []

        for rel_path in memory_files:
            file_path = home / rel_path
            if file_path.exists():
                parsed = parse_memory_file(file_path, separator)
                source_sections.extend((section, profile_name, rel_path) for section in parsed)

        if not source_sections:
            for rel_path in fallback_files:
                file_path = home / rel_path
                if file_path.exists():
                    parsed = parse_memory_file(file_path, separator)
                    source_sections.extend((section, profile_name, rel_path) for section in parsed)

        if source_sections:
            used_sources.append(f"{profile_name}:{home}")
            all_sections.extend(source_sections)

    return all_sections, used_sources


def build_graph(config: dict) -> dict:
    """Build a complete knowledge graph from configured memory sources."""
    nodes = []
    links = []
    node_ids = set()

    def add_node(node_id: str, label: str, category: str, description: str = ""):
        if node_id not in node_ids:
            nodes.append({
                "id": node_id,
                "label": label,
                "category": category,
                "description": description,
            })
            node_ids.add(node_id)

    def add_link(source: str, target: str, label: str = ""):
        if source in node_ids and target in node_ids:
            key = f"{source}->{target}"
            if not any(f"{item['source']}->{item['target']}" == key for item in links):
                links.append({"source": source, "target": target, "label": label})

    center = config["center_node"]
    add_node(center["id"], center["label"], center["category"], center["description"])
    center_id = center["id"]

    all_sections, used_sources = collect_sections(config)
    categories = config["categories"]
    relation_keywords = config["relation_keywords"]
    label_to_id = {}

    for section_text, _profile_name, _source_file in all_sections:
        if len(section_text.strip()) < 5:
            continue

        node_id = stable_id(section_text)
        label = extract_label(section_text)
        category = classify_section(section_text, categories)
        description = re.sub(r"\*\*", "", section_text).strip()[:150]

        if label in label_to_id:
            existing_id = label_to_id[label]
            for node in nodes:
                if node["id"] == existing_id and len(description) > len(node["description"]):
                    node["description"] = description
            node_id = existing_id
        else:
            add_node(node_id, label, category, description)
            label_to_id[label] = node_id

        relation = detect_relation(section_text, relation_keywords)
        add_link(center_id, node_id, relation)

    for section_text, _profile_name, _source_file in all_sections:
        node_id = stable_id(section_text)
        if node_id not in node_ids:
            continue
        refs = detect_connections(nodes, section_text)
        for ref_id in refs:
            if ref_id != node_id and ref_id != center_id:
                add_link(node_id, ref_id, "mentions")

    source_text = ", ".join(used_sources) if used_sources else "none"
    return {
        "lastUpdated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "source": source_text,
        "sources": used_sources,
        "nodes": nodes,
        "links": links,
    }
