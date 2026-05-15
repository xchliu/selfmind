"""Unified sync engine for SelfMind — single entry point for all data sources.

Core principle: SelfMind records EVOLUTION, not just current state.
Every sync:
  1. Creates a snapshot of source files (for temporal comparison)
  2. Parses all data sources into entry dicts
  3. Bulk upserts with evolution tracking (no deletion, only inactivation)
  4. Logs all changes in operations_log

Collects data from:
  1. Memory files (MEMORY.md, USER.md) — §-separated entries with [category/subcategory] tags
  2. Wiki pages (*.md in wiki directory) — YAML frontmatter + markdown body
  3. Honcho API — observations (explicit/inductive/deductive/contradiction), conclusions
  4. Skills directory — SKILL.md files with YAML frontmatter
"""

import logging
import os
import re
import json
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Optional

from .unified_store import UnifiedStore
from .parser import classify_entry, extract_label  # Reuse existing classification logic

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────

TAG_RE = re.compile(r'\[(\w+)(?:/(\w+))?(?:/(\w+))?\]')

def _http_get(url: str, timeout: int = 10) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        logger.warning(f"HTTP GET {url} failed: {exc}")
        return None


def _http_post(url: str, body: dict, timeout: int = 15) -> Optional[dict | list]:
    try:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        logger.warning(f"HTTP POST {url} failed: {exc}")
        return None


def _read_file_safe(filepath: str) -> str:
    """Read a file safely, returning empty string if not found."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


# ────────────────────────────────────────────────────────────
# Source 1: Memory files (MEMORY.md, USER.md)
# ────────────────────────────────────────────────────────────

def parse_memory_file(filepath: str, source_name: str, profile: str) -> list[dict]:
    """Parse §-separated memory file into entry dicts."""
    if not os.path.exists(filepath):
        return []

    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    parts = raw.split("§")
    entries = []
    for part in parts:
        text = part.strip()
        if not text or len(text) < 5:
            continue

        # Extract [category/subcategory] tag — skip literal 'primary' prefix
        primary_cat = secondary_cat = None
        m = TAG_RE.search(text)
        if m:
            parts = [g for g in m.groups() if g]
            if parts[0] == 'primary' and len(parts) > 1:
                # [primary/autobiographical/principles] → autobiographical + principles
                primary_cat = parts[1]
                secondary_cat = parts[2] if len(parts) > 2 else None
            else:
                # [autobiographical/identity] → autobiographical + identity
                primary_cat = parts[0]
                secondary_cat = parts[1] if len(parts) > 1 else None

        # If no explicit tag, classify via keywords
        if not primary_cat:
            primary_cat, secondary_cat = classify_entry(text)

        label = extract_label(text, max_len=20)

        # Importance based on category hierarchy
        IMPORTANCE_BY_CAT = {
            "security": 0.9, "identity": 0.9,
            "autobiographical": 0.7, "procedural": 0.6, "skill": 0.6,
            "semantic": 0.5, "social": 0.5, "working": 0.4,
        }
        importance = IMPORTANCE_BY_CAT.get(primary_cat, 0.5)

        entries.append({
            "content": text,
            "type": "memory",
            "source": source_name,
            "source_profile": profile,
            "primary_cat": primary_cat,
            "secondary_cat": secondary_cat,
            "label": label,
            "importance": importance,
        })

    return entries


# ────────────────────────────────────────────────────────────
# Source 2: Wiki pages
# ────────────────────────────────────────────────────────────

def parse_wiki_page(filepath: str, wiki_root: str, profile: str) -> Optional[dict]:
    """Parse a wiki markdown file with YAML frontmatter into an entry dict."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None

    # Split frontmatter and body
    fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not fm_match:
        body = content
        frontmatter = {}
    else:
        fm_text = fm_match.group(1)
        body = fm_match.group(2)

        # Parse YAML-like frontmatter
        frontmatter = {}
        for line in fm_text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r'^(\w+):\s*(.+)$', line)
            if m:
                frontmatter[m.group(1)] = m.group(2).strip()

    if not body.strip():
        return None

    # Determine type from directory
    rel_path = str(Path(filepath).relative_to(wiki_root))
    dir_name = rel_path.split("/")[0] if "/" in rel_path else "misc"

    dir_type_map = {
        "entities": "entity", "concepts": "concept", "comparisons": "comparison",
        "queries": "query", "projects": "project", "summaries": "summary",
        "raw": "raw",
    }
    page_type = dir_type_map.get(dir_name, "wiki")
    wiki_type = frontmatter.get("type", page_type)

    title = frontmatter.get("title", Path(filepath).stem)
    tags_raw = frontmatter.get("tags", "")
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    label = title[:25]

    # Importance by wiki page type
    WIKI_IMPORTANCE = {
        "entity": 0.5, "concept": 0.5, "comparison": 0.4,
        "query": 0.4, "project": 0.6, "summary": 0.3,
    }
    importance = WIKI_IMPORTANCE.get(wiki_type, 0.4)

    return {
        "content": body.strip(),
        "type": "wiki",
        "source": filepath,
        "source_profile": profile,
        "primary_cat": wiki_type,
        "secondary_cat": dir_name,
        "label": label,
        "tags": json.dumps(tags),
        "importance": importance,
    }


def scan_wiki_directory(wiki_root: str, profile: str) -> list[dict]:
    """Scan all wiki subdirectories and parse markdown files."""
    scan_dirs = {"entities", "concepts", "comparisons", "queries", "projects", "summaries", "raw"}
    entries = []

    if not os.path.exists(wiki_root):
        return entries

    for dir_name in scan_dirs:
        dir_path = os.path.join(wiki_root, dir_name)
        if not os.path.isdir(dir_path):
            continue
        for fname in os.listdir(dir_path):
            if fname.endswith(".md"):
                fpath = os.path.join(dir_path, fname)
                entry = parse_wiki_page(fpath, wiki_root, profile)
                if entry:
                    entries.append(entry)

    return entries


# ────────────────────────────────────────────────────────────
# Source 3: Honcho API
# ────────────────────────────────────────────────────────────

def fetch_honcho_documents(base_url: str, workspace: str, page_size: int = 200) -> list[dict]:
    """Fetch Honcho documents via PostgreSQL direct query (more reliable than API)."""
    try:
        result = subprocess.run(
            ["psql", "-h", "localhost", "-U", "postgres",
             "-c", f"SELECT id, observer, observed, level, content FROM documents "
                    f"WHERE workspace_name='{workspace}' "
                    f"AND level IN ('inductive','deductive','contradiction') "
                    f"AND deleted_at IS NULL ORDER BY created_at DESC",
             ],
            capture_output=True, text=True, timeout=15,
            env={**os.environ, "PGPASSWORD": "postgres"},
        )
        if result.returncode != 0:
            logger.warning(f"psql query failed: {result.stderr}")
            return []
        # Parse psql tabular output
        lines = result.stdout.strip().split("\n")
        docs = []
        for line in lines[2:]:
            if line.startswith("(") or not line.strip() or line.count("|") < 4:
                continue
            parts = line.split("|")
            if len(parts) >= 5:
                docs.append({
                    "id": parts[0].strip(),
                    "observer": parts[1].strip(),
                    "observed": parts[2].strip(),
                    "level": parts[3].strip(),
                    "content": parts[4].strip(),
                })
        return docs
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning(f"psql not available or timed out: {exc}")
        return _fetch_honcho_via_api(base_url, workspace, page_size)


def _fetch_honcho_via_api(base_url: str, workspace: str, page_size: int = 200) -> list[dict]:
    """Fallback: fetch documents via Honcho REST API."""
    url = f"{base_url}/workspaces/{workspace}/documents/list"
    all_items = []
    page = 1
    while True:
        result = _http_post(url, {"page": page, "size": page_size})
        if result is None:
            break
        items = result.get("items", []) if isinstance(result, dict) else []
        if not items:
            break
        all_items.extend(items)
        total_pages = result.get("pages", 1)
        if page >= total_pages:
            break
        page += 1
    return all_items


def fetch_honcho_conclusions(base_url: str, workspace: str, page_size: int = 200) -> list[dict]:
    """Fetch all conclusions from Honcho API — paginated."""
    url = f"{base_url}/workspaces/{workspace}/conclusions/list"
    all_items = []
    page = 1

    while True:
        result = _http_post(url, {"page": page, "size": page_size})
        if result is None:
            break
        items = result.get("items", []) if isinstance(result, dict) else []
        if not items:
            break
        all_items.extend(items)
        total_pages = result.get("pages", 1)
        if page >= total_pages:
            break
        page += 1

    return all_items


def honcho_doc_to_entry(doc: dict, profile: str) -> Optional[dict]:
    """Convert a Honcho document (observation) into an entry dict."""
    content = doc.get("content", "")
    if not content or len(content.strip()) < 5:
        return None

    level = doc.get("level", "explicit")
    level_type_map = {
        "explicit": "honcho_obs",
        "inductive": "honcho_obs",
        "deductive": "honcho_obs",
        "contradiction": "honcho_obs",
    }
    entry_type = level_type_map.get(level, "honcho_obs")

    primary_cat, secondary_cat = classify_entry(content)
    label = extract_label(content, max_len=20)

    return {
        "content": content.strip(),
        "type": entry_type,
        "source": f"honcho_api/{level}",
        "source_profile": profile,
        "primary_cat": primary_cat,
        "secondary_cat": secondary_cat,
        "label": label,
        "observer": doc.get("observer", ""),
        "observed": doc.get("observed", ""),
        "honcho_level": level,
        "honcho_doc_id": doc.get("id", ""),
    }


def honcho_conclusion_to_entry(conc: dict, profile: str) -> Optional[dict]:
    """Convert a Honcho conclusion into an entry dict."""
    content = conc.get("content", "")
    if not content or len(content.strip()) < 5:
        return None

    primary_cat, secondary_cat = classify_entry(content)
    label = extract_label(content, max_len=20)

    return {
        "content": content.strip(),
        "type": "honcho_conc",
        "source": "honcho_api/conclusions",
        "source_profile": profile,
        "primary_cat": primary_cat,
        "secondary_cat": secondary_cat,
        "label": label,
        "observer": conc.get("observer_id", ""),
        "observed": conc.get("observed_id", ""),
        "honcho_level": "conclusion",
        "honcho_doc_id": conc.get("id", ""),
    }


# ────────────────────────────────────────────────────────────
# Source 4: Skills
# ────────────────────────────────────────────────────────────

def scan_skills_directory(skills_root: str, profile: str) -> list[dict]:
    """Scan skills directory for SKILL.md files."""
    entries = []
    if not os.path.exists(skills_root):
        return entries

    for category_dir in os.listdir(skills_root):
        cat_path = os.path.join(skills_root, category_dir)
        if not os.path.isdir(cat_path):
            continue
        for skill_dir in os.listdir(cat_path):
            skill_path = os.path.join(cat_path, skill_dir)
            skill_md = os.path.join(skill_path, "SKILL.md")
            if not os.path.isfile(skill_md):
                continue
            try:
                with open(skill_md, "r", encoding="utf-8") as f:
                    content = f.read()
            except OSError:
                continue

            if not content.strip() or len(content.strip()) < 20:
                continue

            entries.append({
                "content": content.strip(),
                "type": "skill",
                "source": skill_md,
                "source_profile": profile,
                "primary_cat": "skill",
                "secondary_cat": category_dir,
                "label": skill_dir[:25],
                "importance": 0.6,
            })

    return entries


# ────────────────────────────────────────────────────────────
# Master sync: orchestrates all sources (evolution-aware)
# ────────────────────────────────────────────────────────────

def unified_sync(store: UnifiedStore, config: dict) -> dict:
    """Master sync: collect from all sources and write to unified store.

    Evolution-aware:
      1. Create snapshot of source files before any changes
      2. Parse all sources
      3. Bulk upsert per source type (with source_type to prevent cross-type inactivation)
      4. Compute decay scores
      5. Record comprehensive stats

    Returns stats dict.
    """
    stats = {"memory": {}, "wiki": {}, "honcho": {}, "skills": {}}

    source_cfg = config.get("source", {})
    profiles = source_cfg.get("profiles", {})

    # Resolve active profile and home directory (used by all sources)
    active_profile = source_cfg.get("active_profile", "hermes")
    profile_cfg = profiles.get(active_profile, {})
    home = Path(profile_cfg.get("home", Path.home() / ".hermes"))

    # ── Step 0: Create snapshot of source files BEFORE sync ──
    memory_file_path = str(home / "memories" / "MEMORY.md")
    user_file_path = str(home / "memories" / "USER.md")
    memory_md = _read_file_safe(memory_file_path)
    user_md = _read_file_safe(user_file_path)
    snapshot_id = store.create_snapshot(memory_md, user_md, trigger="sync")
    stats["snapshot_id"] = snapshot_id
    logger.info(f"Snapshot #{snapshot_id} created before sync")

    # ── Source 1: Memory files ──
    memory_files = profile_cfg.get("memory_files", ["memories/MEMORY.md", "memories/USER.md"])
    memory_entries = []
    for mf in memory_files:
        filepath = str(home / mf)
        entries = parse_memory_file(filepath, mf, active_profile)
        memory_entries.extend(entries)

    if memory_entries:
        result = store.bulk_upsert(memory_entries, source_type="memory")
        stats["memory"] = {"entries": len(memory_entries), **result}

    # ── Source 2: Wiki pages ──
    wiki_root = config.get("wiki", {}).get("path", str(home / "wiki"))
    wiki_entries = scan_wiki_directory(wiki_root, active_profile)
    if wiki_entries:
        result = store.bulk_upsert(wiki_entries, source_type="wiki")
        stats["wiki"] = {"entries": len(wiki_entries), **result}

    # ── Source 3: Honcho (optional) ──
    honcho_env = os.environ.get("HONCHO_ENABLED", "true").lower()
    if honcho_env in ("false", "0", "no", "off"):
        logger.info("Honcho disabled by HONCHO_ENABLED env var")
        stats["honcho"] = {"skipped": True, "reason": "disabled by env"}
    else:
        active_profile = source_cfg.get("active_profile", "hermes")
        profile_cfg = profiles.get(active_profile, {})
        api_config = profile_cfg.get("api", {})
        honcho_enabled = api_config.get("type") == "honcho" and api_config.get("enabled", True)
        if honcho_enabled:
            base_url = api_config.get("base_url", "http://localhost:8000/v3")
            workspace = api_config.get("workspace", "hermes")
            try:
                honcho_stats = sync_honcho(store, base_url, workspace, active_profile)
                stats["honcho"] = honcho_stats
            except Exception as exc:
                logger.warning(f"Honcho sync failed (graceful skip): {exc}")
                stats["honcho"] = {"skipped": True, "reason": str(exc)}
        else:
            logger.info("Honcho not configured for active profile")
            stats["honcho"] = {"skipped": True, "reason": "not configured"}

    # ── Source 4: Skills ──
    skills_root = str(home / "skills")
    skills_entries = scan_skills_directory(skills_root, active_profile)
    if skills_entries:
        result = store.bulk_upsert(skills_entries, source_type="skill")
        stats["skills"] = {"entries": len(skills_entries), **result}

    # ── Compute decay scores ──
    decay_updated = store.compute_decay_scores()
    stats["decay_updated"] = decay_updated

    # ── Overall stats ──
    overall = store.get_stats()
    stats["total_active"] = overall["total_active"]
    stats["total_inactive"] = overall["total_inactive"]
    stats["by_type"] = overall["by_type"]
    stats["version_changes"] = overall["version_changes"]

    logger.info(f"Unified sync complete: {stats}")
    return stats


def sync_honcho(store: UnifiedStore, base_url: str, workspace: str, profile: str) -> dict:
    """Sync Honcho documents and conclusions into the unified store.
    Evolution-aware: inactivates old Honcho entries before full refresh."""
    stats = {"documents_fetched": 0, "conclusions_fetched": 0, "entries_created": 0, "entries_updated": 0}

    # Inactivate old Honcho entries (full refresh strategy)
    inactivated = store.delete_entries_by_source("honcho_api/")
    stats["old_entries_inactivated"] = inactivated

    # 1. Fetch documents (observations)
    logger.info(f"Fetching Honcho documents from {base_url}/workspaces/{workspace}")
    docs = fetch_honcho_documents(base_url, workspace)
    stats["documents_fetched"] = len(docs)

    doc_entries = []
    for doc in docs:
        entry = honcho_doc_to_entry(doc, profile)
        if entry:
            doc_entries.append(entry)

    # 2. Fetch conclusions
    logger.info(f"Fetching Honcho conclusions from {base_url}/workspaces/{workspace}")
    concs = fetch_honcho_conclusions(base_url, workspace)
    stats["conclusions_fetched"] = len(concs)

    conc_entries = []
    for conc in concs:
        entry = honcho_conclusion_to_entry(conc, profile)
        if entry:
            conc_entries.append(entry)

    # Bulk upsert with source_type to prevent cross-type inactivation
    all_honcho = doc_entries + conc_entries
    if all_honcho:
        result = store.bulk_upsert(all_honcho, source_type="honcho_obs")
        stats["entries_created"] = result["added"]
        stats["entries_updated"] = result["updated"]

    logger.info(f"  Honcho sync: {stats}")
    return stats