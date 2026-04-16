"""
Wiki parser for SelfMind — reads LLM Wiki markdown pages and builds a
D3-compatible knowledge graph that can be rendered alongside the memory graph.
"""

import hashlib
import re
from datetime import datetime
from pathlib import Path

# Directories to scan inside the wiki root
_SCAN_DIRS = {"entities", "concepts", "comparisons", "queries"}

# Map parent directory name → page type fallback
_DIR_TYPE_MAP = {
    "entities": "entity",
    "concepts": "concept",
    "comparisons": "comparison",
    "queries": "query",
}

# Files at the wiki root to skip
_SKIP_FILES = {"SCHEMA.md", "index.md", "log.md"}

# Regex patterns
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

def parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown using simple regex parsing.

    Returns a dict with keys: title, created, updated, type, tags, sources.
    Missing keys get sensible defaults.
    """
    result: dict = {
        "title": "",
        "created": "",
        "updated": "",
        "type": "",
        "tags": [],
        "sources": [],
    }

    match = _FRONTMATTER_RE.match(content)
    if not match:
        return result

    raw = match.group(1)

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Simple "key: value" parsing
        kv = line.split(":", 1)
        if len(kv) != 2:
            continue

        key = kv[0].strip().lower()
        value = kv[1].strip()

        if key == "title":
            result["title"] = value.strip('"').strip("'")
        elif key == "created":
            result["created"] = value.strip('"').strip("'")
        elif key == "updated":
            result["updated"] = value.strip('"').strip("'")
        elif key == "type":
            result["type"] = value.strip('"').strip("'")
        elif key == "tags":
            result["tags"] = _parse_yaml_list(value, raw, "tags")
        elif key == "sources":
            result["sources"] = _parse_yaml_list(value, raw, "sources")

    return result


def _parse_yaml_list(inline_value: str, raw_block: str, key: str) -> list[str]:
    """Parse a YAML list that is either inline `[a, b]` or multi-line `- item`."""
    # Inline form: [tag1, tag2]
    if inline_value.startswith("["):
        inner = inline_value.strip("[]")
        return [item.strip().strip('"').strip("'") for item in inner.split(",") if item.strip()]

    # Multi-line form: collect subsequent lines starting with "  - "
    items: list[str] = []
    capture = False
    for line in raw_block.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(f"{key}:"):
            capture = True
            continue
        if capture:
            if stripped.startswith("- "):
                items.append(stripped[2:].strip().strip('"').strip("'"))
            elif stripped and not stripped.startswith("-"):
                break  # next key
    return items


# ---------------------------------------------------------------------------
# Wikilink extraction
# ---------------------------------------------------------------------------

def extract_wikilinks(content: str) -> list[str]:
    """Find all [[wikilink]] references in the markdown body (after frontmatter).

    Returns a deduplicated list preserving first-occurrence order.
    """
    # Strip frontmatter
    body = _FRONTMATTER_RE.sub("", content, count=1)
    seen: set[str] = set()
    links: list[str] = []
    for m in _WIKILINK_RE.finditer(body):
        name = m.group(1).strip()
        if name and name not in seen:
            seen.add(name)
            links.append(name)
    return links


# ---------------------------------------------------------------------------
# Wiki scanning
# ---------------------------------------------------------------------------

def scan_wiki_pages(wiki_path: str) -> list[dict]:
    """Scan the wiki directory for .md files in recognised subdirectories.

    Returns a list of page dicts with metadata extracted from frontmatter and content.
    """
    root = Path(wiki_path)
    if not root.is_dir():
        return []

    pages: list[dict] = []

    for subdir_name in sorted(_SCAN_DIRS):
        subdir = root / subdir_name
        if not subdir.is_dir():
            continue

        for md_file in sorted(subdir.rglob("*.md")):
            # Skip known root-level files (shouldn't appear here, but be safe)
            if md_file.name in _SKIP_FILES:
                continue

            try:
                content = md_file.read_text(encoding="utf-8")
            except OSError:
                continue

            fm = parse_frontmatter(content)
            wikilinks = extract_wikilinks(content)

            # Body after frontmatter for preview
            body = _FRONTMATTER_RE.sub("", content, count=1).strip()
            preview = body[:200] if body else ""

            name = md_file.stem  # filename without .md

            pages.append({
                "name": name,
                "title": fm["title"] or name,
                "type": fm["type"] or _DIR_TYPE_MAP.get(subdir_name, "entity"),
                "tags": fm["tags"],
                "sources": fm["sources"],
                "wikilinks": wikilinks,
                "content_preview": preview,
                "path": str(md_file),
                "created": fm["created"],
                "updated": fm["updated"],
            })

    return pages


# ---------------------------------------------------------------------------
# Graph building
# ---------------------------------------------------------------------------

def _md5_short(text: str) -> str:
    """Return first 8 hex chars of the MD5 hash of *text*."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


def build_wiki_graph(config: dict) -> dict:
    """Build a D3-compatible graph dict from the wiki.

    The returned dict has keys: lastUpdated, source, nodes, links —
    matching the memory graph format so the frontend can reuse rendering.
    """
    wiki_cfg = config.get("wiki", {})
    wiki_path = wiki_cfg.get("path", "")

    if not wiki_cfg.get("enabled", False) or not wiki_path:
        return {"lastUpdated": "", "source": "", "nodes": [], "links": []}

    pages = scan_wiki_pages(wiki_path)

    nodes: list[dict] = []
    links: list[dict] = []

    # --- Center node ---
    center_id = "wiki_center"
    nodes.append({
        "id": center_id,
        "label": "知识图谱",
        "category": "wiki_center",
        "description": "LLM Wiki knowledge graph center",
        "primary": "wiki_center",
        "secondary": "",
        "group": "wiki_center",
        "tags": [],
        "created": "",
        "updated": "",
    })

    # Build a name → node-id lookup for wikilink resolution
    name_to_id: dict[str, str] = {}
    for page in pages:
        node_id = "w_" + _md5_short(page["name"])
        name_to_id[page["name"]] = node_id

    # --- Page nodes ---
    for page in pages:
        node_id = name_to_id[page["name"]]
        nodes.append({
            "id": node_id,
            "label": page["title"],
            "category": page["type"],
            "description": page["content_preview"],
            "primary": page["type"],
            "secondary": "",
            "group": page["type"],
            "tags": page["tags"],
            "created": page["created"],
            "updated": page["updated"],
        })

        # Center → page
        links.append({
            "source": center_id,
            "target": node_id,
            "label": "contains",
        })

    # --- Tag nodes ---
    all_tags: dict[str, str] = {}  # tag text → node id
    for page in pages:
        for tag in page["tags"]:
            if tag not in all_tags:
                tag_id = "wt_" + _md5_short(tag)
                all_tags[tag] = tag_id
                nodes.append({
                    "id": tag_id,
                    "label": tag,
                    "category": "wiki_tag",
                    "description": "",
                    "primary": "wiki_tag",
                    "secondary": "",
                    "group": "wiki_tag",
                    "tags": [],
                    "created": "",
                    "updated": "",
                })

    # --- Wikilink edges (page → page) ---
    for page in pages:
        source_id = name_to_id[page["name"]]
        for linked_name in page["wikilinks"]:
            target_id = name_to_id.get(linked_name)
            if target_id:
                links.append({
                    "source": source_id,
                    "target": target_id,
                    "label": "references",
                })

    # --- Tag edges (page → tag) ---
    for page in pages:
        source_id = name_to_id[page["name"]]
        for tag in page["tags"]:
            tag_id = all_tags[tag]
            links.append({
                "source": source_id,
                "target": tag_id,
                "label": "tagged",
            })

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "lastUpdated": now,
        "source": wiki_path,
        "nodes": nodes,
        "links": links,
    }
