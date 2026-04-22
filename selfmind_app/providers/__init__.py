"""
SelfMind Providers - 多源记忆适配器层
"""

from .base import MemoryProvider, MemoryItem, MemoryChange, ProviderMetadata
from .file_adapter import FileAdapter
from .skills_provider import SkillsProvider
from .aggregation import AggregationEngine, AggregatedChanges, Conflict

__all__ = [
    "MemoryProvider",
    "MemoryItem",
    "MemoryChange",
    "ProviderMetadata",
    "FileAdapter",
    "SkillsProvider",
    "AggregationEngine",
    "AggregatedChanges",
    "Conflict",
]
