"""Consolidation Engine for SelfMind V2.

Mirrors human sleep consolidation: dedup, compress, extract patterns, detect conflicts.
Operates on MEMORY.md entries via MetadataDB, generates suggestions for human review.
"""

import difflib
import hashlib
import json
import os
import re
from datetime import datetime
from typing import Optional

import requests

from selfmind_app.config import load_config


def _similarity(a: str, b: str) -> float:
    """Normalized text similarity using SequenceMatcher (0.0 ~ 1.0)."""
    return difflib.SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _strip_tags(text: str) -> str:
    """Remove [tag/subtag] markers for content comparison."""
    return re.sub(r'\[[\w/]+\]\s*', '', text).strip()


class Consolidator:
    """Memory consolidation engine — the 'sleep system' for AI memory."""

    # Similarity threshold for duplicate detection
    DEDUP_THRESHOLD = 0.65
    # Minimum content length to consider for compression
    COMPRESS_MIN_LEN = 120

    def __init__(self, meta_db, memory_md_path: str, user_md_path: str = None):
        self.db = meta_db
        self.memory_md_path = memory_md_path
        self.user_md_path = user_md_path
        self._config = load_config()

    # ── 1. Duplicate Detection ──────────────────────────────────

    def find_duplicates(self) -> list[dict]:
        """Find semantically similar entry pairs.

        Returns list of {pair: [entry_a, entry_b], similarity: float, suggestion: str}
        """
        entries = self.db.get_all_entries(status="active")
        if len(entries) < 2:
            return []

        # Strip tags for comparison
        cleaned = [(e, _strip_tags(e.get("content_preview", ""))) for e in entries]

        duplicates = []
        seen = set()

        for i in range(len(cleaned)):
            for j in range(i + 1, len(cleaned)):
                key = (cleaned[i][0]["id"], cleaned[j][0]["id"])
                if key in seen:
                    continue

                sim = _similarity(cleaned[i][1], cleaned[j][1])
                if sim >= self.DEDUP_THRESHOLD:
                    seen.add(key)
                    duplicates.append({
                        "type": "duplicate",
                        "pair": [cleaned[i][0]["id"], cleaned[j][0]["id"]],
                        "entries": [cleaned[i][0], cleaned[j][0]],
                        "similarity": round(sim, 3),
                        "suggestion": self._dedup_suggestion(cleaned[i][0], cleaned[j][0], sim),
                    })

        # Sort by similarity descending
        duplicates.sort(key=lambda x: x["similarity"], reverse=True)
        return duplicates

    def _dedup_suggestion(self, a: dict, b: dict, sim: float) -> str:
        if sim >= 0.9:
            return "几乎完全相同，建议删除其一"
        elif sim >= 0.8:
            return "高度相似，建议合并为一条"
        else:
            return "部分重叠，建议检查是否可以合并"

    # ── 2. Compression Candidates ───────────────────────────────

    def find_compressible(self) -> list[dict]:
        """Find entries that could be compressed without losing meaning."""
        entries = self.db.get_all_entries(status="active")
        candidates = []

        for e in entries:
            preview = e.get("content_preview", "")
            if len(preview) >= self.COMPRESS_MIN_LEN:
                candidates.append({
                    "type": "compress",
                    "entry": e,
                    "current_length": len(preview),
                    "suggestion": "内容较长，可考虑压缩表述",
                })

        return candidates

    # ── 3. Conflict Detection ───────────────────────────────────

    def find_conflicts(self) -> list[dict]:
        """Detect potentially contradictory entries (same category, different claims)."""
        entries = self.db.get_all_entries(status="active")
        if len(entries) < 2:
            return []

        # Group by category
        by_cat = {}
        for e in entries:
            cat = e.get("category") or "unknown"
            by_cat.setdefault(cat, []).append(e)

        conflicts = []
        for cat, group in by_cat.items():
            if len(group) < 2:
                continue
            # Check for entries in same category with low similarity
            # (could indicate contradiction or redundancy)
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a_text = _strip_tags(group[i].get("content_preview", ""))
                    b_text = _strip_tags(group[j].get("content_preview", ""))
                    sim = _similarity(a_text, b_text)
                    # Medium similarity in same category = potential conflict
                    if 0.3 <= sim < self.DEDUP_THRESHOLD:
                        conflicts.append({
                            "type": "conflict",
                            "pair": [group[i]["id"], group[j]["id"]],
                            "entries": [group[i], group[j]],
                            "category": cat,
                            "similarity": round(sim, 3),
                            "suggestion": f"同分类 [{cat}] 下内容相似度 {sim:.0%}，可能存在冲突或需要合并",
                        })

        return conflicts

    # ── 4. Category Health ──────────────────────────────────────

    def analyze_distribution(self) -> dict:
        """Analyze memory distribution across categories."""
        entries = self.db.get_all_entries(status="active")
        if not entries:
            return {"total": 0, "categories": {}, "warnings": []}

        by_cat = {}
        for e in entries:
            cat = e.get("category") or "uncategorized"
            by_cat.setdefault(cat, []).append(e)

        total = len(entries)
        categories = {}
        for cat, group in by_cat.items():
            avg_decay = sum(e.get("decay_score", 0) for e in group) / len(group)
            categories[cat] = {
                "count": len(group),
                "percentage": round(len(group) / total * 100, 1),
                "avg_decay": round(avg_decay, 3),
                "pinned": sum(1 for e in group if e.get("pinned")),
            }

        # Generate warnings
        warnings = []
        for cat, info in categories.items():
            if info["percentage"] > 40:
                warnings.append(f"⚠️ [{cat}] 占比过高 ({info['percentage']}%)，可能过度集中")
            if info["avg_decay"] < 0.1:
                warnings.append(f"⚠️ [{cat}] 平均衰减分很低 ({info['avg_decay']})，可能需要清理")
            if cat == "uncategorized" and info["count"] > 3:
                warnings.append(f"⚠️ {info['count']} 条记忆未分类，建议添加标签")

        return {"total": total, "categories": categories, "warnings": warnings}

    # ── 5. LLM-Powered Consolidation ────────────────────────────

    def llm_consolidate(self, entries: list[dict], task: str = "merge") -> Optional[dict]:
        """Use LLM to generate consolidation suggestions.

        task: 'merge' | 'compress' | 'extract_pattern'
        Returns: {suggestion: str, confidence: float, reasoning: str}
        """
        llm_cfg = self._config.get("llm", {})
        base_url = llm_cfg.get("base_url", "")
        api_key = llm_cfg.get("api_key", "")
        model = llm_cfg.get("model", "gpt-4o-mini")

        if not base_url or not api_key:
            return None

        contents = "\n---\n".join(
            f"[{e.get('id', '?')}] {e.get('content_preview', '')}"
            for e in entries
        )

        prompts = {
            "merge": f"以下是几条可能重复的记忆条目，请合并为一条精炼的记忆，保留所有关键信息：\n\n{contents}\n\n请返回JSON格式：{{\"merged\": \"合并后的内容\", \"reasoning\": \"合并理由\", \"confidence\": 0.0-1.0}}",
            "compress": f"以下记忆条目内容较长，请在不丢失关键信息的前提下压缩表述：\n\n{contents}\n\n请返回JSON格式：{{\"compressed\": \"压缩后的内容\", \"reasoning\": \"压缩理由\", \"savings_pct\": 压缩比例}}",
            "extract_pattern": f"以下是多条记忆，请分析是否存在可提炼的规律或模式：\n\n{contents}\n\n请返回JSON格式：{{\"pattern\": \"提炼的规律\", \"evidence\": [\"支撑证据\"], \"confidence\": 0.0-1.0}}",
        }

        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "你是记忆整理助手。只返回JSON，不要多余文字。"},
                        {"role": "user", "content": prompts.get(task, prompts["merge"])},
                    ],
                    "max_tokens": 1024,
                    "temperature": 0.3,
                },
                timeout=30,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"error": "LLM response not valid JSON", "raw": text}
        except Exception as e:
            return {"error": str(e)}

    # ── 6. Full Scan (the "sleep cycle") ────────────────────────

    def run_full_scan(self) -> dict:
        """Run all consolidation checks. Returns complete analysis."""
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "duplicates": self.find_duplicates(),
            "compressible": self.find_compressible(),
            "conflicts": self.find_conflicts(),
            "distribution": self.analyze_distribution(),
            "summary": self._generate_summary(),
        }

    def _generate_summary(self) -> dict:
        """Generate a human-readable summary of memory health."""
        dupes = self.find_duplicates()
        compress = self.find_compressible()
        conflicts = self.find_conflicts()
        dist = self.analyze_distribution()

        actions = []
        if dupes:
            actions.append(f"🔗 发现 {len(dupes)} 对疑似重复记忆")
        if compress:
            actions.append(f"📦 {len(compress)} 条记忆可以压缩")
        if conflicts:
            actions.append(f"⚡ {len(conflicts)} 对可能冲突")
        for w in dist.get("warnings", []):
            actions.append(w)

        health = "🟢 健康" if not actions else ("🟡 需要注意" if len(actions) <= 2 else "🔴 建议整理")

        return {
            "health": health,
            "action_count": len(actions),
            "actions": actions,
        }
