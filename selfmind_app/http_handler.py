import json
import logging
import os
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional

from selfmind_app.config import CONFIG_FILE, DATA_FILE, SELFMIND_DIR, load_config
from selfmind_app.document_importer import DocumentImporter
from selfmind_app.memory_store import MemoryStore
from selfmind_app.metadata_db import MetadataDB
from selfmind_app.consolidator import Consolidator
from selfmind_app.forgetter import ForgetterEngine
from selfmind_app.analyzer import AnalyzerEngine
from selfmind_app.parser import build_graph
from selfmind_app.wiki_parser import build_wiki_graph
from selfmind_app.providers import FileAdapter, SkillsProvider, AggregationEngine

logger = logging.getLogger(__name__)

# 全局聚合引擎实例
_aggregation_engine = None


def _get_aggregation_engine():
    """获取或创建聚合引擎"""
    global _aggregation_engine
    if _aggregation_engine is None:
        config = load_config()
        file_adapter = FileAdapter(config)
        skills_provider = SkillsProvider(config)
        _aggregation_engine = AggregationEngine([file_adapter, skills_provider])
    return _aggregation_engine

# Shared instances (created lazily)
_importer = DocumentImporter()
_store = MemoryStore()
_meta_db = MetadataDB(str(SELFMIND_DIR / "selfmind.db"))
_consolidator = None
_forgetter = None
_analyzer = None


def _node_signature(node: dict) -> str:
    return "|".join(
        [
            node.get("label", ""),
            node.get("category", ""),
            node.get("description", ""),
        ]
    )


def _safe_read_existing_data() -> Optional[dict]:
    if not DATA_FILE.exists():
        return None
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _apply_node_timestamps(new_data: dict, previous_data: Optional[dict]) -> dict:
    """Attach createdAt/updatedAt to nodes using previous snapshot as baseline."""
    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    prev_nodes = (previous_data or {}).get("nodes", [])
    prev_by_id = {node.get("id"): node for node in prev_nodes if node.get("id")}

    for node in new_data.get("nodes", []):
        node_id = node.get("id")
        prev = prev_by_id.get(node_id)

        if not prev:
            node["createdAt"] = now_iso
            node["updatedAt"] = now_iso
            continue

        prev_created = prev.get("createdAt") or now_iso
        prev_updated = prev.get("updatedAt") or prev_created

        node["createdAt"] = prev_created
        if _node_signature(prev) != _node_signature(node):
            node["updatedAt"] = now_iso
        else:
            node["updatedAt"] = prev_updated

    return new_data


def _merge_metadata(data: dict) -> dict:
    """Merge metadata (decay_score, status, pinned) into nodes."""
    # Get all metadata entries
    meta_entries = _meta_db.get_all_entries()
    
    # Build lookup by content preview (first 80 chars, normalize ** markers)
    meta_lookup = {}
    for entry in meta_entries:
        preview = entry.get('content_preview', '')[:80]
        if preview:
            # Normalize ** markers that parser removes
            normalized = preview.replace('**', '')
            meta_lookup[normalized] = entry
    
    # Build secondary lookup by category/subcategory for primary entries
    # metadata category='primary' + subcategory='social' -> node primary='social'
    meta_by_cat = {}
    for entry in meta_entries:
        if entry.get('category') == 'primary' and entry.get('subcategory'):
            key = f"primary:{entry['subcategory']}"
            meta_by_cat[key] = entry
        elif entry.get('category') == 'secondary' and entry.get('subcategory'):
            key = f"secondary:{entry['subcategory']}"
            meta_by_cat[key] = entry
    
    # Merge into nodes
    merged_count = 0
    for node in data.get('nodes', []):
        node_cat = node.get('category')
        
        if node_cat == 'memory':
            # Try exact match first
            desc = node.get('description', '')[:80].replace('**', '')
            if desc in meta_lookup:
                meta = meta_lookup[desc]
                node['decay_score'] = meta.get('decay_score', 1.0)
                node['status'] = meta.get('status', 'active')
                node['pinned'] = bool(meta.get('pinned', 0))
                merged_count += 1
                continue
            
            # Fallback: match by primary/secondary
            primary = node.get('primary', '')
            secondary = node.get('secondary', '')
            if primary:
                key = f"primary:{primary}"
                if key in meta_by_cat:
                    meta = meta_by_cat[key]
                    node['decay_score'] = meta.get('decay_score', 1.0)
                    node['status'] = meta.get('status', 'active')
                    node['pinned'] = bool(meta.get('pinned', 0))
                    merged_count += 1
                    continue
            if secondary:
                key = f"secondary:{secondary}"
                if key in meta_by_cat:
                    meta = meta_by_cat[key]
                    node['decay_score'] = meta.get('decay_score', 1.0)
                    node['status'] = meta.get('status', 'active')
                    node['pinned'] = bool(meta.get('pinned', 0))
                    merged_count += 1
    
    if merged_count > 0:
        logger.info(f"✅ Merged metadata for {merged_count} nodes")
    return data


def refresh_data() -> dict:
    """Rebuild graph from memory files and write to data.json."""
    config = load_config()
    previous = _safe_read_existing_data()
    data = _apply_node_timestamps(build_graph(config), previous)
    # Merge metadata into nodes
    data = _merge_metadata(data)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


class SelfMindHandler(SimpleHTTPRequestHandler):
    """HTTP handler for SelfMind API + static files."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SELFMIND_DIR), **kwargs)

    def do_GET(self):
        clean_path = self.path.split("?")[0]
        if clean_path == "/api/data":
            self._json_response(self._load_data())
        elif clean_path == "/api/poll":
            self._handle_poll()
        elif clean_path == "/api/wiki/data":
            self._json_response(self._load_wiki_data())
        elif clean_path == "/api/iq":
            self._json_response(self._compute_iq())
        elif clean_path == "/api/skills":
            self._json_response(self._scan_skills())
        elif clean_path.startswith("/api/skills/"):
            skill_name = clean_path.split("/api/skills/")[1]
            self._json_response(self._get_skill_detail(skill_name))
        elif clean_path == "/api/config":
            self._json_response(load_config())
        elif clean_path == "/api/documents/scan":
            self._handle_documents_scan()
        elif clean_path == "/api/documents/extract-stream":
            self._handle_extract_stream()
        elif clean_path == "/api/memories":
            self._handle_memories_list()
        elif clean_path.startswith("/api/memories/stats"):
            self._json_response(_store.get_stats())
        elif clean_path.startswith("/api/memories/"):
            entry_id = clean_path.split("/api/memories/")[1]
            entry = _store.get_entry(entry_id)
            if entry:
                self._json_response(entry)
            else:
                self._json_response({"error": "Not found"}, code=404)
        elif clean_path == "/api/meta/entries":
            self._handle_meta_entries()
        elif clean_path.startswith("/api/meta/entries/"):
            entry_id = clean_path.split("/api/meta/entries/")[1]
            entry = _meta_db.get_entry(entry_id)
            if entry:
                self._json_response(entry)
            else:
                self._json_response({"error": "Not found"}, code=404)
        elif clean_path == "/api/meta/health":
            self._json_response(_meta_db.get_health_stats())
        elif clean_path == "/api/meta/snapshots":
            self._json_response(_meta_db.get_snapshots())
        elif clean_path == "/api/meta/operations":
            self._json_response(_meta_db.get_operations_log())
        elif clean_path == "/api/consolidate/scan":
            self._handle_consolidate_scan()
        elif clean_path == "/api/consolidate/duplicates":
            self._handle_consolidate_duplicates()
        elif clean_path == "/api/consolidate/conflicts":
            self._handle_consolidate_conflicts()
        elif clean_path == "/api/consolidate/distribution":
            self._handle_consolidate_distribution()
        # 遗忘引擎 API
        elif clean_path == "/api/forget/analyze":
            self._handle_forget_analyze()
        elif clean_path == "/api/forget/execute":
            self._handle_forget_execute()
        elif clean_path == "/api/forget/restore":
            self._handle_forget_restore()
        # 分析引擎 API
        elif clean_path == "/api/analyze/patterns":
            self._handle_analyze_patterns()
        elif clean_path == "/api/analyze/graph":
            self._handle_analyze_graph()
        elif clean_path == "/api/analyze/importance":
            self._handle_analyze_importance()
        elif clean_path == "/api/analyze/completeness":
            self._handle_analyze_completeness()
        elif clean_path == "/api/analyze/full":
            self._handle_analyze_full()
        elif clean_path == "/api/agents":
            self._json_response(self._get_agents())
        elif clean_path.startswith("/api/v1/"):
            self._handle_v1_api(clean_path)
        elif clean_path.startswith("/api/agents/"):
            # Handle /api/agents/{id}/default, /api/agents/{id}/switch
            parts = clean_path.split("/")
            if len(parts) >= 4:
                agent_id = parts[3]
                if clean_path.endswith("/default"):
                    self._set_default_agent(agent_id)
                elif clean_path.endswith("/switch"):
                    self._switch_agent(agent_id)
                else:
                    self._send_error(404, "Not found")
            else:
                self._send_error(404, "Not found")
        elif clean_path == "/api/import":
            self._json_response({"error": "Use POST"})
            self.path = "/index.html"
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        clean_path = self.path.split("?")[0]

        if clean_path == "/api/refresh":
            data = refresh_data()
            self._json_response(
                {
                    "status": "ok",
                    "nodes": len(data["nodes"]),
                    "links": len(data["links"]),
                    "message": "Memory data refreshed",
                }
            )
            return

        if clean_path == "/api/wiki/refresh":
            data = self._refresh_wiki_data()
            self._json_response({
                "status": "ok",
                "nodes": len(data.get("nodes", [])),
                "links": len(data.get("links", [])),
                "message": "Wiki data refreshed",
            })
            return

        if clean_path == "/api/save":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                new_data = json.loads(body)
                new_data["lastUpdated"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(new_data, f, ensure_ascii=False, indent=2)
                self._json_response(
                    {
                        "status": "ok",
                        "path": str(DATA_FILE),
                        "message": "Data saved",
                    }
                )
            except Exception as exc:
                self._json_response({"status": "error", "message": str(exc)}, code=400)
            return

        if clean_path == "/api/config":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                new_config = json.loads(body)
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(new_config, f, ensure_ascii=False, indent=2)
                self._json_response({"status": "ok", "message": "Config saved"})
            except Exception as exc:
                self._json_response({"status": "error", "message": str(exc)}, code=400)
            return

        if clean_path == "/api/documents/extract":
            self._handle_documents_extract()
            return

        if clean_path == "/api/memories":
            self._handle_memories_add()
            return

        if clean_path == "/api/memories/sync":
            self._handle_memories_sync()
            return

        if clean_path == "/api/memories/bulk-status":
            self._handle_memories_bulk_status()
            return

        if clean_path == "/api/meta/sync":
            self._handle_meta_sync()
            return

        if clean_path == "/api/meta/snapshots":
            self._handle_meta_create_snapshot()
            return

        if clean_path == "/api/meta/decay":
            count = _meta_db.compute_decay_scores()
            self._json_response({"status": "ok", "updated": count})
            return

        if clean_path.startswith("/api/meta/entries/") and clean_path.endswith("/pin"):
            entry_id = clean_path.split("/api/meta/entries/")[1].replace("/pin", "")
            _meta_db.pin_entry(entry_id)
            self._json_response({"status": "ok", "pinned": True})
            return

        if clean_path.startswith("/api/meta/entries/") and clean_path.endswith("/unpin"):
            entry_id = clean_path.split("/api/meta/entries/")[1].replace("/unpin", "")
            _meta_db.unpin_entry(entry_id)
            self._json_response({"status": "ok", "pinned": False})
            return

        if clean_path.startswith("/api/meta/snapshots/") and clean_path.endswith("/restore"):
            sid = clean_path.split("/api/meta/snapshots/")[1].replace("/restore", "")
            try:
                snap = _meta_db.restore_snapshot(int(sid))
            except (ValueError, TypeError):
                snap = None
            if snap:
                self._json_response(snap)
            else:
                self._json_response({"error": "Snapshot not found"}, code=404)
            return

        if clean_path == "/api/consolidate/llm":
            self._handle_consolidate_llm()
            return

        if clean_path == "/api/agents":
            self._add_agent()
            return

        if clean_path.startswith("/api/v1/"):
            self._handle_v1_api_post(clean_path)
            return

        if clean_path == "/api/import":
            self._import_memory()
            return

        if clean_path.startswith("/api/agents/") and clean_path.endswith("/switch"):
            agent_id = clean_path.split("/api/agents/")[1].replace("/switch", "")
            self._switch_agent(agent_id)
            return

        self._json_response({"error": "Not found"}, code=404)

    def do_PUT(self):
        clean_path = self.path.split("?")[0]
        if clean_path.startswith("/api/memories/"):
            entry_id = clean_path.split("/api/memories/")[1]
            self._handle_memory_update(entry_id)
            return

        if clean_path.startswith("/api/agents/") and clean_path.endswith("/default"):
            agent_id = clean_path.split("/api/agents/")[1].replace("/default", "")
            self._set_default_agent(agent_id)
            return

        if clean_path.startswith("/api/agents/") and clean_path.endswith("/switch"):
            agent_id = clean_path.split("/api/agents/")[1].replace("/switch", "")
            self._switch_agent(agent_id)
            return

        self._json_response({"error": "Not found"}, code=404)

    def do_DELETE(self):
        clean_path = self.path.split("?")[0]
        if clean_path.startswith("/api/memories/"):
            entry_id = clean_path.split("/api/memories/")[1]
            if _store.delete_entry(entry_id):
                self._json_response({"status": "ok", "message": "Entry deleted"})
            else:
                self._json_response({"error": "Not found"}, code=404)
            return

        if clean_path.startswith("/api/agents/"):
            agent_id = clean_path.split("/api/agents/")[1]
            self._delete_agent(agent_id)
            return

        self._json_response({"error": "Not found"}, code=404)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _handle_poll(self):
        """轻量轮询接口：返回记忆源文件的修改时间戳，用于前端检测变化。"""
        import hashlib
        from pathlib import Path
        
        home = Path.home()
        memory_file = home / ".hermes" / "memories" / "MEMORY.md"
        user_file = home / ".hermes" / "memories" / "USER.md"
        
        files_info = {}
        total_mtime = 0.0
        
        for fname, fpath in [("MEMORY.md", memory_file), ("USER.md", user_file)]:
            if fpath.exists():
                stat = fpath.stat()
                mtime = stat.st_mtime_ns
                total_mtime += mtime
                files_info[fname] = {
                    "mtime_ns": mtime,
                    "size": stat.st_size,
                }
            else:
                files_info[fname] = {"mtime_ns": 0, "size": 0}
        
        # 用所有文件的 mtime 拼接后取 hash，作为单一比较值
        mtime_str = str(total_mtime)
        poll_hash = hashlib.md5(mtime_str.encode()).hexdigest()
        
        self._json_response({
            "hash": poll_hash,
            "files": files_info,
            "timestamp": datetime.now().isoformat(),
        })

    def _load_data(self):
        if DATA_FILE.exists():
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Backfill timestamps for old data files that predate createdAt/updatedAt.
            if any("createdAt" not in node or "updatedAt" not in node for node in data.get("nodes", [])):
                data = _apply_node_timestamps(data, None)
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            return data
        return refresh_data()

    def _scan_skills(self, include_content: bool = False) -> dict:
        """Scan ~/.hermes/skills for SKILL.md files and return skill stats.
        
        Args:
            include_content: If True, include full content for each skill
        """
        from pathlib import Path
        import re

        skills_dir = Path.home() / ".hermes" / "skills"
        if not skills_dir.exists():
            return {"total": 0, "categories": 0, "category_list": [], "skills": []}

        skill_files = list(skills_dir.rglob("SKILL.md"))
        skills = []
        categories = set()

        for sf in skill_files:
            try:
                content = sf.read_text(encoding="utf-8")
                # Parse YAML frontmatter
                name = sf.parent.name
                desc = ""
                cat = sf.parent.parent.name if sf.parent.parent != skills_dir else ""
                subcat = ""

                # Extract name and description from frontmatter
                fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
                if fm_match:
                    fm = fm_match.group(1)
                    for line in fm.split("\n"):
                        if line.startswith("name:"):
                            name = line.split(":", 1)[1].strip().strip("'\"")
                        elif line.startswith("description:"):
                            desc = line.split(":", 1)[1].strip().strip("'\"")

                # Determine category and subcategory from path
                rel_path = sf.parent.relative_to(skills_dir)
                if len(rel_path.parts) >= 2:
                    cat = rel_path.parts[0]
                    subcat = rel_path.parts[1] if len(rel_path.parts) > 1 else ""
                elif len(rel_path.parts) == 1:
                    cat = rel_path.parts[0]
                    subcat = ""

                if cat and cat != ".hermes":
                    categories.add(cat)
                elif not cat:
                    categories.add("uncategorized")

                # Estimate complexity: count steps, code blocks, sections
                n_steps = len(re.findall(r"^\d+\.", content, re.MULTILINE))
                n_code_blocks = content.count("```")
                n_sections = len(re.findall(r"^#{1,3}\s", content, re.MULTILINE))
                complexity = min(1.0, (n_steps * 0.05 + n_code_blocks * 0.03 + n_sections * 0.04))

                skill_entry = {
                    "name": name,
                    "description": desc[:100] if desc else content[:100].replace("\n", " "),
                    "category": cat or "uncategorized",
                    "subcategory": subcat,
                    "complexity": round(complexity, 2),
                    "content_length": len(content),
                    "path": str(sf.parent),
                }
                
                # Include full content if requested
                if include_content:
                    skill_entry["content"] = content
                
                skills.append(skill_entry)
            except (OSError, UnicodeDecodeError):
                continue

        return {
            "total": len(skills),
            "categories": len(categories),
            "category_list": sorted(categories),
            "skills": skills,
            "avg_complexity": round(sum(s["complexity"] for s in skills) / max(len(skills), 1), 2),
        }

    def _get_skill_detail(self, skill_name: str) -> dict:
        """Get detailed info for a specific skill by name or path."""
        skills = self._scan_skills(include_content=True).get("skills", [])
        
        # Try to find by name (partial match)
        for skill in skills:
            if skill_name.lower() in skill["name"].lower() or skill["name"].lower() in skill_name.lower():
                return {
                    "name": skill["name"],
                    "description": skill.get("description", ""),
                    "category": skill.get("category", ""),
                    "subcategory": skill.get("subcategory", ""),
                    "complexity": skill.get("complexity", 0),
                    "content": skill.get("content", ""),
                    "path": skill.get("path", ""),
                }
        
        # Try to find by exact path match
        for skill in skills:
            if skill.get("path", "").endswith(skill_name):
                return {
                    "name": skill["name"],
                    "description": skill.get("description", ""),
                    "category": skill.get("category", ""),
                    "subcategory": skill.get("subcategory", ""),
                    "complexity": skill.get("complexity", 0),
                    "content": skill.get("content", ""),
                    "path": skill.get("path", ""),
                }
        
        return {"error": f"Skill '{skill_name}' not found"}

    def _compute_iq(self) -> dict:
        """Compute an IQ score modeled on human intelligence distribution.

        Human IQ: mean=100, σ=15. This algorithm maps AI brain complexity
        (memory + skills) to a comparable scale:
        - 40~60: 沉睡中 (newborn AI, minimal memory & skills)
        - 60~80: 刚觉醒 (growing, basic structure)
        - 80~90: 发育中 (decent memory, some skills)
        - 90~100: 正常水平 (solid memory, decent connections & skills)
        - 100~110: 正常偏上 (good knowledge + skill breadth)
        - 110~120: 中上水平 (rich knowledge, good network, many skills)
        - 120~140: 非常聪明 (extensive, well-connected, skill mastery)
        - 140~160: 天才 (near impossible without massive memory + skills)

        Benchmarks (approximate):
        - 17 nodes, 19 links, 20 skills → ~80 IQ (developing)
        - 50 nodes, 80 links, 50 skills → ~95 IQ (normal)
        - 100 nodes, 200 links, 100 skills → ~112 IQ (smart)
        - 200+ nodes, 500+ links, 200+ skills → ~130+ IQ (very smart)
        """
        import math

        data = self._load_data()
        nodes = data.get("nodes", [])
        links = data.get("links", [])
        n_nodes = len(nodes)
        n_links = len(links)

        # Scan skills
        skill_stats = self._scan_skills()
        n_skills = skill_stats["total"]
        n_skill_cats = skill_stats["categories"]
        avg_skill_complexity = skill_stats.get("avg_complexity", 0)

        if n_nodes == 0 and n_skills == 0:
            return {"iq": 40, "level": "未觉醒 💤", "breakdown": {}, "tips": ["还没有任何记忆和技能呢"], "skills": skill_stats}

        # --- 6 dimensions, each scored 0.0 ~ 1.0 ---

        # 1. 记忆容量 (weight 25%): logarithmic scale
        #    1 node → ~0.0, 20 → ~0.33, 50 → ~0.55, 100 → ~0.72, 200 → ~0.86, 500 → 1.0
        capacity_raw = math.log(n_nodes + 1) / math.log(501) if n_nodes > 0 else 0
        capacity = min(1.0, capacity_raw)

        # 2. 连接密度 (weight 20%): links-to-nodes ratio with diminishing returns
        density_ratio = n_links / n_nodes if n_nodes > 0 else 0
        density = min(1.0, 1 - 1 / (1 + density_ratio / 3))

        # 3. 分类覆盖 (weight 15%): how many of 8 primary cognitive categories are represented
        #    New taxonomy: autobiographical, semantic, episodic, procedural, social, working, spatial, emotional
        primary_categories = set(n.get("primary", "") for n in nodes if n.get("primary"))
        category_count = len(primary_categories)
        max_categories = 8
        coverage = min(1.0, category_count / max_categories)

        # 4. 知识深度 (weight 10%): average description richness
        if n_nodes > 0:
            avg_desc_len = sum(len(n.get("description", "")) for n in nodes) / n_nodes
            depth = min(1.0, math.log(avg_desc_len + 1) / math.log(501))
        else:
            depth = 0

        # 5. 网络效应 (weight 10%): connectivity quality
        degree = {}
        for link in links:
            s = link.get("source", {})
            t = link.get("target", {})
            sid = s.get("id", s) if isinstance(s, dict) else s
            tid = t.get("id", t) if isinstance(t, dict) else t
            degree[sid] = degree.get(sid, 0) + 1
            degree[tid] = degree.get(tid, 0) + 1
        avg_degree = sum(degree.values()) / max(len(degree), 1) if degree else 0
        isolated = sum(1 for n in nodes if n.get("id") not in degree)
        isolation_penalty = isolated / n_nodes if n_nodes > 0 else 0
        network = min(1.0, (1 - 1 / (1 + avg_degree / 4)) * (1 - isolation_penalty * 0.5)) if n_nodes > 0 else 0

        # 6. 技能掌握 (weight 20%): skill breadth, depth, and complexity
        #    Combines: total skills (log scale), category diversity, avg complexity
        #    5 skills → ~0.15, 20 → ~0.35, 50 → ~0.52, 100 → ~0.66, 200 → ~0.80, 500 → 1.0
        skill_count_score = math.log(n_skills + 1) / math.log(501) if n_skills > 0 else 0
        skill_diversity = min(1.0, n_skill_cats / 15)  # 15 categories = full coverage
        skill_quality = avg_skill_complexity  # already 0~1
        # Weighted sub-composite: count matters most, then diversity, then quality
        skills_score = min(1.0, skill_count_score * 0.5 + skill_diversity * 0.3 + skill_quality * 0.2)

        # --- Weighted composite score (0.0 ~ 1.0) ---
        weights = {
            "capacity": 0.25, "density": 0.20, "coverage": 0.15,
            "depth": 0.10, "network": 0.10, "skills": 0.20,
        }
        scores = {
            "capacity": capacity, "density": density, "coverage": coverage,
            "depth": depth, "network": network, "skills": skills_score,
        }
        composite = sum(scores[k] * weights[k] for k in weights)

        # --- Map composite to IQ (human-like distribution) ---
        # Strict curve: mirrors human rarity at high IQ
        # composite 0.0 → IQ 40, 0.3 → IQ 64, 0.5 → IQ 77, 0.7 → IQ 92, 0.85 → IQ 106, 1.0 → IQ 140
        iq = int(40 + 100 * (composite ** 1.3))
        iq = min(160, max(40, iq))

        # Level label (matching human IQ classification)
        if iq >= 140:
            level = "天才 🧠"
        elif iq >= 120:
            level = "非常聪明 🌟"
        elif iq >= 110:
            level = "中上水平 💡"
        elif iq >= 100:
            level = "正常偏上 📖"
        elif iq >= 90:
            level = "正常水平 📖"
        elif iq >= 80:
            level = "发育中 🌱"
        elif iq >= 60:
            level = "刚觉醒 👶"
        else:
            level = "沉睡中 💤"

        # Tips for improvement (based on weakest dimensions)
        dim_labels = {
            "capacity": "记忆容量", "density": "连接密度", "coverage": "分类覆盖",
            "depth": "知识深度", "network": "网络效应", "skills": "技能掌握",
        }
        dim_tips = {
            "capacity": "多积累记忆节点，扩大知识库规模",
            "density": "建立更多节点间的关联和连接",
            "coverage": "拓展更多分类领域的认知",
            "depth": "丰富每条记忆的描述和细节",
            "network": "减少孤立节点，增强知识互联",
            "skills": "学习更多技能，提升实操能力",
        }
        tips = []
        sorted_dims = sorted(scores.items(), key=lambda x: x[1])
        for dim_key, dim_score in sorted_dims[:2]:
            if dim_score < 0.7:
                tips.append(dim_tips[dim_key])
        if not tips:
            tips.append("各项指标均衡发展，继续保持！")

        # Format breakdown for frontend
        max_scores = {
            "capacity": 25, "density": 20, "coverage": 15,
            "depth": 10, "network": 10, "skills": 20,
        }
        breakdown = {}
        for k in scores:
            breakdown[k] = {
                "score": round(scores[k] * max_scores[k], 1),
                "max": max_scores[k],
                "label": dim_labels[k],
            }

        return {
            "iq": iq,
            "level": level,
            "breakdown": breakdown,
            "stats": {
                "nodes": n_nodes,
                "links": n_links,
                "categories": category_count,
                "avg_degree": round(avg_degree, 2),
                "skills": n_skills,
                "skill_categories": n_skill_cats,
            },
            "tips": tips,
            "skills": {
                "total": skill_stats["total"],
                "categories": skill_stats["categories"],
                "category_list": skill_stats["category_list"],
            },
        }

    # ── New API handler methods ──────────────────────────────────────

    def _read_body(self) -> dict:
        """Read and parse JSON request body."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        return json.loads(body) if body else {}

    def _handle_documents_scan(self):
        """GET /api/documents/scan?dir=... — Scan directory for documents."""
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        dir_path = params.get("dir", [""])[0]

        if not dir_path:
            config = load_config()
            dir_path = config.get("documents", {}).get("watch_dir", "")

        if not dir_path:
            self._json_response(
                {"error": "No directory specified. Use ?dir=/path or set documents.watch_dir in config."},
                code=400,
            )
            return

        files = _importer.scan_directory(dir_path)
        self._json_response({"dir": dir_path, "files": files, "count": len(files)})

    def _handle_extract_stream(self):
        """GET /api/documents/extract-stream?dir=... — SSE stream: scan + extract with progress."""
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        dir_path = params.get("dir", [""])[0]

        if not dir_path:
            config = load_config()
            dir_path = config.get("documents", {}).get("watch_dir", "")

        # Set up SSE response headers
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def send_event(data: dict):
            try:
                payload = json.dumps(data, ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        if not dir_path:
            send_event({"type": "error", "message": "未指定目录路径"})
            return

        # Phase 1: Scan
        send_event({"type": "scanning", "dir": dir_path})
        files = _importer.scan_directory(dir_path)

        if not files:
            send_event({"type": "done", "total_files": 0, "total_extracted": 0,
                        "message": "未找到可导入的文档"})
            return

        send_event({"type": "scan_done", "total_files": len(files),
                    "files": [f["name"] for f in files]})

        # Phase 2: Extract file by file
        config = load_config()
        llm_config = config.get("llm", {})

        if not llm_config.get("api_key"):
            send_event({"type": "error", "message": "LLM API Key 未配置"})
            return

        total_extracted = 0
        processed = 0
        skipped = 0

        for i, file_info in enumerate(files):
            file_path = file_info["path"]
            file_name = file_info["name"]

            send_event({
                "type": "extracting",
                "file": file_name,
                "current": i + 1,
                "total": len(files),
            })

            content = _importer.read_document(file_path)
            if not content.strip():
                skipped += 1
                send_event({
                    "type": "file_skipped",
                    "file": file_name,
                    "reason": "文件内容为空",
                    "current": i + 1,
                    "total": len(files),
                })
                continue

            try:
                memories = _importer.extract_memories(content, file_name, config)
                if memories:
                    ids = _store.add_entries(memories)
                    total_extracted += len(memories)
                processed += 1

                send_event({
                    "type": "file_done",
                    "file": file_name,
                    "extracted": len(memories) if memories else 0,
                    "total_extracted": total_extracted,
                    "current": i + 1,
                    "total": len(files),
                })
            except Exception as exc:
                logger.error("Error extracting %s: %s", file_name, exc)
                send_event({
                    "type": "file_error",
                    "file": file_name,
                    "error": str(exc),
                    "current": i + 1,
                    "total": len(files),
                })

        send_event({
            "type": "done",
            "total_files": len(files),
            "processed": processed,
            "skipped": skipped,
            "total_extracted": total_extracted,
        })

    def _handle_documents_extract(self):
        """POST /api/documents/extract — Extract memories from documents.

        Body: {"dir": "/path/to/docs"} or {"file": "/path/to/file.md"}
        """
        try:
            body = self._read_body()
        except Exception as exc:
            self._json_response({"error": f"Invalid JSON: {exc}"}, code=400)
            return

        config = load_config()
        llm_config = config.get("llm", {})

        if not llm_config.get("api_key"):
            self._json_response(
                {"error": "LLM API key not configured. Set llm.api_key in config or LLM_API_KEY env var."},
                code=400,
            )
            return

        file_path = body.get("file")
        dir_path = body.get("dir")

        if file_path:
            # Single file extraction
            content = _importer.read_document(file_path)
            if not content.strip():
                self._json_response({"error": f"Could not read file: {file_path}"}, code=400)
                return
            source_name = file_path.split("/")[-1] if "/" in file_path else file_path
            memories = _importer.extract_memories(content, source_name, config)
            # Store extracted memories
            if memories:
                ids = _store.add_entries(memories)
                self._json_response({
                    "status": "ok",
                    "extracted": len(memories),
                    "ids": ids,
                    "memories": _store.get_entries({"status": "pending"}),
                })
            else:
                self._json_response({"status": "ok", "extracted": 0, "ids": [], "memories": []})

        elif dir_path:
            # Batch extraction from directory
            memories = _importer.batch_extract(dir_path, config)
            if memories:
                ids = _store.add_entries(memories)
                self._json_response({
                    "status": "ok",
                    "extracted": len(memories),
                    "ids": ids,
                    "memories": _store.get_entries({"status": "pending"}),
                })
            else:
                self._json_response({"status": "ok", "extracted": 0, "ids": [], "memories": []})
        else:
            self._json_response({"error": "Provide 'dir' or 'file' in request body"}, code=400)

    def _handle_memories_list(self):
        """GET /api/memories?status=...&primary=... — List memories with filters."""
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        filters = {}
        for key in ("status", "primary", "secondary", "source_file"):
            if key in params:
                val = params[key]
                filters[key] = val[0] if len(val) == 1 else val

        entries = _store.get_entries(filters if filters else None)
        self._json_response({"entries": entries, "total": len(entries)})

    def _handle_memories_add(self):
        """POST /api/memories — Add memory entries manually."""
        try:
            body = self._read_body()
        except Exception as exc:
            self._json_response({"error": f"Invalid JSON: {exc}"}, code=400)
            return

        entries = body.get("entries", [])
        if not entries:
            # Single entry
            if body.get("text"):
                entries = [body]
            else:
                self._json_response({"error": "Provide 'entries' array or a single entry object"}, code=400)
                return

        ids = _store.add_entries(entries)
        self._json_response({"status": "ok", "ids": ids, "count": len(ids)})

    def _handle_memory_update(self, entry_id: str):
        """PUT /api/memories/:id — Update a memory entry."""
        try:
            updates = self._read_body()
        except Exception as exc:
            self._json_response({"error": f"Invalid JSON: {exc}"}, code=400)
            return

        result = _store.update_entry(entry_id, updates)
        if result:
            self._json_response({"status": "ok", "entry": result})
        else:
            self._json_response({"error": "Not found"}, code=404)

    def _handle_memories_sync(self):
        """POST /api/memories/sync — Sync memories to an agent system.

        Body: {"ids": [...], "agent": "hermes"} or {"ids": [...], "agent": "openclaw"}
        """
        try:
            body = self._read_body()
        except Exception as exc:
            self._json_response({"error": f"Invalid JSON: {exc}"}, code=400)
            return

        entry_ids = body.get("ids", [])
        agent = body.get("agent", "hermes")
        config = load_config()

        if not entry_ids:
            self._json_response({"error": "Provide 'ids' array"}, code=400)
            return

        profiles = config.get("source", {}).get("profiles", {})
        if agent not in profiles:
            self._json_response({"error": f"Unknown agent: {agent}. Available: {list(profiles.keys())}"}, code=400)
            return

        agent_home = profiles[agent].get("home", "")

        if agent == "hermes":
            result = _store.sync_to_hermes(entry_ids, agent_home)
        elif agent == "openclaw":
            result = _store.sync_to_openclaw(entry_ids, agent_home)
        else:
            result = _store.sync_to_hermes(entry_ids, agent_home)

        self._json_response({"status": "ok", **result})

    def _handle_memories_bulk_status(self):
        """POST /api/memories/bulk-status — Bulk update memory entry status.

        Body: {"ids": [...], "status": "approved"}
        """
        try:
            body = self._read_body()
        except Exception as exc:
            self._json_response({"error": f"Invalid JSON: {exc}"}, code=400)
            return

        entry_ids = body.get("ids", [])
        status = body.get("status", "")

        if not entry_ids or not status:
            self._json_response({"error": "Provide 'ids' array and 'status'"}, code=400)
            return

        try:
            count = _store.bulk_update_status(entry_ids, status)
            self._json_response({"status": "ok", "updated": count})
        except ValueError as exc:
            self._json_response({"error": str(exc)}, code=400)

    def _load_wiki_data(self) -> dict:
        """Load wiki graph data, building from wiki files."""
        wiki_data_file = SELFMIND_DIR / "wiki_data.json"
        if wiki_data_file.exists():
            try:
                with open(wiki_data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return self._refresh_wiki_data()

    def _refresh_wiki_data(self) -> dict:
        """Rebuild wiki graph from wiki markdown files."""
        config = load_config()
        data = build_wiki_graph(config)
        wiki_data_file = SELFMIND_DIR / "wiki_data.json"
        with open(wiki_data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data

    # ── Meta API handler methods ─────────────────────────────────────

    def _handle_meta_entries(self):
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        status = params.get("status", [None])[0]
        self._json_response(_meta_db.get_all_entries(status=status))

    def _handle_meta_sync(self):
        config = load_config()
        source_cfg = config.get("source", {})
        active = source_cfg.get("active_profile", "hermes")
        profile = source_cfg.get("profiles", {}).get(active, {})
        home = profile.get("home", "")
        files = profile.get("memory_files", [])
        memory_path = user_path = None
        for f in files:
            full = os.path.join(home, f)
            if os.path.exists(full):
                if "MEMORY" in f.upper() or "memory" in f:
                    memory_path = full
                elif "USER" in f.upper() or "user" in f:
                    user_path = full
        if not memory_path:
            # Try fallback
            for f in profile.get("memory_files_fallback", []):
                full = os.path.join(home, f)
                if os.path.exists(full):
                    if "memory" in f.lower():
                        memory_path = full
                    elif "user" in f.lower():
                        user_path = full
        if not memory_path:
            self._json_response({"error": "No memory file found"}, code=404)
            return
        result = _meta_db.sync_from_memory_files(memory_path, user_path)
        self._json_response({"status": "ok", **result})

    def _handle_meta_create_snapshot(self):
        config = load_config()
        source_cfg = config.get("source", {})
        active = source_cfg.get("active_profile", "hermes")
        profile = source_cfg.get("profiles", {}).get(active, {})
        home = profile.get("home", "")
        memory_content = user_content = ""
        for f in profile.get("memory_files", []):
            full = os.path.join(home, f)
            if os.path.exists(full):
                with open(full, "r", encoding="utf-8") as fh:
                    content = fh.read()
                if "MEMORY" in f.upper() or "memory" in f:
                    memory_content = content
                elif "USER" in f.upper() or "user" in f:
                    user_content = content
        sid = _meta_db.create_snapshot(memory_content, user_content, "manual")
        self._json_response({"status": "ok", "snapshot_id": sid})

    # ── Consolidation API handler methods ──────────────────────────

    def _get_consolidator(self) -> Consolidator:
        global _consolidator
        if _consolidator is None:
            config = load_config()
            source_cfg = config.get("source", {})
            active = source_cfg.get("active_profile", "hermes")
            profile = source_cfg.get("profiles", {}).get(active, {})
            home = profile.get("home", "")
            memory_path = user_path = None
            for f in profile.get("memory_files", []):
                full = os.path.join(home, f)
                if os.path.exists(full):
                    if "memory" in f.lower():
                        memory_path = full
                    elif "user" in f.lower():
                        user_path = full
            _consolidator = Consolidator(_meta_db, memory_path or "", user_path)
        return _consolidator

    def _get_forgetter(self) -> ForgetterEngine:
        global _forgetter
        if _forgetter is None:
            _forgetter = ForgetterEngine()
        return _forgetter

    def _get_analyzer(self) -> AnalyzerEngine:
        global _analyzer
        if _analyzer is None:
            _analyzer = AnalyzerEngine()
        return _analyzer

    # 省略原有的 _get_consolidator 方法后半部分...

    def _handle_consolidate_scan(self):
        c = self._get_consolidator()
        self._json_response(c.run_full_scan())

    def _handle_consolidate_duplicates(self):
        c = self._get_consolidator()
        # Use graph data (nodes/links) instead of metadataDB
        self._json_response(c.find_duplicates_from_graph())

    def _handle_consolidate_conflicts(self):
        c = self._get_consolidator()
        # TODO: Implement conflict detection for graph data
        self._json_response({"conflicts": [], "message": "Conflict detection from graph data not yet implemented"})

    def _handle_consolidate_distribution(self):
        c = self._get_consolidator()
        # Use graph data for distribution analysis
        self._json_response(c.analyze_distribution_from_graph())

    def _handle_consolidate_llm(self):
        try:
            body = self._read_body()
        except Exception as exc:
            self._json_response({"error": f"Invalid JSON: {exc}"}, code=400)
            return
        entry_ids = body.get("entry_ids", [])
        task = body.get("task", "merge")
        if not entry_ids:
            self._json_response({"error": "Provide 'entry_ids' array"}, code=400)
            return
        entries = [_meta_db.get_entry(eid) for eid in entry_ids]
        entries = [e for e in entries if e]
        if not entries:
            self._json_response({"error": "No valid entries found"}, code=404)
            return
        c = self._get_consolidator()
        result = c.llm_consolidate(entries, task)
        if result:
            self._json_response(result)
        else:
            self._json_response({"error": "LLM not configured"}, code=400)

    # ── Forgetter API handlers ───────────────────────────────────────

    def _handle_forget_analyze(self):
        """分析哪些记忆应该被遗忘"""
        f = self._get_forgetter()
        # Use graph data for analysis
        self._json_response(f.analyze_forget_from_graph())

    def _handle_forget_execute(self):
        """执行遗忘操作"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
        try:
            params = json.loads(body) if body else {}
        except json.JSONDecodeError:
            params = {}
        
        memory_ids = params.get('memory_ids')
        dry_run = params.get('dry_run', False)
        
        f = self._get_forgetter()
        result = f.run_forgetting(memory_ids=memory_ids, dry_run=dry_run)
        self._json_response(result)

    def _handle_forget_restore(self):
        """恢复已遗忘的记忆"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
        try:
            params = json.loads(body) if body else {}
        except json.JSONDecodeError:
            params = {}
        
        memory_id = params.get('memory_id')
        if not memory_id:
            self._json_response({"error": "Provide 'memory_id'"}, code=400)
            return
        
        f = self._get_forgetter()
        result = f.restore_memory(memory_id)
        self._json_response({"success": result, "memory_id": memory_id})

    # ── Analyzer API handlers ────────────────────────────────────────

    def _handle_analyze_patterns(self):
        """分析记忆模式"""
        a = self._get_analyzer()
        # TODO: Implement pattern analysis for graph data
        self._json_response({"patterns": [], "message": "Pattern analysis from graph data not yet implemented"})

    def _handle_analyze_graph(self):
        """更新知识图谱"""
        a = self._get_analyzer()
        # Use graph data insights
        self._json_response(a.extract_insights_from_graph())

    def _handle_analyze_importance(self):
        """分析记忆重要性"""
        a = self._get_analyzer()
        # Use graph data for importance analysis
        self._json_response(a.analyze_importance_from_graph())

    def _handle_analyze_completeness(self):
        """分析知识完整性"""
        a = self._get_analyzer()
        # Use graph data insights for completeness
        self._json_response(a.extract_insights_from_graph())

    def _handle_analyze_full(self):
        """完整分析"""
        a = self._get_analyzer()
        result = a.run_full_analysis()
        self._json_response(result)

    # ========== Agent管理API ==========
    def _get_agents(self):
        """获取所有Agent"""
        config = load_config()
        
        # 从source.profiles构建agents列表
        profiles = config.get("source", {}).get("profiles", {})
        agents = []
        for pid, pdata in profiles.items():
            agents.append({
                "id": pid,
                "name": pdata.get("name", pid.title()),
                "path": pdata.get("home", "")
            })
        
        # 添加自定义agents（如果有）
        custom_agents = config.get("agents", [])
        for ca in custom_agents:
            if not any(a["id"] == ca["id"] for a in agents):
                agents.append(ca)
        
        current = config.get("source", {}).get("active_profile", "hermes")
        
        return {
            "agents": agents,
            "currentAgent": current
        }

    def _add_agent(self):
        """添加新Agent"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except:
            self._json_response({"error": "Invalid JSON"}, code=400)
            return

        name = data.get("name", "").strip()
        path = data.get("path", "").strip()

        if not name or not path:
            self._json_response({"error": "Name and path required"}, code=400)
            return

        # 展开路径
        path = str(Path(path).expanduser())

        config = load_config()
        profiles = config.setdefault("source", {}).setdefault("profiles", {})
        agent_id = name.lower().replace(" ", "-")

        # 检查是否已存在
        if agent_id in profiles:
            self._json_response({"error": "Agent already exists"}, code=400)
            return

        # 添加到profiles
        profiles[agent_id] = {
            "name": name,
            "home": path,
            "memory_files": ["memories/MEMORY.md", "memories/USER.md"],
            "memory_files_fallback": ["memory.md", "user.md"]
        }

        # 保存配置
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        self._json_response({"status": "ok", "agent": {"id": agent_id, "name": name, "path": path}})

    def _delete_agent(self, agent_id):
        """删除Agent"""
        config = load_config()
        
        # 不能删除内置的agent
        if agent_id in ["hermes", "openclaw", "honcho"]:
            self._json_response({"error": "Cannot delete built-in agent"}, code=400)
            return

        profiles = config.get("source", {}).get("profiles", {})
        
        if agent_id not in profiles:
            self._json_response({"error": "Agent not found"}, code=404)
            return

        del profiles[agent_id]

        # 如果删除的是当前agent，切换到hermes
        current = config.get("source", {}).get("active_profile", "hermes")
        if current == agent_id:
            config.setdefault("source", {})["active_profile"] = "hermes"

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        self._json_response({"status": "ok", "message": "Agent deleted"})

    def _set_default_agent(self, agent_id):
        """设置默认Agent"""
        config = load_config()
        profiles = config.get("source", {}).get("profiles", {})

        # 验证agent存在
        if agent_id not in profiles:
            self._json_response({"error": "Agent not found"}, code=404)
            return

        config.setdefault("source", {})["active_profile"] = agent_id

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        self._json_response({"status": "ok", "message": "Default agent set to " + agent_id})

    def _switch_agent(self, agent_id):
        """切换当前Agent"""
        config = load_config()
        profiles = config.get("source", {}).get("profiles", {})

        # 验证agent存在
        if agent_id not in profiles:
            self._json_response({"error": "Agent not found"}, code=404)
            return

        config.setdefault("source", {})["active_profile"] = agent_id

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        self._json_response({"status": "ok", "message": "Switched to " + agent_id})

    def _import_memory(self):
        """导入记忆文件"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except:
            self._json_response({"error": "Invalid JSON"}, code=400)
            return

        import_path = data.get("path", "").strip()
        if not import_path:
            self._json_response({"error": "Path required"}, code=400)
            return

        import_path = str(Path(import_path).expanduser())

        if not os.path.exists(import_path):
            self._json_response({"error": "File not found"}, code=404)
            return

        # 读取文件内容
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            self._json_response({"error": str(e)}, code=500)
            return

        # 简单处理：解析为节点
        from selfmind_app.parser import parse_memory_file
        nodes, links = parse_memory_file(import_path, content)

        # 保存到当前agent的memory目录
        config = load_config()
        memory_path = config.get("memory_path", str(Path.home() / ".hermes" / "memories"))

        # 追加到现有数据
        existing = _safe_read_existing_data() or {"nodes": [], "links": []}
        existing["nodes"].extend(nodes)
        existing["links"].extend(links)

        # 去重
        node_ids = set()
        unique_nodes = []
        for n in existing["nodes"]:
            if n.get("id") not in node_ids:
                node_ids.add(n.get("id"))
                unique_nodes.append(n)

        existing["nodes"] = unique_nodes

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

        self._json_response({"status": "ok", "imported": len(nodes), "message": f"Imported {len(nodes)} nodes"})

    def _json_response(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    # ─── v1 API Handlers ────────────────────────────────────────────────

    def _handle_v1_api(self, path: str):
        """处理 v1 API GET 请求"""
        from datetime import datetime

        if path == "/api/v1/changes":
            # 获取聚合变化
            since_str = self._get_query_param("since")
            since = None
            if since_str:
                try:
                    since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
                except ValueError:
                    self._json_response({"error": "Invalid since parameter"}, code=400)
                    return

            engine = _get_aggregation_engine()
            result = engine.aggregate_changes(since)

            self._json_response({
                "changes": [
                    {
                        "change_id": c.change_id,
                        "item_id": c.item_id,
                        "source": c.source,
                        "change_type": c.change_type,
                        "timestamp": c.timestamp.isoformat(),
                        "content": c.after.content[:200] if c.after else None,
                        "category": c.after.category if c.after else None,
                    }
                    for c in result.changes[:50]  # 限制返回数量
                ],
                "providers": [
                    {
                        "name": p.name,
                        "status": p.status,
                        "item_count": p.item_count,
                    }
                    for p in result.providers
                ],
                "stats": {
                    "total": result.total_count,
                    "created": result.created_count,
                    "updated": result.updated_count,
                    "deleted": result.deleted_count,
                }
            })
            return

        if path == "/api/v1/status":
            # 获取 Provider 状态
            engine = _get_aggregation_engine()
            status = engine.get_provider_status()
            self._json_response({
                "providers": status,
                "timestamp": datetime.now().isoformat()
            })
            return

        if path == "/api/v1/memories":
            # 获取所有记忆
            engine = _get_aggregation_engine()
            items = engine.get_all_memories()
            self._json_response({
                "memories": [
                    {
                        "id": m.id,
                        "source": m.source,
                        "category": m.category,
                        "content": m.content[:200],
                        "importance": m.importance,
                        "tags": m.tags,
                        "created_at": m.created_at.isoformat(),
                        "updated_at": m.updated_at.isoformat(),
                    }
                    for m in items[:100]
                ],
                "total": len(items)
            })
            return

        self._json_response({"error": "Not found"}, code=404)

    def _handle_v1_api_post(self, path: str):
        """处理 v1 API POST 请求"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        if path == "/api/v1/sync":
            # 触发同步
            try:
                body_json = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self._json_response({"error": "Invalid JSON"}, code=400)
                return

            force = body_json.get("force", False)

            # 刷新数据
            data = refresh_data()
            engine = _get_aggregation_engine()

            self._json_response({
                "status": "ok",
                "message": "Sync completed",
                "nodes": len(data.get("nodes", [])),
                "links": len(data.get("links", [])),
                "providers": engine.get_provider_status()
            })
            return

        self._json_response({"error": "Not found"}, code=404)

    def _get_query_param(self, key: str) -> Optional[str]:
        """获取 URL 查询参数"""
        import urllib.parse
        if "?" in self.path:
            query = self.path.split("?")[1]
            params = urllib.parse.parse_qs(query)
            result = params.get(key, [])
            return result[0] if result else None
        return None

    def log_message(self, format, *args):
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] {args[0]}")
