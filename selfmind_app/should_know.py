"""认知盲区检测 — 信号B推理 + 差距匹配引擎

核心逻辑：
  信号A = SelfMind库中已有的条目（知识图谱节点）
  信号B = 基于角色/项目/战略推理出的"应该知道"的主题
  差距  = 信号B - 信号A（红=不存在，黄=衰退中）

不新建数据采集器，所有信号B数据从现有SelfMind数据管道推理得出。
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 信号B: 你应该知道的主题定义
# ──────────────────────────────────────────────
# 每个主题从现有SelfMind数据(记忆/wiki/项目)推理而来，
# 不依赖外部采集器。keywords用于在entries表中做内容匹配。

SHOULD_KNOW_TOPICS = [
    # ── 战略/项目类 ──
    {
        "id": "finna-platform",
        "label": "Finna全行级平台",
        "domain": "project",
        "priority": 5,
        "keywords": ["Finna", "全行级", "智能体平台", "AIA"],
        "reason": "年度核心战略，全行级Agent平台5000+ agent目标"
    },
    {
        "id": "meet-miaojie",
        "label": "Meet妙记C端",
        "domain": "project",
        "priority": 5,
        "keywords": ["Meet", "妙记", "妙计", "C端", "陈兴隆"],
        "reason": "2026聚焦方向之一，用户量+有效会议>1w"
    },
    {
        "id": "enterprise-graph",
        "label": "企业图谱B端",
        "domain": "project",
        "priority": 5,
        "keywords": ["企业图谱", "陪练签约", "B端", "尹晨轩"],
        "reason": "2026聚焦方向之一，陪练签约+图谱用户商机"
    },
    {
        "id": "selfmind",
        "label": "SelfMind智能体记忆系统",
        "domain": "project",
        "priority": 5,
        "keywords": ["SelfMind", "记忆", "智能体记忆", "衰减", "元记忆"],
        "reason": "核心产品，理论+研发+推广持续迭代"
    },
    {
        "id": "ai-five-year-plan",
        "label": "AI五年发展规划",
        "domain": "project",
        "priority": 4,
        "keywords": ["五年规划", "AI规划", "三位一体"],
        "reason": "员工筑底+中枢强基+场景增效，需跟进执行"
    },
    {
        "id": "marketization-kpi",
        "label": "2026市场化KPI",
        "domain": "project",
        "priority": 4,
        "keywords": ["市场化", "KPI", "900万", "PCBL"],
        "reason": "900万目标，PCBL四腿战略推进"
    },
    {
        "id": "agi-pathfinder",
        "label": "AGI探路者党建品牌",
        "domain": "project",
        "priority": 3,
        "keywords": ["AGI探路者", "党建", "党支部"],
        "reason": "AI特色党支部品牌，方案规划阶段"
    },
    {
        "id": "ai-rank-assessment",
        "label": "AI职级考核体系",
        "domain": "project",
        "priority": 4,
        "keywords": ["职级", "考核", "AI能力", "L0", "L1", "L2"],
        "reason": "全员AI能力基本门槛，需落地推进"
    },

    # ── 团队管理类 ──
    {
        "id": "team-org",
        "label": "AI部门组织架构和团队分工",
        "domain": "management",
        "priority": 4,
        "keywords": ["组织架构", "团队", "部门", "实验室", "平台", "产品", "场景"],
        "reason": "5团队×4重点工作，营收结构+能力流传导"
    },
    {
        "id": "management-june",
        "label": "6月管理关注事项",
        "domain": "management",
        "priority": 5,
        "keywords": ["6月管理", "非首钢办公", "反洗钱", "招聘", "问题员工"],
        "reason": "6条关键管理事项，需每周追踪进度"
    },
    {
        "id": "anti-money-laundering",
        "label": "反洗钱项目",
        "domain": "management",
        "priority": 4,
        "keywords": ["反洗钱", "王庚午", "尹辰轩"],
        "reason": "管理关注事项之一，需跟进王庚午/尹辰轩"
    },
    {
        "id": "recruitment",
        "label": "人员招聘和问题员工",
        "domain": "management",
        "priority": 3,
        "keywords": ["招聘", "问题员工", "人员"],
        "reason": "团队建设持续性事项"
    },

    # ── 认知/身份类 ──
    {
        "id": "identity-db-ai",
        "label": "数据库人带AI部门 — 身份认同重建",
        "domain": "identity",
        "priority": 4,
        "keywords": ["身份认同", "identity lag", "数据库人", "DB+AI"],
        "reason": "核心矛盾：自认数据库人但实际是AI负责人，需要成果叙事"
    },
    {
        "id": "career-review",
        "label": "职业生涯复盘和自我叙事",
        "domain": "identity",
        "priority": 4,
        "keywords": ["职业复盘", "tange-career-review", "自我叙事", "成果叙事"],
        "reason": "从「我要做什么」转向「我做了什么」"
    },

    # ── 行业/认知类 ──
    {
        "id": "ai-agent-trends",
        "label": "AI Agent行业动态",
        "domain": "knowledge",
        "priority": 4,
        "keywords": ["AI Agent", "智能体", "Agent形态", "多智能体"],
        "reason": "作为AI部门负责人，需持续跟踪Agent技术发展方向"
    },
    {
        "id": "ai-employee-management",
        "label": "AI员工管理研究",
        "domain": "knowledge",
        "priority": 3,
        "keywords": ["AI员工", "企业AI管理", "靠谱", "信任", "授权飞轮"],
        "reason": "坦哥计划系统研究的方向，可能产出框架性文章"
    },

    # ── Nous团队 ──
    {
        "id": "nous-team-status",
        "label": "Nous团队协作状态",
        "domain": "nous",
        "priority": 4,
        "keywords": ["Nous", "小亚", "柏拉图", "苏格拉底", "多智能体协作"],
        "reason": "三成员协作链运转情况，需常态化关注"
    },
]

# 阈值定义
DECAY_THRESHOLD_YELLOW = 0.30  # 衰减分数低于此值 → 黄标（需刷新）
RECALL_STALE_DAYS = 30         # 超过此天数未被回忆 → 黄标


class ShouldKnowEngine:
    """认知盲区检测引擎"""

    def __init__(self, store):
        self.store = store

    def _keyword_search(self, keywords: List[str]) -> List[dict]:
        """在条目表中匹配关键词，返回匹配的活跃条目"""
        if not self.store or not keywords:
            return []

        all_active = self.store.get_all_entries(status="active")
        if not all_active:
            return []

        matches = []
        for entry in all_active:
            content = (entry.get("content", "") or "") + " " + \
                      (entry.get("content_preview", "") or "") + " " + \
                      (entry.get("label", "") or "")
            content_lower = content.lower()

            # 至少匹配一个关键词
            for kw in keywords:
                if kw.lower() in content_lower:
                    matches.append(entry)
                    break

        return matches

    def _get_last_recall_days(self, entry_id: str) -> Optional[int]:
        """获取条目距离最近一次被回忆的天数"""
        try:
            row = self.store.conn.execute(
                "SELECT MAX(timestamp) as last_recall FROM agent_recall_log WHERE entry_id=?",
                (entry_id,)
            ).fetchone()
            if row and row["last_recall"]:
                last = datetime.fromisoformat(row["last_recall"])
                return (datetime.now() - last).days
        except Exception:
            pass
        # 降级：使用 entry 自身的 last_recalled 字段
        try:
            entry = self.store.get_entry(entry_id)
            if entry and entry.get("last_recalled"):
                last = datetime.fromisoformat(entry["last_recalled"])
                return (datetime.now() - last).days
        except Exception:
            pass
        return None

    def analyze_gaps(self) -> Dict:
        """运行全量认知差距分析，返回排序后的差距列表"""
        gaps = []
        greens = 0

        for topic in SHOULD_KNOW_TOPICS:
            matches = self._keyword_search(topic["keywords"])
            topic_gap = {
                "id": topic["id"],
                "label": topic["label"],
                "domain": topic["domain"],
                "priority": topic["priority"],
                "reason": topic["reason"],
            }

            if not matches:
                # 红标：不存在 — 盲区
                topic_gap["status"] = "red"
                topic_gap["detail"] = "SelfMind中无相关内容，建议补充"
                gaps.append(topic_gap)
                continue

            # 取 decay_score 最差的匹配条目
            best_entry = max(matches, key=lambda e: e.get("decay_score", 0))
            min_decay = best_entry.get("decay_score", 0.5)
            last_recall_days = self._get_last_recall_days(best_entry["id"])

            stale = last_recall_days is not None and last_recall_days > RECALL_STALE_DAYS

            if min_decay < DECAY_THRESHOLD_YELLOW:
                topic_gap["status"] = "yellow"
                topic_gap["detail"] = f"已有相关内容但衰减严重(decay={min_decay:.2f})，建议刷新"
                topic_gap["decay_score"] = round(min_decay, 3)
                topic_gap["last_recall_days"] = last_recall_days
                topic_gap["entry_preview"] = best_entry.get("content_preview", "")[:80]
                gaps.append(topic_gap)
            elif stale:
                topic_gap["status"] = "yellow"
                topic_gap["detail"] = f"已有内容但{last_recall_days}天未被回忆，建议重新引用"
                topic_gap["decay_score"] = round(min_decay, 3)
                topic_gap["last_recall_days"] = last_recall_days
                topic_gap["entry_preview"] = best_entry.get("content_preview", "")[:80]
                gaps.append(topic_gap)
            else:
                greens += 1

        # 排序：红优先于黄，同色按优先级降序
        gaps.sort(key=lambda g: (
            0 if g["status"] == "red" else 1,
            -g["priority"]
        ))

        return {
            "timestamp": datetime.now().isoformat(),
            "total_topics": len(SHOULD_KNOW_TOPICS),
            "green_count": greens,
            "red_count": sum(1 for g in gaps if g["status"] == "red"),
            "yellow_count": sum(1 for g in gaps if g["status"] == "yellow"),
            "gaps": gaps,
            "top3": gaps[:3],  # 每天不超过3条
            "summary": self._generate_summary(gaps, greens)
        }

    def _generate_summary(self, gaps: List[Dict], greens: int) -> str:
        """生成本日认知差距摘要（不超过3条）"""
        top3 = gaps[:3]
        if not top3:
            return f"✅ 全部{greens}个认知领域状态健康，无盲区无衰退。"

        lines = [f"今日认知差距提醒（{len(top3)}条）："]
        for g in top3:
            icon = "🔴" if g["status"] == "red" else "🟡"
            lines.append(f"  {icon} [{g['domain']}] {g['label']}")
            lines.append(f"     {g['detail']}")
        lines.append(f"  ✅ 其他{greens}个领域正常")
        return "\n".join(lines)