"""SelfMind Analytics — Memory Access Frequency & Relationship Analysis

Scans Hermes conversation history (state.db) to compute:
  - access_count: how often each memory entry appears in conversations
  - co_occurrence: how often two memories appear in the same session
  - importance_score: composite score from priority level + access frequency

Acts as a read-only observer — never modifies state.db.
"""

import re
import sqlite3
from pathlib import Path


# ────────────────────────────────────────────────────────────────────
# 1. Database connection
# ────────────────────────────────────────────────────────────────────

def _find_state_db() -> Path | None:
    """Locate Hermes state.db — check HERMES_HOME env var first, then default."""
    import os
    hermes_home = os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
    db_path = Path(hermes_home) / "state.db"
    if db_path.exists() and db_path.stat().st_size > 0:
        return db_path
    return None


def _get_all_messages(db_path: Path) -> list[tuple[str, str]]:
    """Fetch all assistant+user messages as (session_id, content) pairs."""
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.execute(
            "SELECT session_id, content FROM messages "
            "WHERE role IN ('user', 'assistant') AND content IS NOT NULL "
            "ORDER BY session_id, timestamp"
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except (sqlite3.Error, OSError):
        return []


# ────────────────────────────────────────────────────────────────────
# 2. Access frequency analysis
# ────────────────────────────────────────────────────────────────────

def _build_search_patterns(entries: list[dict]) -> list[tuple[str, re.Pattern]]:
    """Build regex patterns for each memory entry.
    
    Uses the entry label and key phrases from description for matching.
    """
    patterns = []
    for entry in entries:
        node_id = entry.get("node_id", "")
        label = entry.get("label", "")
        
        # Skip very short labels (too generic)
        if len(label) < 3:
            continue
        
        # Escape for regex, case-insensitive
        escaped = re.escape(label)
        try:
            pat = re.compile(escaped, re.IGNORECASE)
            patterns.append((node_id, pat))
        except re.error:
            continue
    
    return patterns


def compute_access_counts(
    entries: list[dict],
    messages: list[tuple[str, str]],
) -> dict[str, int]:
    """Count how many messages reference each memory entry.
    
    Returns: {node_id: access_count}
    """
    patterns = _build_search_patterns(entries)
    counts: dict[str, int] = {e["node_id"]: 0 for e in entries}
    
    for _session_id, content in messages:
        if not content:
            continue
        for node_id, pat in patterns:
            if pat.search(content):
                counts[node_id] = counts.get(node_id, 0) + 1
    
    return counts


# ────────────────────────────────────────────────────────────────────
# 3. Co-occurrence analysis (session-level)
# ────────────────────────────────────────────────────────────────────

def compute_co_occurrences(
    entries: list[dict],
    messages: list[tuple[str, str]],
) -> dict[str, int]:
    """Count how often two memory entries appear in the same session.
    
    Returns: {"nodeA->nodeB": count} (sorted pair, so A < B)
    """
    patterns = _build_search_patterns(entries)
    
    # Group messages by session
    sessions: dict[str, str] = {}
    for session_id, content in messages:
        if content:
            sessions.setdefault(session_id, "")
            sessions[session_id] += " " + content
    
    # For each session, find which memories are mentioned
    co_counts: dict[str, int] = {}
    
    for _sid, session_text in sessions.items():
        mentioned = []
        for node_id, pat in patterns:
            if pat.search(session_text):
                mentioned.append(node_id)
        
        # Count pairwise co-occurrences
        for i in range(len(mentioned)):
            for j in range(i + 1, len(mentioned)):
                a, b = sorted([mentioned[i], mentioned[j]])
                key = f"{a}->{b}"
                co_counts[key] = co_counts.get(key, 0) + 1
    
    return co_counts


# ────────────────────────────────────────────────────────────────────
# 4. Importance scoring
# ────────────────────────────────────────────────────────────────────

# Priority weight from memory tag prefix
_PRIORITY_WEIGHTS = {
    "primary": 3.0,
    "secondary": 1.0,
}


def compute_importance(
    entries: list[dict],
    access_counts: dict[str, int],
) -> dict[str, float]:
    """Compute importance score for each memory entry.
    
    importance = priority_weight + log(1 + access_count) * frequency_weight
    
    Returns: {node_id: importance_score} normalized to 0.0–1.0
    """
    import math
    
    raw_scores: dict[str, float] = {}
    
    for entry in entries:
        node_id = entry["node_id"]
        text = entry.get("text", "")
        
        # Determine priority from tag
        priority_weight = 1.0
        tag_match = re.search(r"\[(primary|secondary)/", text)
        if tag_match:
            priority_weight = _PRIORITY_WEIGHTS.get(tag_match.group(1), 1.0)
        
        # Frequency component
        freq = access_counts.get(node_id, 0)
        freq_score = math.log1p(freq) * 2.0
        
        raw_scores[node_id] = priority_weight + freq_score
    
    # Normalize to 0.0–1.0
    if not raw_scores:
        return {}
    
    max_score = max(raw_scores.values()) or 1.0
    return {nid: score / max_score for nid, score in raw_scores.items()}


# ────────────────────────────────────────────────────────────────────
# 5. Main entry point
# ────────────────────────────────────────────────────────────────────

def analyze_memories(entries: list[dict]) -> dict:
    """Run full analytics on memory entries.
    
    Returns:
        {
            "access_counts": {node_id: int},
            "co_occurrences": {"nodeA->nodeB": int},
            "importance": {node_id: float (0-1)},
            "db_found": bool,
            "message_count": int,
            "session_count": int,
        }
    """
    db_path = _find_state_db()
    
    if not db_path:
        # No database — return defaults
        return {
            "access_counts": {e["node_id"]: 0 for e in entries},
            "co_occurrences": {},
            "importance": {e["node_id"]: 0.5 for e in entries},
            "db_found": False,
            "message_count": 0,
            "session_count": 0,
        }
    
    messages = _get_all_messages(db_path)
    
    # Count unique sessions
    session_ids = set(sid for sid, _ in messages)
    
    access_counts = compute_access_counts(entries, messages)
    co_occurrences = compute_co_occurrences(entries, messages)
    importance = compute_importance(entries, access_counts)
    
    return {
        "access_counts": access_counts,
        "co_occurrences": co_occurrences,
        "importance": importance,
        "db_found": True,
        "message_count": len(messages),
        "session_count": len(session_ids),
    }
