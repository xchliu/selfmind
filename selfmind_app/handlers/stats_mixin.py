"""Stats, poll, IQ, skills, and data-loading handler methods."""

import hashlib
import json
import math
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from selfmind_app.config import (
    CONFIG_FILE,
    DATA_FILE,
    SELFMIND_DIR,
    load_config,
    get_enabled_profiles,
)

logger = logging.getLogger(__name__)


class StatsMixin:
    """Handler methods for stats, poll, IQ, skills, and data loading."""

    def _handle_stats(self):
        """返回记忆各层的实时状态和关键指标，供 U 型沉淀页面使用。"""
        from pathlib import Path
        import subprocess

        home = Path.home()
        hermes_home = home / ".hermes"
        stats = {}

        # L1: 对话记忆 — session文件数
        sessions_dir = hermes_home / "sessions"
        if sessions_dir.exists():
            session_count = len([f for f in sessions_dir.iterdir() if f.name.endswith('.json')])
        else:
            session_count = 0
        stats['L1'] = {
            'status': 'ok',
            'metric': session_count,
            'metric_label': 'sessions',
            'detail': f'{session_count} 个历史会话'
        }

        # L2: 核心快照 — Memory/User容量
        memory_file = hermes_home / "memories" / "MEMORY.md"
        user_file = hermes_home / "memories" / "USER.md"
        mem_size = memory_file.stat().st_size if memory_file.exists() else 0
        user_size = user_file.stat().st_size if user_file.exists() else 0
        mem_max = 2200
        user_max = 1375
        mem_pct = round(mem_size / mem_max * 100) if mem_max > 0 else 0
        user_pct = round(user_size / user_max * 100) if user_max > 0 else 0
        mem_status = 'err' if mem_pct > 90 else 'warn' if mem_pct > 75 else 'ok'
        stats['L2'] = {
            'status': mem_status,
            'metric': mem_pct,
            'metric_label': 'capacity',
            'detail': f'MEM {mem_size}/{mem_max} ({mem_pct}%) · USER {user_size}/{user_max} ({user_pct}%)'
        }

        # L3: 身份推理 — Honcho健康+结论数
        honcho_status = 'offline'
        conclusion_count = 0
        try:
            import urllib.request
            resp = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)
            if resp.status == 200:
                honcho_status = 'ok'
                # Try to get conclusion count from poll data
                try:
                    poll_resp = urllib.request.urlopen('http://127.0.0.1:8000/v3/workspaces/hermes/peers/liuxiaocheng/conclusions', timeout=3)
                    import json as _json
                    conclusions_data = _json.loads(resp.read())
                    conclusion_count = len(conclusions_data) if isinstance(conclusions_data, list) else 0
                except Exception:
                    pass
        except Exception:
            pass
        # Also check from SelfMind's honcho_api module
        try:
            config = load_config()
            enabled = get_enabled_profiles(config)
            if 'honcho' in enabled:
                from selfmind_app.honcho_api import honcho_api_health
                honcho_cfg = config['source']['profiles']['honcho'].get('api', {})
                honcho_info = honcho_api_health(honcho_cfg.get('base_url', 'http://localhost:8000/v3'))
                if honcho_info.get('status') == 'ok':
                    honcho_status = 'ok'
                    conclusion_count = honcho_info.get('conclusion_count', 0)
        except Exception:
            pass
        stats['L3'] = {
            'status': honcho_status,
            'metric': conclusion_count,
            'metric_label': 'conclusions',
            'detail': f'Honcho {honcho_status} · {conclusion_count} conclusions'
        }

        # L4: 可视化图谱 — SelfMind进程+wiki节点数
        # If we're serving this API, SelfMind IS running
        selfmind_running = True
        wiki_nodes = 0
        try:
            data = self._load_data()
            wiki_nodes = len(data.get('nodes', []))
        except Exception:
            pass
        stats['L4'] = {
            'status': 'ok' if selfmind_running else 'err',
            'metric': wiki_nodes,
            'metric_label': 'nodes',
            'detail': f'SelfMind {"running" if selfmind_running else "offline"} · {wiki_nodes} 图谱节点'
        }

        # L5: 程序记忆 — skill数量
        skills_dir = hermes_home / "skills"
        skill_count = len([d for d in skills_dir.iterdir() if d.is_dir()]) if skills_dir.exists() else 0
        stats['L5'] = {
            'status': 'ok',
            'metric': skill_count,
            'metric_label': 'skills',
            'detail': f'{skill_count} 个可复用工作流'
        }

        # L6: 知识库 — wiki实体文件数
        wiki_dir = Path(home / "Documents" / "aiworkspace" / "wiki" / "entities")
        entity_count = len([f for f in wiki_dir.iterdir() if f.name.endswith('.md')]) if wiki_dir.exists() else 0
        stats['L6'] = {
            'status': 'ok',
            'metric': entity_count,
            'metric_label': 'entities',
            'detail': f'{entity_count} 个结构化实体'
        }

        self._json_response(stats)

    def _handle_poll(self):
        """轻量轮询接口：返回记忆源文件的修改时间戳 + Honcho API状态，用于前端检测变化。"""
        import hashlib
        from pathlib import Path
        
        config = load_config()
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
        
        # Check Honcho API health if honcho profile has api config
        honcho_info = {"status": "disabled"}
        honcho_mtime = 0
        source_cfg = config.get("source", {})
        profiles = source_cfg.get("profiles", {})
        mode = source_cfg.get("mode", "auto")
        
        # Only check Honcho if it's an enabled profile with api config
        enabled_profiles = get_enabled_profiles(config)
        if "honcho" in enabled_profiles:
            honcho_profile = profiles.get("honcho", {})
            api_config = honcho_profile.get("api")
            if api_config and api_config.get("type") == "honcho":
                from selfmind_app.honcho_api import honcho_api_health
                honcho_info = honcho_api_health(api_config.get("base_url", "http://localhost:8000/v3"))
                # Use conclusion count as a "mtime" proxy — changes when new conclusions are added
                honcho_mtime = honcho_info.get("conclusion_count", 0)
                total_mtime += honcho_mtime * 1000  # Scale up so changes are detectable
        
        # 用所有文件的 mtime 拼接后取 hash，作为单一比较值
        mtime_str = str(total_mtime)
        poll_hash = hashlib.md5(mtime_str.encode()).hexdigest()
        
        self._json_response({
            "hash": poll_hash,
            "files": files_info,
            "honcho": honcho_info,
            "timestamp": datetime.now().isoformat(),
        })

    def _load_data(self):
        if DATA_FILE.exists():
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Backfill timestamps for old data files that predate createdAt/updatedAt.
            from selfmind_app.http_handler import _apply_node_timestamps
            if any("createdAt" not in node or "updatedAt" not in node for node in data.get("nodes", [])):
                data = _apply_node_timestamps(data, None)
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            return data
        from selfmind_app.http_handler import refresh_data
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