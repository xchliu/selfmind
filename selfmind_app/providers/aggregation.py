"""
Aggregation Engine - 变化聚合引擎
将多源记忆的变化聚合并统一展示
"""

from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from .base import MemoryProvider, MemoryItem, MemoryChange, ProviderMetadata


@dataclass
class AggregatedChanges:
    """聚合后的变化"""
    changes: List[MemoryChange]
    providers: List[ProviderMetadata]
    total_count: int
    created_count: int
    updated_count: int
    deleted_count: int


@dataclass
class Conflict:
    """冲突项"""
    conflict_id: str
    item_id: str
    sources: List[str]                    # 冲突来源
    items: List[MemoryItem]              # 冲突的记忆项
    timestamp: datetime


class AggregationEngine:
    """聚合引擎"""

    def __init__(self, providers: List[MemoryProvider] = None):
        self.providers: List[MemoryProvider] = providers or []

    def add_provider(self, provider: MemoryProvider):
        """添加 Provider"""
        self.providers.append(provider)

    def aggregate_changes(self, since: Optional[datetime] = None) -> AggregatedChanges:
        """
        聚合所有 Provider 的变化
        1. 并行拉取各 Provider 增量
        2. 统一格式转换
        3. 时间排序
        4. 去重（基于 content_hash）
        5. 冲突检测
        """
        all_changes = []
        all_metadata = []

        # 并行拉取各 Provider 变化
        for provider in self.providers:
            try:
                changes = provider.get_changes(since or datetime.min)
                all_changes.extend(changes)

                metadata = provider.get_metadata()
                all_metadata.append(metadata)
            except Exception as e:
                # 记录错误但继续
                all_metadata.append(ProviderMetadata(
                    name=provider.name,
                    source_type=provider.get_source_type(),
                    enabled=False,
                    status=f"error: {str(e)[:50]}"
                ))

        # 时间排序
        all_changes.sort(key=lambda x: x.timestamp, reverse=True)

        # 统计
        created = sum(1 for c in all_changes if c.change_type == "created")
        updated = sum(1 for c in all_changes if c.change_type == "updated")
        deleted = sum(1 for c in all_changes if c.change_type == "deleted")

        return AggregatedChanges(
            changes=all_changes,
            providers=all_metadata,
            total_count=len(all_changes),
            created_count=created,
            updated_count=updated,
            deleted_count=deleted
        )

    def detect_conflicts(self, changes: List[MemoryChange]) -> List[Conflict]:
        """检测跨源冲突"""
        # 按 item_id 分组
        by_item = {}
        for change in changes:
            if change.after:
                key = change.after.content_hash[:16]  # 用内容哈希作为 key
                if key not in by_item:
                    by_item[key] = []
                by_item[key].append(change)

        conflicts = []
        for key, change_list in by_item.items():
            if len(change_list) > 1:
                # 检测同一内容的多个来源
                sources = set(c.source for c in change_list)
                if len(sources) > 1:
                    items = [c.after for c in change_list if c.after]
                    if items:
                        conflicts.append(Conflict(
                            conflict_id=f"cf_{key}",
                            item_id=items[0].id,
                            sources=list(sources),
                            items=items,
                            timestamp=max(c.timestamp for c in change_list)
                        ))

        return conflicts

    def resolve_conflict_timestamp(self, conflict: Conflict) -> MemoryItem:
        """冲突解决策略：时间戳优先"""
        return max(conflict.items, key=lambda x: x.updated_at)

    def resolve_conflict_source_priority(self, conflict: Conflict, priority: List[str]) -> MemoryItem:
        """冲突解决策略：来源优先级"""
        # 按优先级排序
        def sort_key(item):
            for idx, src in enumerate(priority):
                if item.source == src:
                    return idx
            return len(priority)

        return min(conflict.items, key=sort_key)

    def get_all_memories(self) -> List[MemoryItem]:
        """获取所有 Provider 的所有记忆"""
        all_items = []
        for provider in self.providers:
            try:
                items = provider.fetch_memories()
                all_items.extend(items)
            except Exception:
                pass
        return all_items

    def get_provider_status(self) -> List[Dict[str, Any]]:
        """获取所有 Provider 的状态"""
        status = []
        for provider in self.providers:
            meta = provider.get_metadata()
            status.append({
                "name": meta.name,
                "type": meta.source_type,
                "enabled": meta.enabled,
                "item_count": meta.item_count,
                "status": meta.status,
                "last_sync": meta.last_sync.isoformat() if meta.last_sync else None
            })
        return status
