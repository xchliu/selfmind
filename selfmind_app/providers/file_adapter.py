"""
File Adapter - 本地文件 Provider
读取 MEMORY.md 和 USER.md，转换为统一 MemoryItem 格式
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import hashlib

from .base import MemoryProvider, MemoryItem, MemoryChange, ProviderMetadata


class FileAdapter(MemoryProvider):
    """本地文件 Provider"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("hermes")
        self.config = config
        self._cache: Dict[str, MemoryItem] = {}
        self._last_hash: Optional[str] = None

        # 获取源配置
        source_cfg = config.get("source", {})
        profiles = source_cfg.get("profiles", {})
        active = source_cfg.get("active_profile", "hermes")
        profile = profiles.get(active, {})

        self.home = Path(profile.get("home", str(Path.home() / ".hermes")))
        self.files = profile.get("memory_files", ["memories/MEMORY.md", "memories/USER.md"])
        self.fallback = profile.get("memory_files_fallback", ["memory.md", "user.md"])
        self.separator = config.get("section_separator", "§")

    def get_source_type(self) -> str:
        return "file"

    def _resolve_file_path(self, relative_path: str) -> Optional[Path]:
        """解析文件路径"""
        path = self.home / relative_path
        if path.exists():
            return path

        # 尝试 fallback
        for fb in self.fallback:
            path = self.home / fb
            if path.exists():
                return path
        return None

    def _read_memory_files(self) -> str:
        """读取所有记忆文件"""
        contents = []
        for rel_path in self.files:
            path = self._resolve_file_path(rel_path)
            if path:
                try:
                    content = path.read_text(encoding="utf-8")
                    contents.append(f"# {path.name}\n{content}")
                except (OSError, UnicodeDecodeError):
                    pass

        # 检查是否有 fallback 文件
        if not contents:
            for fb in self.fallback:
                path = self.home / fb
                if path.exists():
                    try:
                        content = path.read_text(encoding="utf-8")
                        contents.append(f"# {path.name}\n{content}")
                    except (OSError, UnicodeDecodeError):
                        pass

        return "\n\n".join(contents)

    def _parse_memory_items(self, content: str) -> List[MemoryItem]:
        """解析 Markdown 内容为 MemoryItem"""
        items = []
        now = datetime.now()

        # 按 section separator 分割
        sections = content.split(self.separator)
        file_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

        for idx, section in enumerate(sections):
            section = section.strip()
            if not section:
                continue

            # 跳过注释和空行
            if section.startswith('#') or section.startswith('//'):
                # 可能包含文件名
                continue

            # 解析记忆条目
            # 格式: [分类] 内容 或 直接内容
            lines = section.split('\n')
            first_line = lines[0].strip() if lines else ""

            # 提取分类和内容
            category = "memory"
            content_text = section

            # 尝试从开头提取分类 [category]
            cat_match = re.match(r'\[([^\]]+)\]', first_line)
            if cat_match:
                category = cat_match.group(1).lower()
                content_text = '\n'.join(lines[1:]).strip()

            # 提取标签
            tags = re.findall(r'#(\w+)', content_text)

            # 提取重要性 (如果有)
            importance = 0.5
            imp_match = re.search(r'importance[:\s]*(\d+\.?\d*)', content_text, re.IGNORECASE)
            if imp_match:
                importance = float(imp_match.group(1))
                importance = max(0, min(1, importance))

            # 生成 source_id
            source_id = f"line_{idx}_{self._compute_hash(content_text[:50])}"

            # 创建 MemoryItem
            item = MemoryItem(
                id=self._generate_id(self.name, source_id),
                source="file",
                source_id=source_id,
                content=content_text[:500],  # 限制长度
                content_hash=self._compute_hash(content_text),
                created_at=now,
                updated_at=now,
                accessed_at=now,
                access_count=0,
                importance=importance,
                category=category,
                tags=tags[:5],  # 最多5个标签
                metadata={
                    "file_hash": file_hash,
                    "raw_section": section[:200]
                }
            )
            items.append(item)

        return items

    def fetch_memories(self, since: Optional[datetime] = None) -> List[MemoryItem]:
        """获取所有记忆"""
        content = self._read_memory_files()
        items = self._parse_memory_items(content)

        # 更新缓存
        self._cache = {item.id: item for item in items}
        self._last_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

        # 如果指定了 since，过滤更新
        if since:
            items = [item for item in items if item.updated_at >= since]

        return items

    def get_changes(self, since: datetime) -> List[MemoryChange]:
        """获取增量变化"""
        # 先获取当前所有记忆
        current_items = self.fetch_memories()
        current_map = {item.source_id: item for item in current_items}

        # 从缓存获取之前的记忆
        previous_items = self._cache

        changes = []
        now = datetime.now()

        # 检测新增和更新
        for source_id, item in current_map.items():
            prev = previous_items.get(self._generate_id(self.name, source_id))

            if prev is None:
                # 新增
                changes.append(MemoryChange(
                    change_id=f"ch_{self.name}_{source_id}_{now.timestamp()}",
                    item_id=item.id,
                    source=self.name,
                    change_type="created",
                    before=None,
                    after=item,
                    timestamp=item.created_at
                ))
            elif prev.content_hash != item.content_hash:
                # 更新
                changes.append(MemoryChange(
                    change_id=f"ch_{self.name}_{source_id}_{now.timestamp()}",
                    item_id=item.id,
                    source=self.name,
                    change_type="updated",
                    before=prev,
                    after=item,
                    timestamp=item.updated_at
                ))

        # 检测删除（之前有但现在没有的）
        current_ids = set(current_map.keys())
        for item_id, prev in previous_items.items():
            if prev.source_id not in current_ids:
                changes.append(MemoryChange(
                    change_id=f"ch_{self.name}_{prev.source_id}_{now.timestamp()}",
                    item_id=prev.id,
                    source=self.name,
                    change_type="deleted",
                    before=prev,
                    after=None,
                    timestamp=now
                ))

        return changes

    def get_metadata(self) -> ProviderMetadata:
        """获取 Provider 元信息"""
        items = self.fetch_memories()
        return ProviderMetadata(
            name=self.name,
            source_type="file",
            enabled=True,
            item_count=len(items),
            last_sync=datetime.now(),
            status="connected"
        )

    def get_file_hash(self) -> Optional[str]:
        """获取当前文件内容的哈希"""
        content = self._read_memory_files()
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

    def has_changed(self) -> bool:
        """检查文件是否有变化"""
        current_hash = self.get_file_hash()
        if current_hash is None:
            return False
        return current_hash != self._last_hash
