"""Unified data store for SelfMind — single SQLite-based source of truth.

Core principle: SelfMind records EVOLUTION, not just current state.
- Entries that disappear from source files become "inactive" (NOT deleted)
- Content changes create new versions, old versions preserved as history
- Every sync creates a snapshot of source files for temporal queries
- operations_log tracks all changes with before/after state

All data sources (memory files, wiki pages, Honcho observations/conclusions)
write into one `entries` table. All consumers (graph, health, stats, wiki) read from it.
"""

import hashlib
import json
import math
import os
import re
import sqlite3
from datetime import datetime, timedelta


# ────────────────────────────────────────────────────────────
# Schema: entries table (unified) + supporting tables
# ────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    id TEXT PRIMARY KEY,                       -- deterministic: type:source:sha256[:8]
    content_hash TEXT NOT NULL,                -- SHA256 full for dedup
    content TEXT NOT NULL,                     -- full text
    content_preview TEXT,                      -- first 120 chars for display
    type TEXT NOT NULL DEFAULT 'memory',       -- memory/wiki/honcho_obs/honcho_conc/skill
    source TEXT NOT NULL,                      -- file path or API endpoint
    source_profile TEXT DEFAULT 'hermes',      -- config profile name

    -- Classification (from parser TAXONOMY or Honcho metadata)
    primary_cat TEXT,                          -- e.g. autobiographical, semantic
    secondary_cat TEXT,                        -- e.g. identity, domain
    label TEXT,                                -- short display label
    tags TEXT DEFAULT '[]',                    -- JSON array of tags

    -- Honcho-specific fields
    observer TEXT,                             -- who observed (e.g. liuxiaocheng)
    observed TEXT,                             -- who was observed (e.g. hermes)
    honcho_level TEXT,                         -- explicit/inductive/deductive/contradiction
    honcho_doc_id TEXT,                        -- Honcho document ID

    -- Lifecycle management (evolution-aware)
    importance REAL DEFAULT 0.5,
    decay_score REAL DEFAULT 0.25,             -- base vitality for new entries
    access_count INTEGER DEFAULT 0,
    version INTEGER DEFAULT 1,                 -- incremented on content changes
    first_seen_at TEXT,                        -- when this content first appeared
    created_at TEXT,                           -- when this DB row was created
    updated_at TEXT,                           -- last field update
    last_accessed TEXT,
    last_synced_at TEXT,                       -- last time source confirmed this entry exists
    status TEXT DEFAULT 'active',              -- active/inactive/archived (NOT deleted!)
    pinned INTEGER DEFAULT 0
);

-- History table: records content changes over time
CREATE TABLE IF NOT EXISTS entry_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL,                    -- references entries.id
    version INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    content TEXT NOT NULL,
    content_preview TEXT,
    primary_cat TEXT,
    secondary_cat TEXT,
    label TEXT,
    tags TEXT,
    timestamp TEXT NOT NULL,                  -- when this version was recorded
    trigger TEXT DEFAULT 'sync',              -- sync/manual/edit
    FOREIGN KEY (entry_id) REFERENCES entries(id)
);

-- Snapshot table: full source file content at each sync point
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    memory_md TEXT,                            -- full MEMORY.md content at this point
    user_md TEXT,                              -- full USER.md content at this point
    trigger TEXT DEFAULT 'sync',               -- sync/manual/startup
    stats TEXT                                 -- JSON: {added, updated, inactive, total}
);

-- Operations log: tracks all mutations
CREATE TABLE IF NOT EXISTS operations_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    operation TEXT NOT NULL,                   -- add/update/inactivate/archive/pin/unpin/version_change
    target_ids TEXT,                           -- JSON array of entry IDs
    detail TEXT,                               -- JSON: {before, after, reason}
    auto_or_manual TEXT DEFAULT 'auto'
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_entries_type ON entries(type);
CREATE INDEX IF NOT EXISTS idx_entries_status ON entries(status);
CREATE INDEX IF NOT EXISTS idx_entries_primary ON entries(primary_cat);
CREATE INDEX IF NOT EXISTS idx_entries_source ON entries(source);
CREATE INDEX IF NOT EXISTS idx_entries_content_hash ON entries(content_hash);
CREATE INDEX IF NOT EXISTS idx_entries_observer ON entries(observer);
CREATE INDEX IF NOT EXISTS idx_entries_honcho_level ON entries(honcho_level);
CREATE INDEX IF NOT EXISTS idx_history_entry ON entry_history(entry_id);
CREATE INDEX IF NOT EXISTS idx_history_timestamp ON entry_history(timestamp);
"""


TAG_RE = re.compile(r'\[(\w+)(?:/(\w+))?(?:/(\w+))?]')


class UnifiedStore:
    """Single-source-of-truth data store for SelfMind — evolution-aware."""

    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def _now(self):
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def _hash(self, content):
        return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

    def _stable_id(self, content, type_val="memory", source=""):
        """Deterministic ID: type + source_prefix + sha256[:8].
        This makes IDs predictable across syncs while staying unique."""
        raw = f"{type_val}:{source}:{content.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]

    # ──────────────── Write operations ────────────────

    def upsert_entry(self, **kwargs) -> str:
        """Insert or update an entry. Returns the entry ID.
        If content changed from existing entry, creates a history record."""
        content = kwargs.get("content", "")
        if not content or len(content.strip()) < 5:
            return None

        content = content.strip()
        content_hash = self._hash(content)
        type_val = kwargs.get("type", "memory")
        source = kwargs.get("source", "")
        entry_id = self._stable_id(content, type_val, source)
        now = self._now()

        preview = content[:120].replace("\n", " ")

        # Check if exists by content_hash
        existing = self.conn.execute(
            "SELECT id, status, version, content_hash FROM entries WHERE content_hash=?",
            (content_hash,)
        ).fetchone()

        if existing:
            # Same content already exists — just refresh sync timestamp
            self.conn.execute(
                "UPDATE entries SET last_synced_at=?, updated_at=? WHERE content_hash=?",
                (now, now, content_hash)
            )
            # If it was inactive, reactivate it (content reappeared in source)
            if existing["status"] == "inactive":
                self.conn.execute(
                    "UPDATE entries SET status='active', last_synced_at=?, updated_at=? WHERE content_hash=?",
                    (now, now, content_hash)
                )
                self._log_op("reactivate", [existing["id"]],
                             {"status": "inactive"}, {"status": "active"})
            self.conn.commit()
            return existing["id"]

        # Check if ID exists with DIFFERENT content (content evolved)
        existing_by_id = self.conn.execute(
            "SELECT * FROM entries WHERE id=?",
            (entry_id,)
        ).fetchone()

        if existing_by_id and existing_by_id["content_hash"] != content_hash:
            # Content changed — record old version in history, then update
            old_version = existing_by_id["version"]
            new_version = old_version + 1
            self._record_history(existing_by_id, trigger=kwargs.get("_trigger", "sync"))
            # Update entry with new content
            update_fields = {
                "content": content,
                "content_hash": content_hash,
                "content_preview": preview,
                "version": new_version,
                "updated_at": now,
                "last_synced_at": now,
                "status": "active",  # reactivate if was inactive
            }
            for field in ("primary_cat", "secondary_cat", "label", "type",
                         "source", "source_profile", "observer", "observed",
                         "honcho_level", "honcho_doc_id", "tags", "importance"):
                if field in kwargs and kwargs[field] is not None:
                    update_fields[field] = kwargs[field]
            sets = ", ".join(f"{k}=?" for k in update_fields)
            vals = list(update_fields.values()) + [entry_id]
            self.conn.execute(f"UPDATE entries SET {sets} WHERE id=?", vals)
            self._log_op("version_change", [entry_id],
                         {"version": old_version, "content_hash": existing_by_id["content_hash"]},
                         {"version": new_version, "content_hash": content_hash})
            self.conn.commit()
            return entry_id

        # New entry — never seen before
        self.conn.execute(
            """INSERT INTO entries (
                id, content_hash, content, content_preview, type, source, source_profile,
                primary_cat, secondary_cat, label, tags,
                observer, observed, honcho_level, honcho_doc_id,
                importance, decay_score, access_count, version,
                first_seen_at, created_at, updated_at, last_accessed, last_synced_at, status, pinned
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                entry_id, content_hash, content, preview,
                type_val, source, kwargs.get("source_profile", "hermes"),
                kwargs.get("primary_cat"), kwargs.get("secondary_cat"),
                kwargs.get("label", preview[:20]),
                kwargs.get("tags", "[]"),
                kwargs.get("observer"), kwargs.get("observed"),
                kwargs.get("honcho_level"), kwargs.get("honcho_doc_id"),
                kwargs.get("importance", 0.5), kwargs.get("decay_score", 0.25),
                0, 1,  # version 1 for new entries
                now, now, now, now, now,
                "active", 0,
            )
        )
        self._log_op("add", [entry_id], None, {"type": type_val, "source": source})
        self.conn.commit()
        return entry_id

    def bulk_upsert(self, entries: list[dict], source_type: str = None) -> dict:
        """Bulk insert/update entries. EVOLUTION-AWARE:
        - Entries present in batch: upserted (updated or added)
        - Entries NOT in batch but in DB of same type: marked 'inactive' (NOT deleted!)
        - Reactivates entries that reappear in source after being inactive

        source_type: if specified, only marks inactive entries of this type.
        """
        added = updated = reactivated = version_changed = skipped = inactivated = 0
        now = self._now()

        # Collect all content hashes from this batch, grouped by type
        batch_by_type = {}  # type -> {content_hash: entry_dict}
        for entry in entries:
            content = entry.get("content", "")
            if not content or len(content.strip()) < 5:
                skipped += 1
                continue
            content = content.strip()
            content_hash = self._hash(content)
            t = entry.get("type", "memory")
            if t not in batch_by_type:
                batch_by_type[t] = {}
            batch_by_type[t][content_hash] = entry

        # Determine which types to check for inactivation
        # Only inactivate within the same type group
        if source_type:
            check_types = {source_type}
        else:
            check_types = set(batch_by_type.keys())

        # Process each entry in the batch
        for t, hash_map in batch_by_type.items():
            for content_hash, entry in hash_map.items():
                existing = self.conn.execute(
                    "SELECT id, status, version, content_hash FROM entries WHERE content_hash=?",
                    (content_hash,)
                ).fetchone()

                if existing:
                    # Content already exists in DB — refresh sync timestamp
                    if existing["status"] == "inactive":
                        # Reactivate — content reappeared in source!
                        self.conn.execute(
                            "UPDATE entries SET status='active', last_synced_at=?, updated_at=? WHERE content_hash=?",
                            (now, now, content_hash)
                        )
                        reactivated += 1
                        self._log_op("reactivate", [existing["id"]],
                                     {"status": "inactive"}, {"status": "active"})
                    else:
                        # Already active — just refresh timestamps
                        # Update classification fields if provided
                        update_fields = {"last_synced_at": now, "updated_at": now}
                        for field in ("primary_cat", "secondary_cat", "label",
                                     "source", "source_profile", "observer", "observed",
                                     "honcho_level", "honcho_doc_id", "tags", "importance"):
                            if field in entry and entry[field] is not None:
                                update_fields[field] = entry[field]
                        sets = ", ".join(f"{k}=?" for k in update_fields)
                        vals = list(update_fields.values()) + [content_hash]
                        self.conn.execute(f"UPDATE entries SET {sets} WHERE content_hash=?", vals)
                        updated += 1
                else:
                    # New content — check if ID exists with different content (version evolution)
                    type_val = entry.get("type", "memory")
                    source = entry.get("source", "")
                    entry_id = self._stable_id(content, type_val, source)
                    existing_by_id = self.conn.execute(
                        "SELECT * FROM entries WHERE id=?",
                        (entry_id,)
                    ).fetchone()

                    if existing_by_id and existing_by_id["content_hash"] != content_hash:
                        # Same ID but different content = content evolved
                        old_version = existing_by_id["version"]
                        new_version = old_version + 1
                        self._record_history(existing_by_id, trigger="sync")
                        update_fields = {
                            "content": entry.get("content", "").strip(),
                            "content_hash": content_hash,
                            "content_preview": entry.get("content", "").strip()[:120].replace("\n", " "),
                            "version": new_version,
                            "status": "active",
                            "last_synced_at": now,
                            "updated_at": now,
                        }
                        for field in ("primary_cat", "secondary_cat", "label", "type",
                                     "source", "source_profile", "observer", "observed",
                                     "honcho_level", "honcho_doc_id", "tags", "importance"):
                            if field in entry and entry[field] is not None:
                                update_fields[field] = entry[field]
                        sets = ", ".join(f"{k}=?" for k in update_fields)
                        vals = list(update_fields.values()) + [entry_id]
                        self.conn.execute(f"UPDATE entries SET {sets} WHERE id=?", vals)
                        version_changed += 1
                        self._log_op("version_change", [entry_id],
                                     {"version": old_version}, {"version": new_version})
                    else:
                        # Brand new entry
                        preview = entry.get("content", "").strip()[:120].replace("\n", " ")
                        self.conn.execute(
                            """INSERT INTO entries (
                                id, content_hash, content, content_preview, type, source, source_profile,
                                primary_cat, secondary_cat, label, tags,
                                observer, observed, honcho_level, honcho_doc_id,
                                importance, decay_score, access_count, version,
                                first_seen_at, created_at, updated_at, last_accessed, last_synced_at, status, pinned
                            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (
                                entry_id, content_hash, entry.get("content", "").strip(), preview,
                                entry.get("type", "memory"), entry.get("source", ""),
                                entry.get("source_profile", "hermes"),
                                entry.get("primary_cat"), entry.get("secondary_cat"),
                                entry.get("label", preview[:20]),
                                entry.get("tags", "[]"),
                                entry.get("observer"), entry.get("observed"),
                                entry.get("honcho_level"), entry.get("honcho_doc_id"),
                                entry.get("importance", 0.5), entry.get("decay_score", 0.25),
                                0, 1, now, now, now, now, now, "active", 0,
                            )
                        )
                        added += 1

        # Mark entries NOT in batch as 'inactive' (they disappeared from source)
        # Only within the same type group — never cross-type
        for t in check_types:
            batch_hashes = set(batch_by_type.get(t, {}).keys())
            for row in self.conn.execute(
                "SELECT id, content_hash, status, pinned FROM entries WHERE type=? AND status='active'",
                (t,)
            ):
                if row["content_hash"] not in batch_hashes and not row["pinned"]:
                    self.conn.execute(
                        "UPDATE entries SET status='inactive', updated_at=? WHERE id=?",
                        (now, row["id"])
                    )
                    inactivated += 1
                    self._log_op("inactivate", [row["id"]],
                                 {"status": "active"}, {"status": "inactive"},
                                 reason="disappeared_from_source")

        self.conn.commit()
        return {
            "added": added, "updated": updated, "reactivated": reactivated,
            "version_changed": version_changed, "inactivated": inactivated, "skipped": skipped
        }

    def delete_entries_by_source(self, source_prefix: str) -> int:
        """Mark entries from a specific source as 'inactive'.
        Physical deletion only for Honcho API data (full refresh strategy)."""
        count = 0
        for row in self.conn.execute(
            "SELECT id FROM entries WHERE source LIKE ? AND pinned=0 AND status='active'",
            (f"{source_prefix}%",)
        ):
            self.conn.execute("UPDATE entries SET status='inactive', updated_at=? WHERE id=?",
                              (self._now(), row["id"]))
            count += 1
        self.conn.commit()
        return count

    # ──────────────── Read operations ────────────────

    def get_all_entries(self, status=None, type=None):
        """Get entries filtered by status and/or type."""
        query = "SELECT * FROM entries"
        conditions = []
        params = []
        if status:
            conditions.append("status=?")
            params.append(status)
        if type:
            conditions.append("type=?")
            params.append(type)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_entry(self, entry_id):
        row = self.conn.execute("SELECT * FROM entries WHERE id=?", (entry_id,)).fetchone()
        return dict(row) if row else None

    def get_entries_by_type(self, type_val, status="active"):
        rows = self.conn.execute(
            "SELECT * FROM entries WHERE type=? AND status=? ORDER BY created_at DESC",
            (type_val, status)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_entry_history(self, entry_id, limit=20):
        """Get version history for an entry."""
        rows = self.conn.execute(
            "SELECT * FROM entry_history WHERE entry_id=? ORDER BY version DESC LIMIT ?",
            (entry_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self):
        """Compute comprehensive stats across all entry types."""
        stats = {}

        # Counts by type and status
        rows = self.conn.execute(
            "SELECT type, status, COUNT(*) as cnt FROM entries GROUP BY type, status"
        ).fetchall()
        by_type_status = {}
        for r in rows:
            key = f"{r['type']}_{r['status']}"
            by_type_status[key] = r["cnt"]
        stats["by_type_status"] = by_type_status

        # Total active
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM entries WHERE status='active'").fetchone()
        stats["total_active"] = row["cnt"]

        # Total inactive (evolution history)
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM entries WHERE status='inactive'").fetchone()
        stats["total_inactive"] = row["cnt"]

        # Counts by type (active only)
        rows = self.conn.execute(
            "SELECT type, COUNT(*) as cnt FROM entries WHERE status='active' GROUP BY type"
        ).fetchall()
        stats["by_type"] = {r["type"]: r["cnt"] for r in rows}

        # Avg decay (memory type only)
        row = self.conn.execute(
            "SELECT AVG(decay_score) as avg_decay FROM entries WHERE status='active' AND type='memory'"
        ).fetchone()
        stats["avg_decay"] = round(row["avg_decay"] or 0, 4)

        # Pinned count
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM entries WHERE pinned=1").fetchone()
        stats["pinned"] = row["cnt"]

        # Fading candidates
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM entries WHERE status='active' AND type='memory' AND decay_score < 0.2 AND pinned=0"
        ).fetchone()
        stats["fading_candidates"] = row["cnt"]

        # Version changes count
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM entry_history").fetchone()
        stats["version_changes"] = row["cnt"]

        # Snapshot count
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM snapshots").fetchone()
        stats["snapshots"] = row["cnt"]

        return stats

    # ──────────────── Lifecycle operations ────────────────

    def update_entry(self, entry_id, **kwargs):
        allowed = {"primary_cat", "secondary_cat", "importance", "status",
                   "pinned", "decay_score", "content_preview", "label", "tags"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        sets = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [entry_id]
        self.conn.execute(f"UPDATE entries SET {sets} WHERE id=?", vals)
        self.conn.commit()
        return True

    def pin_entry(self, entry_id):
        self.conn.execute("UPDATE entries SET pinned=1 WHERE id=?", (entry_id,))
        self.conn.commit()
        self._log_op("pin", [entry_id], {"pinned": 0}, {"pinned": 1}, auto_or_manual="manual")

    def unpin_entry(self, entry_id):
        self.conn.execute("UPDATE entries SET pinned=0 WHERE id=?", (entry_id,))
        self.conn.commit()
        self._log_op("unpin", [entry_id], {"pinned": 1}, {"pinned": 0}, auto_or_manual="manual")

    def record_access(self, content_hash):
        now = self._now()
        self.conn.execute(
            "UPDATE entries SET access_count=access_count+1, last_accessed=? WHERE content_hash=?",
            (now, content_hash)
        )
        self.conn.commit()

    def compute_decay_scores(self):
        """Recalculate decay scores for active memory entries."""
        rows = self.conn.execute(
            "SELECT id, access_count, last_accessed, importance FROM entries WHERE status='active' AND type='memory'"
        ).fetchall()
        if not rows:
            return 0

        max_ac = max(r["access_count"] for r in rows) or 1
        now = datetime.now()
        updated = 0

        for r in rows:
            la = r["last_accessed"]
            try:
                last = datetime.strptime(la, "%Y-%m-%dT%H:%M:%S")
            except (ValueError, TypeError):
                last = now
            days = max((now - last).total_seconds() / 86400, 0)
            recency = math.exp(-0.05 * days)
            freq = math.log(1 + r["access_count"]) / math.log(1 + max_ac) if max_ac > 0 else 0
            decay = r["importance"] * (0.5 + 0.5 * freq * recency)
            decay = max(0.0, min(1.0, decay))
            self.conn.execute("UPDATE entries SET decay_score=? WHERE id=?", (round(decay, 4), r["id"]))
            updated += 1

        self.conn.commit()
        return updated

    # ──────────────── History & Snapshot ────────────────

    def _record_history(self, existing_row, trigger="sync"):
        """Record current state of an entry into history before it changes."""
        self.conn.execute(
            """INSERT INTO entry_history (
                entry_id, version, content_hash, content, content_preview,
                primary_cat, secondary_cat, label, tags, timestamp, trigger
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                existing_row["id"], existing_row["version"],
                existing_row["content_hash"], existing_row["content"],
                existing_row["content_preview"],
                existing_row["primary_cat"], existing_row["secondary_cat"],
                existing_row["label"], existing_row["tags"],
                self._now(), trigger,
            )
        )
        self.conn.commit()

    def create_snapshot(self, memory_md_content, user_md_content, trigger="sync", stats=None):
        """Save full source file content for temporal comparison."""
        now = self._now()
        self.conn.execute(
            "INSERT INTO snapshots (timestamp, memory_md, user_md, trigger, stats) VALUES (?,?,?,?,?)",
            (now, memory_md_content, user_md_content, trigger,
             json.dumps(stats) if stats else None)
        )
        self.conn.commit()
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_snapshots(self, limit=10):
        rows = self.conn.execute(
            "SELECT id, timestamp, trigger, length(memory_md) as memory_size, "
            "length(user_md) as user_size, stats FROM snapshots ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d["stats"]:
                try:
                    d["stats"] = json.loads(d["stats"])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(d)
        return result

    def restore_snapshot(self, snapshot_id):
        row = self.conn.execute("SELECT * FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
        if not row:
            return None
        return {"memory_md": row["memory_md"], "user_md": row["user_md"],
                "timestamp": row["timestamp"], "trigger": row["trigger"]}

    def _log_op(self, operation, target_ids, before=None, after=None,
                reason=None, auto_or_manual="auto"):
        """Record an operation in the log."""
        now = self._now()
        detail = {
            "before": before or {},
            "after": after or {},
            "reason": reason or "",
        }
        self.conn.execute(
            "INSERT INTO operations_log (timestamp, operation, target_ids, detail, auto_or_manual) "
            "VALUES (?,?,?,?,?)",
            (now, operation, json.dumps(target_ids), json.dumps(detail), auto_or_manual)
        )
        # Don't commit here — let the caller commit when ready

    def get_operations_log(self, limit=50):
        rows = self.conn.execute(
            "SELECT * FROM operations_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["target_ids"] = json.loads(d["target_ids"]) if d["target_ids"] else []
            except (json.JSONDecodeError, TypeError):
                d["target_ids"] = []
            try:
                d["detail"] = json.loads(d["detail"]) if d["detail"] else {}
            except (json.JSONDecodeError, TypeError):
                d["detail"] = {}
            result.append(d)
        return result

    def get_evolution_summary(self, entry_id):
        """Get full evolution timeline for an entry: current state + all history versions."""
        current = self.get_entry(entry_id)
        if not current:
            return None
        history = self.get_entry_history(entry_id)
        return {"current": current, "history": history}

    # ──────────────── DNA: Agent Evolution Data ────────────────

    def get_dna_timeline(self):
        """Get DNA timeline data: entries grouped by date with evolution metrics.
        
        Returns:
            - timeline: list of {date, entries_created, entries_updated, avg_decay, by_type}
            - dna_entries: all active entries with 4 core DNA fields
            - categories: unique category combinations with counts and avg decay
            - evolution_events: all version changes and status transitions
        """
        # 1. Timeline: group by first_seen_at date
        rows = self.conn.execute(
            "SELECT id, type, primary_cat, secondary_cat, label, content_preview, "
            "importance, decay_score, version, first_seen_at, updated_at, status "
            "FROM entries ORDER BY first_seen_at ASC"
        ).fetchall()

        timeline = {}
        dna_entries = []
        categories = {}
        
        for r in rows:
            d = dict(r)
            date_key = d["first_seen_at"][:10] if d["first_seen_at"] else "unknown"
            
            # Timeline aggregation
            if date_key not in timeline:
                timeline[date_key] = {
                    "date": date_key,
                    "entries_created": 0,
                    "entries_updated": 0,
                    "avg_decay": 0,
                    "by_type": {},
                    "by_status": {},
                    "decay_values": [],
                }
            tl = timeline[date_key]
            tl["entries_created"] += 1
            if d["updated_at"] and d["updated_at"][:10] != date_key:
                tl["entries_updated"] += 1
            if d["decay_score"] is not None:
                tl["decay_values"].append(d["decay_score"])
            tl["by_type"][d["type"]] = tl["by_type"].get(d["type"], 0) + 1
            tl["by_status"][d["status"]] = tl["by_status"].get(d["status"], 0) + 1
            
            # DNA entries (4 core fields + classification)
            dna_entries.append({
                "id": d["id"],
                "type": d["type"],
                "primary_cat": d["primary_cat"],
                "secondary_cat": d["secondary_cat"],
                "label": d["label"] or (d["content_preview"][:40] if d["content_preview"] else ""),
                "content_preview": d["content_preview"],
                "importance": d["importance"] or 0.5,
                "decay_score": d["decay_score"] or 0.25,
                "version": d["version"] or 1,
                "first_seen_at": d["first_seen_at"],
                "updated_at": d["updated_at"],
                "status": d["status"],
            })
            
            # Categories
            cat_key = f"{d['primary_cat']}/{d['secondary_cat']}"
            if cat_key not in categories:
                categories[cat_key] = {"count": 0, "avg_decay": 0, "avg_importance": 0, "decay_values": [], "importance_values": []}
            categories[cat_key]["count"] += 1
            if d["decay_score"] is not None:
                categories[cat_key]["decay_values"].append(d["decay_score"])
            if d["importance"] is not None:
                categories[cat_key]["importance_values"].append(d["importance"])
        
        # Finalize timeline averages
        for tl in timeline.values():
            tl["avg_decay"] = round(sum(tl["decay_values"]) / len(tl["decay_values"]), 3) if tl["decay_values"] else 0
            del tl["decay_values"]
        
        # Finalize category averages
        for cat in categories.values():
            cat["avg_decay"] = round(sum(cat["decay_values"]) / len(cat["decay_values"]), 3) if cat["decay_values"] else 0
            cat["avg_importance"] = round(sum(cat["importance_values"]) / len(cat["importance_values"]), 3) if cat["importance_values"] else 0
            del cat["decay_values"]
            del cat["importance_values"]
        
        # 2. Evolution events: version changes + status transitions
        ops = self.conn.execute(
            "SELECT id, timestamp, operation, target_ids, detail, auto_or_manual "
            "FROM operations_log ORDER BY timestamp ASC"
        ).fetchall()
        
        evolution_events = []
        for op in ops:
            d = dict(op)
            try:
                d["target_ids"] = json.loads(d["target_ids"]) if d["target_ids"] else []
            except:
                d["target_ids"] = []
            try:
                d["detail"] = json.loads(d["detail"]) if d["detail"] else {}
            except:
                d["detail"] = {}
            evolution_events.append(d)
        
        # 3. History versions per entry (for detailed timeline)
        history_rows = self.conn.execute(
            "SELECT entry_id, version, content_preview, primary_cat, secondary_cat, "
            "label, timestamp, trigger FROM entry_history ORDER BY timestamp ASC"
        ).fetchall()
        
        entry_versions = {}
        for h in history_rows:
            d = dict(h)
            eid = d["entry_id"]
            if eid not in entry_versions:
                entry_versions[eid] = []
            entry_versions[eid].append(d)
        
        return {
            "timeline": sorted(timeline.values(), key=lambda x: x["date"]),
            "dna_entries": dna_entries,
            "categories": categories,
            "evolution_events": evolution_events,
            "entry_versions": entry_versions,
            "summary": {
                "total_entries": len(dna_entries),
                "active": len([e for e in dna_entries if e["status"] == "active"]),
                "inactive": len([e for e in dna_entries if e["status"] == "inactive"]),
                "avg_decay": round(sum(e["decay_score"] for e in dna_entries) / len(dna_entries), 3) if dna_entries else 0,
                "avg_version": round(sum(e["version"] for e in dna_entries) / len(dna_entries), 2) if dna_entries else 1,
                "total_evolutions": len(evolution_events),
            }
        }

    def close(self):
        self.conn.close()