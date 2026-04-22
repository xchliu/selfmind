"""
Skills Provider - 技能库数据源
扫描 ~/.hermes/skills/ 下的 SKILL.md 文件，转换为统一 MemoryItem 格式
作为独立数据源出现在数据源状态面板中
"""
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import hashlib

from .base import MemoryProvider, MemoryItem, MemoryChange, ProviderMetadata


class SkillsProvider(MemoryProvider):
    """技能库 Provider — 将 ~/.hermes/skills/ 下的技能作为数据源暴露"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("skills")
        self.config = config or {}
        self._skills_dir = Path.home() / ".hermes" / "skills"
        self._cache: Dict[str, MemoryItem] = {}
        self._last_hash: Optional[str] = None

    def get_source_type(self) -> str:
        return "skills"

    def _scan_all_skills(self) -> List[dict]:
        """扫描所有 SKILL.md，返回技能条目列表（与 http_handler._scan_skills 类似但更轻量）"""
        if not self._skills_dir.exists():
            return []

        skill_files = list(self._skills_dir.rglob("SKILL.md"))
        skills = []

        for sf in skill_files:
            try:
                content = sf.read_text(encoding="utf-8")
                name = sf.parent.name
                desc = ""
                cat = ""
                subcat = ""

                # Parse YAML frontmatter
                fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
                if fm_match:
                    fm = fm_match.group(1)
                    for line in fm.split("\n"):
                        if line.startswith("name:"):
                            name = line.split(":", 1)[1].strip().strip("'\"")
                        elif line.startswith("description:"):
                            desc = line.split(":", 1)[1].strip().strip("'\"")

                # Determine category/subcategory from path
                rel_path = sf.parent.relative_to(self._skills_dir)
                if len(rel_path.parts) >= 2:
                    cat = rel_path.parts[0]
                    subcat = rel_path.parts[1] if len(rel_path.parts) > 1 else ""
                elif len(rel_path.parts) == 1:
                    cat = rel_path.parts[0]
                    subcat = ""

                # Estimate complexity
                n_steps = len(re.findall(r"^\d+\.", content, re.MULTILINE))
                n_code_blocks = content.count("```")
                n_sections = len(re.findall(r"^#{1,3}\s", content, re.MULTILINE))
                complexity = min(1.0, (n_steps * 0.05 + n_code_blocks * 0.03 + n_sections * 0.04))

                skills.append({
                    "name": name,
                    "description": desc[:200] if desc else content[:200].replace("\n", " "),
                    "category": cat or "uncategorized",
                    "subcategory": subcat,
                    "complexity": round(complexity, 2),
                    "content_length": len(content),
                    "path": str(sf.parent),
                    "content": content,
                })
            except (OSError, UnicodeDecodeError):
                continue

        return skills

    def _skills_to_memory_items(self, skills: List[dict]) -> List[MemoryItem]:
        """将技能条目转换为 MemoryItem"""
        items = []
        now = datetime.now()

        for skill in skills:
            source_id = f"skill_{skill['name']}_{self._compute_hash(skill['name'])}"
            content_text = f"## {skill['name']}\n\n{skill['description']}\n\nCategory: {skill['category']}/{skill['subcategory']}\nComplexity: {skill['complexity']}\nPath: {skill['path']}"

            item = MemoryItem(
                id=self._generate_id(self.name, source_id),
                source="skills",
                source_id=source_id,
                content=content_text,
                content_hash=self._compute_hash(content_text),
                created_at=now,
                updated_at=now,
                accessed_at=now,
                access_count=0,
                importance=min(1.0, 0.4 + skill["complexity"] * 0.4),
                category="skill",
                tags=["skill", skill["category"], skill["subcategory"]] if skill["subcategory"] else ["skill", skill["category"]],
                metadata={
                    "name": skill["name"],
                    "category": skill["category"],
                    "subcategory": skill["subcategory"],
                    "complexity": skill["complexity"],
                    "content_length": skill["content_length"],
                    "path": skill["path"],
                }
            )
            items.append(item)

        return items

    def fetch_memories(self, since: Optional[datetime] = None) -> List[MemoryItem]:
        """获取所有技能记忆"""
        skills = self._scan_all_skills()
        items = self._skills_to_memory_items(skills)

        # 更新缓存
        self._cache = {item.id: item for item in items}
        content_hash_input = "|".join(sorted(s["name"] for s in skills))
        self._last_hash = hashlib.sha256(content_hash_input.encode("utf-8")).hexdigest()[:16]

        # 如果指定了 since，过滤更新
        if since:
            items = [item for item in items if item.updated_at >= since]

        return items

    def get_changes(self, since: datetime) -> List[MemoryChange]:
        """获取增量变化（简化实现：全量扫描对比缓存）"""
        current_items = {item.id: item for item in self.fetch_memories(since=None)}
        changes = []

        # 新增或更新的
        for item_id, item in current_items.items():
            if item_id not in self._cache:
                changes.append(MemoryChange(
                    change_id=f"skill_{item_id}_created",
                    item_id=item_id,
                    source=self.name,
                    change_type="created",
                    before=None,
                    after=item,
                    timestamp=item.created_at,
                ))
            elif self._cache[item_id].content_hash != item.content_hash:
                changes.append(MemoryChange(
                    change_id=f"skill_{item_id}_updated",
                    item_id=item_id,
                    source=self.name,
                    change_type="updated",
                    before=self._cache[item_id],
                    after=item,
                    timestamp=datetime.now(),
                ))

        # 删除的
        for item_id in self._cache:
            if item_id not in current_items:
                changes.append(MemoryChange(
                    change_id=f"skill_{item_id}_deleted",
                    item_id=item_id,
                    source=self.name,
                    change_type="deleted",
                    before=self._cache[item_id],
                    after=None,
                    timestamp=datetime.now(),
                ))

        # 按时间过滤
        changes = [c for c in changes if c.timestamp >= since]
        return changes

    def get_metadata(self) -> ProviderMetadata:
        """获取元信息"""
        skills = self._scan_all_skills()
        return ProviderMetadata(
            name=self.name,
            source_type=self.get_source_type(),
            enabled=True,
            item_count=len(skills),
            last_sync=datetime.now(),
            status="connected" if self._skills_dir.exists() else "disconnected",
        )
