"""
遗忘引擎 - SelfMind V2
决定"什么该遗忘"，实现智能记忆衰减
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class ForgetConfig:
    """遗忘引擎配置"""
    decay_half_life_days: float = 90.0      # 信息半衰期（天）
    access_decay_threshold_days: int = 30    # 多少天不访问开始衰减
    forget_threshold: float = 0.8            # 遗忘阈值（0-1）
    privacy_acceleration: float = 1.5        # 敏感信息遗忘加速系数
    min_importance: float = 0.1              # 最低重要性（低于此不遗忘）
    soft_delete: bool = True                 # 软删除（可恢复）


class ForgetterEngine:
    """遗忘引擎"""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent.parent / "data"
        self.data_file = self.data_dir / "data.json"
        self.config = ForgetConfig()
        
    def _load_data(self) -> Dict:
        """加载记忆数据"""
        if not self.data_file.exists():
            return {"memories": []}
        with open(self.data_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_data(self, data: Dict):
        """保存记忆数据"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def calculate_decay(self, created_at: str, current_time: datetime = None) -> float:
        """
        计算时间衰减分数
        使用指数衰减: score = e^(-λ * t)
        半衰期: T_half = ln(2) / λ
        """
        if current_time is None:
            current_time = datetime.now()
            
        try:
            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            # 转换为本地时间
            created = created.replace(tzinfo=None)
            age_days = (current_time - created).days
        except (ValueError, AttributeError):
            return 0.0  # 无法解析时间，不遗忘
        
        # 衰减系数 λ = ln(2) / 半衰期
        import math
        decay_constant = math.log(2) / self.config.decay_half_life_days
        decay_score = 1 - math.exp(-decay_constant * age_days)
        
        return min(decay_score, 1.0)
    
    def calculate_access_decay(self, last_accessed: Optional[str], current_time: datetime = None) -> float:
        """
        计算访问频率衰减
        长时间未访问的记忆更容易被遗忘
        """
        if current_time is None:
            current_time = datetime.now()
            
        if not last_accessed:
            return 0.5  # 从未访问，给中等分数
            
        try:
            accessed = datetime.fromisoformat(last_accessed.replace('Z', '+00:00'))
            accessed = accessed.replace(tzinfo=None)
            days_since_access = (current_time - accessed).days
        except (ValueError, AttributeError):
            return 0.5
        
        if days_since_access < self.config.access_decay_threshold_days:
            return 0.0  # 近期访问过，不衰减
        
        # 超过阈值后加速衰减
        excess_days = days_since_access - self.config.access_decay_threshold_days
        access_decay = min(excess_days / 90, 1.0)  # 90天后完全遗忘访问权重
        
        return access_decay
    
    def calculate_importance_weight(self, memory: Dict) -> float:
        """
        计算重要性权重
        基于：用户反馈、交互频率、唯一性
        """
        importance = 0.5  # 基础分数
        
        # 用户标记的重要性
        if 'importance' in memory:
            importance = memory['importance']
        
        # 交互频率（评论、引用等）
        interactions = memory.get('interactions', 0)
        if interactions > 10:
            importance += 0.2
        elif interactions > 5:
            importance += 0.1
            
        # 是否被其他记忆引用（唯一性）
        references = memory.get('references', [])
        if len(references) > 3:
            importance += 0.15
        elif len(references) > 0:
            importance += 0.05
            
        # 分类权重：某些分类的记忆更重要
        category_weights = {
            'insight': 0.2,
            'goal': 0.2,
            'relationship': 0.1,
            'note': -0.1,
            'log': -0.15
        }
        category = memory.get('category', 'note')
        importance += category_weights.get(category, 0)
        
        return max(0.0, min(importance, 1.0))
    
    def calculate_privacy_decay(self, memory: Dict) -> float:
        """
        计算隐私敏感度衰减
        敏感信息可以设置更快的遗忘速度
        """
        privacy_tags = ['password', 'secret', 'api_key', 'credential', 'private']
        tags = [t.lower() for t in memory.get('tags', [])]
        
        # 包含敏感标签，加速遗忘
        for tag in privacy_tags:
            if tag in tags or any(tag in t for t in tags):
                return self.config.privacy_acceleration
        
        # 检查内容是否包含敏感模式
        content = memory.get('content', '').lower()
        sensitive_patterns = ['password', 'api_key', 'secret', 'token', 'credential']
        for pattern in sensitive_patterns:
            if pattern in content:
                return self.config.privacy_acceleration
        
        return 1.0  # 正常衰减
    
    def calculate_forget_score(self, memory: Dict, current_time: datetime = None) -> float:
        """
        计算综合遗忘分数
        分数越高，越应该被遗忘（0-1）
        """
        # 时间衰减
        created_at = memory.get('created_at', '')
        time_decay = self.calculate_decay(created_at, current_time)
        
        # 访问频率衰减
        last_accessed = memory.get('last_accessed')
        access_decay = self.calculate_access_decay(last_accessed, current_time)
        
        # 重要性权重（重要信息遗忘更慢）
        importance = self.calculate_importance_weight(memory)
        importance_factor = 1 - importance  # 重要性低 = 更容易忘
        
        # 隐私敏感度
        privacy_factor = self.calculate_privacy_decay(memory)
        
        # 综合遗忘分数
        forget_score = (
            time_decay * 0.4 +
            access_decay * 0.3 +
            importance_factor * 0.2 * privacy_factor
        )
        
        return min(forget_score, 1.0)
    
    def get_memories_to_forget(self, threshold: float = None) -> List[Dict]:
        """
        获取应该遗忘的记忆
        threshold: 遗忘分数阈值（默认使用配置）
        """
        if threshold is None:
            threshold = self.config.forget_threshold
            
        data = self._load_data()
        memories = data.get('memories', [])
        
        to_forget = []
        current_time = datetime.now()
        
        for memory in memories:
            # 跳过已经遗忘的
            if memory.get('status') == 'forgotten':
                continue
                
            # 跳过固定的记忆
            if memory.get('pinned', False):
                continue
                
            forget_score = self.calculate_forget_score(memory, current_time)
            
            if forget_score >= threshold:
                memory['forget_score'] = forget_score
                memory['forget_reason'] = self._get_forget_reason(memory, forget_score)
                to_forget.append(memory)
        
        # 按遗忘分数排序
        to_forget.sort(key=lambda x: x.get('forget_score', 0), reverse=True)
        
        return to_forget
    
    def _get_forget_reason(self, memory: Dict, score: float) -> str:
        """生成遗忘原因描述"""
        reasons = []
        
        created_at = memory.get('created_at', '')
        time_decay = self.calculate_decay(created_at)
        if time_decay > 0.7:
            reasons.append("长时间未访问")
            
        last_accessed = memory.get('last_accessed')
        access_decay = self.calculate_access_decay(last_accessed)
        if access_decay > 0.5:
            reasons.append("访问频率低")
            
        importance = self.calculate_importance_weight(memory)
        if importance < 0.3:
            reasons.append("重要性低")
            
        if not reasons:
            reasons.append("自然衰减")
            
        return "; ".join(reasons)
    
    def run_forgetting(self, memory_ids: List[str] = None, dry_run: bool = False) -> Dict[str, Any]:
        """
        执行遗忘操作
        memory_ids: 指定要遗忘的记忆ID列表（None表示自动选择）
        dry_run: True则只返回结果不实际删除
        """
        if memory_ids is None:
            # 自动选择应该遗忘的记忆
            to_forget = self.get_memories_to_forget()
            memory_ids = [m['id'] for m in to_forget]
        
        data = self._load_data()
        memories = data.get('memories', [])
        
        forgotten = []
        
        for memory in memories:
            if memory['id'] in memory_ids:
                if self.config.soft_delete:
                    # 软删除：标记状态，可恢复
                    memory['status'] = 'forgotten'
                    memory['forgotten_at'] = datetime.now().isoformat()
                else:
                    # 硬删除：直接移除
                    memories.remove(memory)
                    
                forgotten.append(memory['id'])
        
        if not dry_run:
            self._save_data(data)
        
        return {
            "forgotten_count": len(forgotten),
            "forgotten_ids": forgotten,
            "soft_delete": self.config.soft_delete,
            "dry_run": dry_run
        }
    
    def restore_memory(self, memory_id: str) -> bool:
        """恢复已遗忘的记忆"""
        data = self._load_data()
        memories = data.get('memories', [])
        
        for memory in memories:
            if memory['id'] == memory_id and memory.get('status') == 'forgotten':
                memory['status'] = 'active'
                memory['restored_at'] = datetime.now().isoformat()
                self._save_data(data)
                return True
                
        return False
    
    def run_full_cycle(self) -> Dict[str, Any]:
        """
        运行完整的遗忘周期
        1. 分析所有记忆的遗忘分数
        2. 执行遗忘
        3. 生成报告
        """
        # 分析阶段
        data = self._load_data()
        memories = [m for m in data.get('memories', []) if m.get('status') != 'forgotten']
        
        analysis = {
            "total_active": len(memories),
            "to_forget": [],
            "score_distribution": {
                "high_risk": 0,  # > 0.8
                "medium_risk": 0,  # 0.5 - 0.8
                "low_risk": 0  # < 0.5
            }
        }
        
        current_time = datetime.now()
        
        for memory in memories:
            score = self.calculate_forget_score(memory, current_time)
            
            if score >= 0.8:
                analysis["score_distribution"]["high_risk"] += 1
            elif score >= 0.5:
                analysis["score_distribution"]["medium_risk"] += 1
            else:
                analysis["score_distribution"]["low_risk"] += 1
                
            if score >= self.config.forget_threshold:
                analysis["to_forget"].append({
                    "id": memory['id'],
                    "title": memory.get('title', '')[:50],
                    "score": round(score, 3)
                })
        
        # 执行遗忘（软删除）
        result = self.run_forgetting(dry_run=False)
        
        analysis["result"] = result
        analysis["timestamp"] = datetime.now().isoformat()
        
        return analysis


if __name__ == "__main__":
    # 测试
    engine = ForgetterEngine()
    result = engine.run_full_cycle()
    print(json.dumps(result, ensure_ascii=False, indent=2))
