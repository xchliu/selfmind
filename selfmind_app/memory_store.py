"""SelfMind MemoryStore — Local JSON database for extracted memories.

Manages ~/Documents/selfmind/memories_store.json with CRUD operations
and sync support for external agent systems (Hermes, OpenClaw).

Thread-safe via fcntl file locking. Zero third-party dependencies.
"""

import fcntl
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────

SELFMIND_DIR = Path(__file__).resolve().parent.parent
STORE_FILE = SELFMIND_DIR / "memories_store.json"

VALID_STATUSES = {"pending", "approved", "synced", "rejected"}

ENTRY_FIELDS = {
    "id", "text", "label", "primary", "secondary", "description",
    "source_file", "status", "createdAt", "updatedAt", "syncedTo",
}

# Fields that callers should never overwrite via update_entry
IMMUTABLE_FIELDS = {"id", "createdAt"}


def _generate_id() -> str:
    """Generate a unique memory entry ID like mem_a1b2c3d4."""
    return "mem_" + uuid.uuid4().hex[:8]


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string (no timezone suffix)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


# ────────────────────────────────────────────────────────────────────
# MemoryStore
# ────────────────────────────────────────────────────────────────────

class MemoryStore:
    """File-backed JSON store for memory entries with thread-safe locking.

    Usage::

        store = MemoryStore()
        ids = store.add_entries([{"text": "...", "label": "hi", ...}])
        entries = store.get_entries({"status": "pending"})
        store.sync_to_hermes(ids, "~/.hermes")
    """

    def __init__(self, store_path: str | Path | None = None):
        self.store_path = Path(store_path) if store_path else STORE_FILE
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.store_path.exists():
            self._write_store({"entries": [], "meta": {"version": 1}})

    # ── File I/O with locking ──────────────────────────────────────

    def _read_store(self) -> dict:
        """Read the JSON store with a shared (read) lock."""
        with open(self.store_path, "r", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        return data

    def _write_store(self, data: dict) -> None:
        """Write the JSON store with an exclusive (write) lock.

        Uses write-to-temp + rename for atomicity.
        """
        tmp_path = self.store_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        os.replace(str(tmp_path), str(self.store_path))

    def _with_lock(self, fn):
        """Execute *fn(data)* under an exclusive lock, then save.

        ``fn`` receives the full store dict and can mutate it in place.
        Must return the value to be returned to the caller.
        """
        # Read → lock → mutate → write (all under exclusive lock)
        with open(self.store_path, "r+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                data = json.load(f)
                result = fn(data)
                f.seek(0)
                f.truncate()
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        return result

    # ── CRUD ───────────────────────────────────────────────────────

    def add_entries(self, entries: list[dict]) -> list[str]:
        """Add new memory entries. Returns list of generated IDs.

        Each entry dict should contain at minimum ``text``.
        Missing fields get sensible defaults.
        """
        now = _now_iso()
        new_ids: list[str] = []
        prepared: list[dict] = []

        for raw in entries:
            entry_id = _generate_id()
            entry = {
                "id": entry_id,
                "text": raw.get("text", ""),
                "label": raw.get("label", "")[:20],
                "primary": raw.get("primary", "working"),
                "secondary": raw.get("secondary", "active"),
                "description": raw.get("description", "")[:150],
                "source_file": raw.get("source_file", ""),
                "status": "pending",
                "createdAt": now,
                "updatedAt": now,
                "syncedTo": [],
            }
            prepared.append(entry)
            new_ids.append(entry_id)

        def _add(data: dict) -> list[str]:
            data["entries"].extend(prepared)
            return new_ids

        return self._with_lock(_add)

    def get_entries(self, filters: dict | None = None) -> list[dict]:
        """List entries with optional filters.

        Supported filter keys: ``status``, ``primary``, ``secondary``,
        ``source_file``.  Values can be a single string or list of strings.
        """
        data = self._read_store()
        entries = data.get("entries", [])

        if not filters:
            return entries

        def _match(entry: dict) -> bool:
            for key in ("status", "primary", "secondary", "source_file"):
                if key not in filters:
                    continue
                allowed = filters[key]
                if isinstance(allowed, str):
                    allowed = [allowed]
                if entry.get(key) not in allowed:
                    return False
            return True

        return [e for e in entries if _match(e)]

    def get_entry(self, entry_id: str) -> dict | None:
        """Get a single entry by ID, or None if not found."""
        data = self._read_store()
        for entry in data.get("entries", []):
            if entry["id"] == entry_id:
                return entry
        return None

    def update_entry(self, entry_id: str, updates: dict) -> dict | None:
        """Update fields on an existing entry. Returns updated entry or None."""
        now = _now_iso()

        def _update(data: dict) -> dict | None:
            for entry in data["entries"]:
                if entry["id"] == entry_id:
                    for key, value in updates.items():
                        if key in IMMUTABLE_FIELDS:
                            continue
                        if key == "label":
                            value = str(value)[:20]
                        elif key == "description":
                            value = str(value)[:150]
                        elif key == "status" and value not in VALID_STATUSES:
                            continue
                        entry[key] = value
                    entry["updatedAt"] = now
                    return dict(entry)
            return None

        return self._with_lock(_update)

    def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry by ID. Returns True if found and deleted."""
        def _delete(data: dict) -> bool:
            original_len = len(data["entries"])
            data["entries"] = [e for e in data["entries"] if e["id"] != entry_id]
            return len(data["entries"]) < original_len

        return self._with_lock(_delete)

    def bulk_update_status(self, entry_ids: list[str], status: str) -> int:
        """Set status on multiple entries at once. Returns count updated."""
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}")

        id_set = set(entry_ids)
        now = _now_iso()

        def _bulk(data: dict) -> int:
            count = 0
            for entry in data["entries"]:
                if entry["id"] in id_set:
                    entry["status"] = status
                    entry["updatedAt"] = now
                    count += 1
            return count

        return self._with_lock(_bulk)

    # ── Sync ───────────────────────────────────────────────────────

    def _write_to_memory_file(
        self,
        entries: list[dict],
        memory_file_path: str,
        separator: str = "§",
    ) -> int:
        """Append formatted entries to a MEMORY.md file.

        Format per entry (compatible with parser.py)::

            [primary/secondary] label: description text
            §

        Returns the number of entries written.
        """
        if not entries:
            return 0

        mem_path = Path(memory_file_path).expanduser()
        mem_path.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = []
        for entry in entries:
            primary = entry.get("primary", "working")
            secondary = entry.get("secondary", "active")
            label = entry.get("label", "")
            # Use full text if available, otherwise fall back to description
            text = entry.get("text", entry.get("description", ""))
            # Build the formatted line: [primary/secondary] label: text
            formatted = f"[{primary}/{secondary}] {label}: {text}"
            lines.append(formatted)

        # Build the block to append
        block_parts: list[str] = []
        for line in lines:
            block_parts.append(line)
            block_parts.append(separator)

        block = "\n".join(block_parts) + "\n"

        # Append to file (create if needed)
        existing = ""
        if mem_path.exists():
            existing = mem_path.read_text(encoding="utf-8")

        # Ensure we start on a new line after existing content
        if existing and not existing.endswith("\n"):
            block = "\n" + block

        with open(mem_path, "a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(block)
                f.flush()
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

        return len(entries)

    def _sync_entries(
        self,
        entry_ids: list[str],
        agent_home: str,
        agent_name: str,
    ) -> dict:
        """Core sync logic shared by sync_to_hermes / sync_to_openclaw.

        Only syncs entries whose status is 'approved'. Updates their status
        to 'synced' and records the agent name in ``syncedTo``.

        Returns a summary dict::

            {"synced": 3, "skipped": 1, "errors": [], "agent": "hermes"}
        """
        home = Path(agent_home).expanduser()
        memory_file = home / "memories" / "MEMORY.md"

        data = self._read_store()
        id_set = set(entry_ids)

        to_sync: list[dict] = []
        skipped = 0

        for entry in data.get("entries", []):
            if entry["id"] not in id_set:
                continue
            if entry["status"] != "approved":
                skipped += 1
                continue
            to_sync.append(entry)

        errors: list[str] = []
        written = 0

        if to_sync:
            try:
                written = self._write_to_memory_file(to_sync, str(memory_file), "§")
            except OSError as exc:
                errors.append(f"Failed to write {memory_file}: {exc}")
                written = 0

        # Update status and syncedTo for successfully written entries
        if written > 0:
            now = _now_iso()
            synced_ids = {e["id"] for e in to_sync[:written]}

            def _mark_synced(store_data: dict) -> None:
                for entry in store_data["entries"]:
                    if entry["id"] in synced_ids:
                        entry["status"] = "synced"
                        entry["updatedAt"] = now
                        if agent_name not in entry.get("syncedTo", []):
                            entry.setdefault("syncedTo", []).append(agent_name)

            self._with_lock(_mark_synced)

        return {
            "synced": written,
            "skipped": skipped,
            "errors": errors,
            "agent": agent_name,
        }

    def sync_to_hermes(self, entry_ids: list[str], hermes_home: str) -> dict:
        """Sync approved entries to Hermes MEMORY.md file.

        Args:
            entry_ids: IDs of entries to sync.
            hermes_home: Hermes home directory (e.g. ``~/.hermes``).

        Returns:
            Summary dict with synced/skipped counts and any errors.
        """
        return self._sync_entries(entry_ids, hermes_home, "hermes")

    def sync_to_openclaw(self, entry_ids: list[str], openclaw_home: str) -> dict:
        """Sync approved entries to OpenClaw MEMORY.md file.

        Args:
            entry_ids: IDs of entries to sync.
            openclaw_home: OpenClaw home directory (e.g. ``~/.openclaw``).

        Returns:
            Summary dict with synced/skipped counts and any errors.
        """
        return self._sync_entries(entry_ids, openclaw_home, "openclaw")

    # ── Stats ──────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return aggregate statistics about the store.

        Returns::

            {
                "total": 42,
                "by_status": {"pending": 10, "approved": 20, ...},
                "by_primary": {"social": 8, "working": 5, ...},
            }
        """
        data = self._read_store()
        entries = data.get("entries", [])

        by_status: dict[str, int] = {}
        by_primary: dict[str, int] = {}

        for entry in entries:
            status = entry.get("status", "pending")
            by_status[status] = by_status.get(status, 0) + 1

            primary = entry.get("primary", "unknown")
            by_primary[primary] = by_primary.get(primary, 0) + 1

        return {
            "total": len(entries),
            "by_status": by_status,
            "by_primary": by_primary,
        }
