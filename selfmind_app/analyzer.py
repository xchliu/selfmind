"""
分析引擎 - SelfMind V2
模式识别、知识图谱更新、洞察生成
Now supports graph data (nodes/links from data.json).
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, asdict

from selfmind_app.config import DATA_FILE


@dataclass
class AnalysisConfig:
    """分析引擎配置"""
    min_pattern_frequency: int = 3       # 最小模式频率
    temporal_pattern_window_days: int = 7 # 时间模式窗口（天）
    max_topics: int = 20                  # 返回的最大主题数
    insight_confidence_threshold: float = 0.6 # 洞察置信度阈值


class AnalyzerEngine:
    """分析引擎"""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent.parent / "data"
        self.data_file = self.data_dir / "data.json"
        self.config = AnalysisConfig()
    
    # ── Graph Data Support (nodes/links from data.json) ──────────────
    
    def load_graph_data(self) -> Dict:
        """Load graph data from data.json (nodes/links format)."""
        if not DATA_FILE.exists():
            return {"nodes": [], "links": []}
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def get_nodes_as_memories(self) -> List[Dict]:
        """Convert graph nodes to memory-like format for analysis."""
        data = self.load_graph_data()
        nodes = data.get("nodes", [])
        
        memories = []
        for node in nodes:
            if node.get("category") != "memory":
                continue
            
            memory = {
                "id": node.get("id", ""),
                "label": node.get("label", ""),
                "content": node.get("description", ""),
                "primary": node.get("primary", ""),
                "secondary": node.get("secondary", ""),
                "group": node.get("group", ""),
                "importance": node.get("importance", 0),
                "access_count": node.get("access_count", 0),
                "created_at": node.get("createdAt", ""),
                "updated_at": node.get("updatedAt", ""),
            }
            memories.append(memory)
        return memories
    
    def analyze_importance_from_graph(self) -> Dict:
        """Analyze importance distribution from graph nodes."""
        memories = self.get_nodes_as_memories()
        
        if not memories:
            return {"message": "No memory nodes found", "analysis": {}}
        
        # Calculate importance statistics
        importances = [m.get("importance", 0) for m in memories]
        avg_importance = sum(importances) / len(importances)
        max_importance = max(importances) if importances else 0
        min_importance = min(importances) if importances else 0
        
        # Find high/low importance memories
        high_importance = [m for m in memories if m.get("importance", 0) >= 0.7]
        low_importance = [m for m in memories if m.get("importance", 0) < 0.3]
        
        # By primary category
        by_category = defaultdict(list)
        for m in memories:
            by_category[m.get("primary", "unknown")].append(m.get("importance", 0))
        
        category_avg = {
            cat: sum(imps) / len(imps) if imps else 0
            for cat, imps in by_category.items()
        }
        
        return {
            "total_memories": len(memories),
            "statistics": {
                "avg_importance": round(avg_importance, 3),
                "max_importance": round(max_importance, 3),
                "min_importance": round(min_importance, 3),
                "high_importance_count": len(high_importance),
                "low_importance_count": len(low_importance),
            },
            "by_category": {k: round(v, 3) for k, v in category_avg.items()},
            "top_memories": [
                {"id": m["id"], "label": m.get("label", "")[:30], "importance": m.get("importance", 0)}
                for m in sorted(memories, key=lambda x: x.get("importance", 0), reverse=True)[:10]
            ]
        }
    
    def extract_insights_from_graph(self) -> Dict:
        """Extract insights from graph data."""
        data = self.load_graph_data()
        nodes = data.get("nodes", [])
        links = data.get("links", [])
        
        # Filter memory nodes
        memory_nodes = [n for n in nodes if n.get("category") == "memory"]
        
        insights = {
            "total_memories": len(memory_nodes),
            "total_connections": len(links),
            "categories": list(set(n.get("primary", "unknown") for n in memory_nodes)),
            "insights": []
        }
        
        # Insight: Orphan memories (no connections)
        connected_ids = set()
        for link in links:
            connected_ids.add(link.get("source"))
            connected_ids.add(link.get("target"))
        
        orphans = [n for n in memory_nodes if n.get("id") not in connected_ids]
        if orphans:
            insights["insights"].append({
                "type": "orphan_memories",
                "message": f"发现 {len(orphans)} 条孤立记忆（无关联）",
                "count": len(orphans)
            })
        
        # Insight: Over-connected nodes
        connection_counts = Counter()
        for link in links:
            connection_counts[link.get("source")] += 1
            connection_counts[link.get("target")] += 1
        
        hub_nodes = [n for n in memory_nodes if connection_counts.get(n.get("id"), 0) >= 5]
        if hub_nodes:
            insights["insights"].append({
                "type": "hub_nodes",
                "message": f"发现 {len(hub_nodes)} 个枢纽记忆（5+关联）",
                "count": len(hub_nodes)
            })
        
        # Insight: Category imbalance
        category_counts = Counter(n.get("primary", "unknown") for n in memory_nodes)
        if len(category_counts) > 0:
            max_cat = max(category_counts.values())
            min_cat = min(category_counts.values())
            if max_cat > min_cat * 3:
                insights["insights"].append({
                    "type": "category_imbalance",
                    "message": "记忆分布不均衡，部分类别过于集中",
                    "distribution": dict(category_counts)
                })
        
        return insights
    def _load_data(self) -> Dict:
        """加载记忆数据"""
        if not self.data_file.exists():
            return {"memories": []}
        with open(self.data_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def analyze_patterns(self, memories: List[Dict] = None) -> Dict[str, Any]:
        """
        分析记忆模式
        返回：时间模式、标签模式、内容模式
        """
        if memories is None:
            data = self._load_data()
            memories = data.get('memories', [])
        
        patterns = {
            "temporal": self._analyze_temporal_patterns(memories),
            "tag": self._analyze_tag_patterns(memories),
            "content": self._analyze_content_patterns(memories)
        }
        
        return patterns
    
    def _analyze_temporal_patterns(self, memories: List[Dict]) -> Dict:
        """分析时间模式"""
        # 按日期分组
        daily_counts = Counter()
        weekly_counts = Counter()
        
        for memory in memories:
            try:
                created = memory.get('created_at', '')
                if not created:
                    continue
                dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                date = dt.date()
                
                daily_counts[date.isoformat()] += 1
                
                # 周几
                weekday = dt.strftime('%A')
                weekly_counts[weekday] += 1
            except (ValueError, AttributeError):
                continue
        
        # 找出峰值时间
        peak_day = weekly_counts.most_common(1)[0] if weekly_counts else ('', 0)
        
        return {
            "daily_distribution": dict(daily_counts.most_common(30)),
            "weekly_distribution": dict(weekly_counts),
            "peak_weekday": peak_day[0],
            "total_days_with_activity": len(daily_counts)
        }
    
    def _analyze_tag_patterns(self, memories: List[Dict]) -> Dict:
        """分析标签模式"""
        tag_counts = Counter()
        tag_cooccurrence = defaultdict(Counter)  # 标签共现
        
        for memory in memories:
            tags = memory.get('tags', [])
            if not isinstance(tags, list):
                tags = [tags] if tags else []
            
            for tag in tags:
                tag_counts[tag] += 1
            
            # 标签共现
            for i, tag1 in enumerate(tags):
                for tag2 in tags[i+1:]:
                    tag_cooccurrence[tag1][tag2] += 1
        
        # 最常用标签
        top_tags = tag_counts.most_common(self.config.max_topics)
        
        # 最常见的标签组合
        top_pairs = []
        for tag1, counter in tag_cooccurrence.items():
            for tag2, count in counter.most_common(3):
                if count >= 2:
                    top_pairs.append({
                        "tags": [tag1, tag2],
                        "count": count
                    })
        
        top_pairs.sort(key=lambda x: x['count'], reverse=True)
        top_pairs = top_pairs[:10]
        
        return {
            "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
            "tag_cooccurrence": [
                {"tags": [t1, t2], "count": c}
                for t1, counter in list(tag_cooccurrence.items())[:20]
                for t2, c in counter.most_common(3) if c >= 2
            ][:20]
        }
    
    def _analyze_content_patterns(self, memories: List[Dict]) -> Dict:
        """分析内容模式"""
        # 提取常用词汇
        all_text = ' '.join([
            memory.get('title', '') + ' ' + memory.get('content', '')
            for memory in memories
        ])
        
        # 简单分词（英文+中文）
        words = re.findall(r'\b[a-zA-Z]{4,}\b', all_text.lower())
        chinese = re.findall(r'[\u4e00-\u9fff]{2,}', all_text)
        
        word_freq = Counter(words + chinese)
        common_words = word_freq.most_common(30)
        
        # 分类分布
        category_counts = Counter(m.get('category', 'unknown') for m in memories)
        
        return {
            "common_words": [{"word": w, "count": c} for w, c in common_words],
            "category_distribution": dict(category_counts)
        }
    
    def update_knowledge_graph(self, memories: List[Dict] = None) -> Dict[str, Any]:
        """
        更新知识图谱
        提取实体和关系，构建图结构
        """
        if memories is None:
            data = self._load_data()
            memories = data.get('memories', [])
        
        # 节点和边
        nodes = {}  # id -> {label, type, weight}
        edges = []  # [{source, target, type, weight}]
        
        # 实体提取（简化版：从标签和分类提取）
        entity_map = {}  # 实体名 -> 节点ID
        
        for memory in memories:
            mem_id = memory.get('id', '')
            title = memory.get('title', '')
            category = memory.get('category', 'note')
            tags = memory.get('tags', [])
            
            # 创建记忆节点
            nodes[mem_id] = {
                "label": title[:50],
                "type": "memory",
                "category": category,
                "weight": 1.0
            }
            
            # 从标签创建实体节点
            for tag in tags:
                if tag not in entity_map:
                    entity_id = f"tag_{tag}"
                    entity_map[tag] = entity_id
                    nodes[entity_id] = {
                        "label": tag,
                        "type": "tag",
                        "weight": 0
                    }
                
                # 增加权重
                nodes[entity_map[tag]]["weight"] += 1
                
                # 创建边
                edges.append({
                    "source": mem_id,
                    "target": entity_map[tag],
                    "type": "has_tag",
                    "weight": 1.0
                })
        
        # 构建分类边
        category_entities = {}
        for memory in memories:
            mem_id = memory.get('id', '')
            category = memory.get('category', 'unknown')
            
            if category not in category_entities:
                cat_id = f"cat_{category}"
                category_entities[category] = cat_id
                nodes[cat_id] = {
                    "label": category,
                    "type": "category",
                    "weight": 0
                }
            
            nodes[category_entities[category]]["weight"] += 1
            
            edges.append({
                "source": mem_id,
                "target": category_entities[category],
                "type": "in_category",
                "weight": 0.5
            })
        
        # 归一化权重
        max_weight = max(n.get('weight', 1) for n in nodes.values()) or 1
        for node in nodes.values():
            node['normalized_weight'] = node.get('weight', 1) / max_weight
        
        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "memory_nodes": len([n for n in nodes.values() if n['type'] == 'memory']),
                "tag_nodes": len([n for n in nodes.values() if n['type'] == 'tag']),
                "category_nodes": len([n for n in nodes.values() if n['type'] == 'category'])
            }
        }
    
    def generate_insights(self, patterns: Dict = None, memories: List[Dict] = None) -> List[Dict]:
        """
        生成洞察
        基于模式和数据分析，生成有价值的洞察
        """
        if patterns is None:
            patterns = self.analyze_patterns(memories)
        if memories is None:
            data = self._load_data()
            memories = data.get('memories', [])
        
        insights = []
        
        # 1. 高频主题洞察
        tag_patterns = patterns.get('tag', {})
        top_tags = tag_patterns.get('top_tags', [])
        if top_tags and top_tags[0]['count'] >= self.config.min_pattern_frequency:
            insights.append({
                "type": "高频主题",
                "title": f"你最关注的主题是「{top_tags[0]['tag']}」",
                "description": f"你最近创建了 {top_tags[0]['count']} 条关于「{top_tags[0]['tag']}」的记忆，这是你最频繁关注的领域。",
                "confidence": min(top_tags[0]['count'] / 10, 1.0),
                "action": "考虑深入探索相关子主题"
            })
        
        # 2. 时间模式洞察
        temporal = patterns.get('temporal', {})
        peak_weekday = temporal.get('peak_weekday', '')
        if peak_weekday:
            insights.append({
                "type": "时间模式",
                "title": f"你最喜欢在{peak_weekday}思考",
                "description": f"你最高效的思考日是{peak_weekday}，这天创建的记忆最多。",
                "confidence": 0.7,
                "action": "可以在这一天安排深度思考任务"
            })
        
        # 3. 知识差距分析
        categories = patterns.get('content', {}).get('category_distribution', {})
        if 'goal' in categories and categories['goal'] < 3:
            insights.append({
                "type": "知识差距",
                "title": "你的目标记录较少",
                "description": "你很少记录目标，这可能影响长期规划。建议多记录你的目标和解题思路。",
                "confidence": 0.6,
                "action": "尝试记录更多目标类记忆"
            })
        
        # 4. 趋势洞察
        daily_dist = temporal.get('daily_distribution', {})
        if len(daily_dist) >= 7:
            recent = list(daily_dist.items())[-7:]
            recent_avg = sum(c for _, c in recent) / 7
            older = list(daily_dist.items())[-14:-7]
            older_avg = sum(c for _, c in older) / 7 if older else recent_avg
            
            if recent_avg > older_avg * 1.5:
                insights.append({
                    "type": "趋势",
                    "title": "你的思考频率正在上升",
                    "description": f"最近7天平均每天创建 {recent_avg:.1f} 条记忆，比之前增加了 {(recent_avg/older_avg-1)*100:.0f}%。",
                    "confidence": 0.8,
                    "action": "保持这个节奏，记录更多有价值的思考"
                })
            elif recent_avg < older_avg * 0.5:
                insights.append({
                    "type": "趋势",
                    "title": "你的思考频率有所下降",
                    "description": "最近你创建的记忆减少了，可能比较忙。建议保持记录习惯。",
                    "confidence": 0.7,
                    "action": "尝试每天至少记录一条想法"
                })
        
        # 5. 分类平衡
        cat_dist = categories
        if cat_dist:
            total = sum(cat_dist.values())
            note_ratio = cat_dist.get('note', 0) / total
            if note_ratio > 0.8:
                insights.append({
                    "type": "多样性",
                    "title": "记忆类型比较单一",
                    "description": "你主要是记录笔记（笔记占80%以上），可以尝试增加更多洞察、目标类记忆。",
                    "confidence": 0.6,
                    "action": "尝试创建更多insight和goal类记忆"
                })
        
        # 过滤低置信度洞察
        insights = [i for i in insights if i['confidence'] >= self.config.insight_confidence_threshold]
        
        return sorted(insights, key=lambda x: x['confidence'], reverse=True)
    
    def analyze_importance(self, memories: List[Dict] = None) -> List[Dict]:
        """
        分析记忆重要性
        基于多个维度给记忆打分
        """
        if memories is None:
            data = self._load_data()
            memories = data.get('memories', [])
        
        scored = []
        
        for memory in memories:
            score = 0.0
            reasons = []
            
            # 1. 交互频率
            interactions = memory.get('interactions', 0)
            if interactions > 10:
                score += 0.3
                reasons.append(f"高交互({interactions}次)")
            elif interactions > 5:
                score += 0.15
                reasons.append(f"中等交互({interactions}次)")
            elif interactions > 0:
                score += 0.05
                reasons.append(f"少量交互({interactions}次)")
            
            # 2. 引用次数
            refs = len(memory.get('references', []))
            if refs > 3:
                score += 0.25
                reasons.append(f"被{refs}个记忆引用")
            elif refs > 0:
                score += 0.1
                reasons.append(f"被{refs}个记忆引用")
            
            # 3. 用户标记
            if memory.get('pinned', False):
                score += 0.2
                reasons.append("已固定")
            
            if memory.get('important', False):
                score += 0.2
                reasons.append("用户标记重要")
            
            # 4. 内容长度（太长或太短都可能是重要的）
            content_len = len(memory.get('content', ''))
            if 500 < content_len < 5000:
                score += 0.1
                reasons.append("内容详实")
            
            # 5. 时间价值（最近的更有相关性）
            try:
                created = datetime.fromisoformat(memory.get('created_at', '').replace('Z', '+00:00'))
                age_days = (datetime.now() - created.replace(tzinfo=None)).days
                if age_days < 30:
                    score += 0.15
                    reasons.append("近期创建")
            except:
                pass
            
            scored.append({
                "id": memory.get('id'),
                "title": memory.get('title', '')[:50],
                "importance_score": min(score, 1.0),
                "reasons": reasons
            })
        
        return sorted(scored, key=lambda x: x['importance_score'], reverse=True)
    
    def analyze_completeness(self, memories: List[Dict] = None) -> Dict:
        """
        分析知识完整性
        评估各个维度的覆盖程度
        """
        if memories is None:
            data = self._load_data()
            memories = data.get('memories', [])
        
        # 1. 分类覆盖
        categories = set(m.get('category', 'unknown') for m in memories)
        all_categories = {'insight', 'goal', 'note', 'relationship', 'log', 'project', 'question'}
        category_coverage = len(categories) / len(all_categories)
        
        # 2. 时间线完整性
        dates = []
        for m in memories:
            try:
                created = m.get('created_at', '')
                if created:
                    dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    dates.append(dt.replace(tzinfo=None))
            except:
                continue
        
        timeline_span = 0
        if len(dates) >= 2:
            dates.sort()
            timeline_span = (dates[-1] - dates[0]).days
        
        # 3. 主题深度
        all_tags = []
        for m in memories:
            tags = m.get('tags', [])
            if isinstance(tags, list):
                all_tags.extend(tags)
        
        unique_tags = len(set(all_tags))
        tag_diversity = unique_tags / max(len(all_tags), 1)
        
        # 4. 关系密度
        total_refs = sum(len(m.get('references', [])) for m in memories)
        relationship_density = total_refs / max(len(memories), 1)
        
        return {
            "category_coverage": round(category_coverage, 2),
            "missing_categories": list(all_categories - categories),
            "timeline_span_days": timeline_span,
            "unique_tags": unique_tags,
            "tag_diversity": round(tag_diversity, 2),
            "relationship_density": round(relationship_density, 2),
            "total_memories": len(memories),
            "overall_score": round(
                (category_coverage * 0.3 + tag_diversity * 0.3 + min(timeline_span/365, 1) * 0.2 + relationship_density * 0.2),
                2
            )
        }
    
    def run_full_analysis(self) -> Dict[str, Any]:
        """
        运行完整分析
        返回所有分析结果
        """
        data = self._load_data()
        memories = data.get('memories', [])
        
        # 过滤活跃记忆
        active_memories = [m for m in memories if m.get('status') != 'forgotten']
        
        # 执行各项分析
        patterns = self.analyze_patterns(active_memories)
        knowledge_graph = self.update_knowledge_graph(active_memories)
        insights = generate_insights(patterns, active_memories)
        importance_ranking = self.analyze_importance(active_memories)
        completeness = self.analyze_completeness(active_memories)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_memories": len(memories),
                "active_memories": len(active_memories)
            },
            "patterns": patterns,
            "knowledge_graph": {
                "stats": knowledge_graph["stats"]
            },
            "insights": insights,
            "importance_ranking": importance_ranking[:20],
            "completeness": completeness
        }


# 修复：定义在类外部的函数
def generate_insights(patterns: Dict, memories: List[Dict]) -> List[Dict]:
    """生成洞察（独立函数版本）"""
    config = AnalysisConfig()
    insights = []
    
    # 1. 高频主题洞察
    tag_patterns = patterns.get('tag', {})
    top_tags = tag_patterns.get('top_tags', [])
    if top_tags and top_tags[0]['count'] >= config.min_pattern_frequency:
        insights.append({
            "type": "高频主题",
            "title": f"你最关注的主题是「{top_tags[0]['tag']}」",
            "description": f"你最近创建了 {top_tags[0]['count']} 条关于「{top_tags[0]['tag']}」的记忆，这是你最频繁关注的领域。",
            "confidence": min(top_tags[0]['count'] / 10, 1.0),
            "action": "考虑深入探索相关子主题"
        })
    
    # 2. 时间模式洞察
    temporal = patterns.get('temporal', {})
    peak_weekday = temporal.get('peak_weekday', '')
    if peak_weekday:
        insights.append({
            "type": "时间模式",
            "title": f"你最喜欢在{peak_weekday}思考",
            "description": f"你最高效的思考日是{peak_weekday}，这天创建的记忆最多。",
            "confidence": 0.7,
            "action": "可以在这一天安排深度思考任务"
        })
    
    # 3. 趋势洞察
    daily_dist = temporal.get('daily_distribution', {})
    if len(daily_dist) >= 7:
        recent = list(daily_dist.items())[-7:]
        recent_avg = sum(c for _, c in recent) / 7
        older = list(daily_dist.items())[-14:-7]
        older_avg = sum(c for _, c in older) / 7 if older else recent_avg
        
        if recent_avg > older_avg * 1.5:
            insights.append({
                "type": "趋势",
                "title": "你的思考频率正在上升",
                "description": f"最近7天平均每天创建 {recent_avg:.1f} 条记忆，比之前增加了 {(recent_avg/older_avg-1)*100:.0f}%。",
                "confidence": 0.8,
                "action": "保持这个节奏，记录更多有价值的思考"
            })
        elif older_avg > 0 and recent_avg < older_avg * 0.5:
            insights.append({
                "type": "趋势",
                "title": "你的思考频率有所下降",
                "description": "最近你创建的记忆减少了，可能比较忙。建议保持记录习惯。",
                "confidence": 0.7,
                "action": "尝试每天至少记录一条想法"
            })
    
    # 过滤低置信度洞察
    insights = [i for i in insights if i['confidence'] >= config.insight_confidence_threshold]
    
    return sorted(insights, key=lambda x: x['confidence'], reverse=True)


if __name__ == "__main__":
    # 测试
    engine = AnalyzerEngine()
    result = engine.run_full_analysis()
    print(json.dumps(result, ensure_ascii=False, indent=2))
