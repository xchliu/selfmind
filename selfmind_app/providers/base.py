"""
Provider Adapter Layer - 抽象基类
定义多源记忆聚合的统一接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
import hashlib


@dataclass
class MemoryItem:
    """统一记忆项"""
    id: str                                    # 全局唯一 ID
    source: str                                # 来源: file/hermes/honcho/mem0
    source_id: str                             # 原始来源的 ID
    content: str                               # 记忆内容
    content_hash: str                          # 内容哈希（去重用）
    created_at: datetime                       # 创建时间
    updated_at: datetime                       # 更新时间
    accessed_at: datetime                      # 最后访问时间
    access_count: int = 0                      # 访问次数
    importance: float = 0.5                     # 重要性 0-1
    category: str = "memory"                   # 分类
    tags: List[str] = field(default_factory=list)  # 标签
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外信息


@dataclass
class MemoryChange:
    """记忆变化事件"""
    change_id: str
    item_id: str
    source: str
    change_type: str                           # created/updated/deleted
    before: Optional[MemoryItem]
    after: Optional[MemoryItem]
    timestamp: datetime


@dataclass
class ProviderMetadata:
    """Provider 元信息"""
    name: str
    source_type: str
    enabled: bool
    item_count: int = 0
    last_sync: Optional[datetime] = None
    status: str = "unknown"                    # connected/disconnected/error


class MemoryProvider(ABC):
    """记忆 Provider 抽象基类"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def fetch_memories(self, since: Optional[datetime] = None) -> List[MemoryItem]:
        """获取记忆列表，可选时间范围"""
        pass

    @abstractmethod
    def get_changes(self, since: datetime) -> List[MemoryChange]:
        """获取增量变化"""
        pass

    @abstractmethod
    def get_metadata(self) -> ProviderMetadata:
        """获取 Provider 元信息"""
        pass

    @abstractmethod
    def get_source_type(self) -> str:
        """获取来源类型标识"""
        pass

    def _compute_hash(self, content: str) -> str:
        """计算内容哈希"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

    def _generate_id(self, source: str, source_id: str) -> str:
        """生成全局唯一 ID"""
        return f"{source}_{source_id}"
