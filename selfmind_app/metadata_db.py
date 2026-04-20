"""SQLite metadata database for SelfMind V2 memory management."""

import hashlib
import json
import math
import os
import re
import sqlite3
from datetime import datetime, timedelta

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memory_meta (
    id TEXT PRIMARY KEY,
    content_hash TEXT UNIQUE,
    source TEXT,
    category TEXT,
    subcategory TEXT,
    created_at DATETIME,
    last_accessed DATETIME,
    access_count INTEGER DEFAULT 0,
    importance REAL DEFAULT 0.5,
    decay_score REAL DEFAULT 1.0,
    status TEXT DEFAULT 'active',
    pinned BOOLEAN DEFAULT 0,
    content_preview TEXT
);

CREATE TABLE IF NOT EXISTS operations_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME,
    operation TEXT,
    target_ids TEXT,
    before_snapshot TEXT,
    after_snapshot TEXT,
    auto_or_manual TEXT,
    confirmed BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME,
    memory_md TEXT,
    user_md TEXT,
    trigger TEXT
);
"""

TAG_RE = re.compile(r'\[(\w+)(?:/(\w+))?(?:/(\w+))?\]')


class MetadataDB:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def _now(self):
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def _hash(self, content):
        return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

    def _parse_entries(self, filepath, source):
        """Parse a memory file into list of (content, source, category, subcategory)."""
        if not os.path.exists(filepath):
            return []
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()
        parts = raw.split("§")
        entries = []
        for part in parts:
            text = part.strip()
            if not text:
                continue
            category = subcategory = None
            m = TAG_RE.search(text)
            if m:
                category = m.group(1)
                subcategory = m.group(2)
            entries.append((text, source, category, subcategory))
        return entries

    def sync_from_memory_files(self, memory_md_path, user_md_path=None):
        """Parse memory files and sync metadata. Returns stats dict."""
        entries = self._parse_entries(memory_md_path, "memory")
        if user_md_path:
            entries.extend(self._parse_entries(user_md_path, "user"))

        now = self._now()
        existing = {}
        for row in self.conn.execute("SELECT id, content_hash, status FROM memory_meta"):
            existing[row["content_hash"]] = (row["id"], row["status"])

        new_hashes = set()
        added = updated = 0

        for idx, (text, source, category, subcategory) in enumerate(entries):
            h = self._hash(text)
            new_hashes.add(h)
            entry_id = f"{source[:3]}_{idx+1:03d}"
            preview = text[:100].replace("\n", " ")

            if h in existing:
                # Already exists, skip
                continue
            else:
                # Check if this ID slot exists with different content (updated)
                row = self.conn.execute("SELECT id FROM memory_meta WHERE id = ?", (entry_id,)).fetchone()
                if row:
                    self.conn.execute(
                        "UPDATE memory_meta SET content_hash=?, category=?, subcategory=?, "
                        "content_preview=?, source=? WHERE id=?",
                        (h, category, subcategory, preview, source, entry_id)
                    )
                    updated += 1
                else:
                    self.conn.execute(
                        "INSERT INTO memory_meta (id, content_hash, source, category, subcategory, "
                        "created_at, last_accessed, access_count, importance, decay_score, status, pinned, content_preview) "
                        "VALUES (?,?,?,?,?,?,?,0,0.5,1.0,'active',0,?)",
                        (entry_id, h, source, category, subcategory, now, now, preview)
                    )
                    added += 1

        # Mark deleted entries (hash no longer present and not pinned)
        deleted = 0
        for h, (eid, status) in existing.items():
            if h not in new_hashes and status == "active":
                self.conn.execute(
                    "UPDATE memory_meta SET status='deleted' WHERE content_hash=? AND pinned=0",
                    (h,)
                )
                deleted += 1

        self.conn.commit()
        return {"added": added, "updated": updated, "deleted": deleted, "total_parsed": len(entries)}

    def get_all_entries(self, status=None):
        if status:
            rows = self.conn.execute("SELECT * FROM memory_meta WHERE status=? ORDER BY id", (status,)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM memory_meta ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def get_entry(self, entry_id):
        row = self.conn.execute("SELECT * FROM memory_meta WHERE id=?", (entry_id,)).fetchone()
        return dict(row) if row else None

    def update_entry(self, entry_id, **kwargs):
        allowed = {"category", "subcategory", "importance", "status", "pinned", "decay_score", "content_preview"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        sets = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [entry_id]
        self.conn.execute(f"UPDATE memory_meta SET {sets} WHERE id=?", vals)
        self.conn.commit()
        return True

    def pin_entry(self, entry_id):
        self.conn.execute("UPDATE memory_meta SET pinned=1 WHERE id=?", (entry_id,))
        self.conn.commit()
        self.log_operation("pin", [entry_id], None, None, "manual")

    def unpin_entry(self, entry_id):
        self.conn.execute("UPDATE memory_meta SET pinned=0 WHERE id=?", (entry_id,))
        self.conn.commit()
        self.log_operation("unpin", [entry_id], None, None, "manual")

    def record_access(self, content_hash):
        now = self._now()
        self.conn.execute(
            "UPDATE memory_meta SET access_count=access_count+1, last_accessed=? WHERE content_hash=?",
            (now, content_hash)
        )
        self.conn.commit()

    def create_snapshot(self, memory_md_content, user_md_content, trigger="manual"):
        now = self._now()
        self.conn.execute(
            "INSERT INTO snapshots (timestamp, memory_md, user_md, trigger) VALUES (?,?,?,?)",
            (now, memory_md_content, user_md_content, trigger)
        )
        self.conn.commit()
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_snapshots(self, limit=10):
        rows = self.conn.execute(
            "SELECT id, timestamp, trigger, length(memory_md) as memory_size, length(user_md) as user_size "
            "FROM snapshots ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def restore_snapshot(self, snapshot_id):
        row = self.conn.execute("SELECT * FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
        if not row:
            return None
        return {"memory_md": row["memory_md"], "user_md": row["user_md"],
                "timestamp": row["timestamp"], "trigger": row["trigger"]}

    def log_operation(self, operation, target_ids, before, after, auto_or_manual="manual"):
        now = self._now()
        self.conn.execute(
            "INSERT INTO operations_log (timestamp, operation, target_ids, before_snapshot, after_snapshot, auto_or_manual) "
            "VALUES (?,?,?,?,?,?)",
            (now, operation, json.dumps(target_ids), before, after, auto_or_manual)
        )
        self.conn.commit()

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
            result.append(d)
        return result

    def compute_decay_scores(self):
        """Recalculate decay scores for all active entries."""
        rows = self.conn.execute(
            "SELECT id, access_count, last_accessed, importance FROM memory_meta WHERE status='active'"
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
            decay = r["importance"] * (freq * recency)
            decay = max(0.0, min(1.0, decay))
            self.conn.execute("UPDATE memory_meta SET decay_score=? WHERE id=?", (round(decay, 4), r["id"]))
            updated += 1

        self.conn.commit()
        return updated

    def get_health_stats(self):
        stats = {}
        # Counts by status
        rows = self.conn.execute(
            "SELECT status, COUNT(*) as cnt FROM memory_meta GROUP BY status"
        ).fetchall()
        by_status = {r["status"]: r["cnt"] for r in rows}
        stats["by_status"] = by_status
        stats["total"] = sum(by_status.values())

        # Avg decay
        row = self.conn.execute(
            "SELECT AVG(decay_score) as avg_decay FROM memory_meta WHERE status='active'"
        ).fetchone()
        stats["avg_decay"] = round(row["avg_decay"] or 0, 4)

        # Pinned count
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM memory_meta WHERE pinned=1").fetchone()
        stats["pinned"] = row["cnt"]

        # Low decay (fading candidates)
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM memory_meta WHERE status='active' AND decay_score < 0.1 AND pinned=0"
        ).fetchone()
        stats["fading_candidates"] = row["cnt"]

        # Snapshot count
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM snapshots").fetchone()
        stats["snapshots"] = row["cnt"]

        # Redundancy hints: entries with same preview
        rows = self.conn.execute(
            "SELECT content_preview, COUNT(*) as cnt FROM memory_meta "
            "WHERE status='active' GROUP BY content_preview HAVING cnt > 1"
        ).fetchall()
        stats["potential_duplicates"] = len(rows)

        return stats

    def close(self):
        self.conn.close()
