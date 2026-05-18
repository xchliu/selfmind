"""AgentAdapter抽象基类 — 未来可对接不同智能体"""
import abc
import json
import os
import hashlib
from pathlib import Path
from datetime import datetime, timezone


class RecallEvent:
    """一次记忆唤起事件"""
    __slots__ = ['entry_content_hash', 'agent_id', 'timestamp', 'source', 'confidence', 'context_snippet']

    def __init__(self, entry_content_hash, agent_id, timestamp, source='session_log',
                 confidence=1.0, context_snippet=''):
        self.entry_content_hash = entry_content_hash
        self.agent_id = agent_id
        self.timestamp = timestamp
        self.source = source
        self.confidence = confidence
        self.context_snippet = context_snippet[:200]  # 截断避免过长

    def to_dict(self):
        return {
            'entry_content_hash': self.entry_content_hash,
            'agent_id': self.agent_id,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'source': self.source,
            'confidence': self.confidence,
            'context_snippet': self.context_snippet,
        }


class AgentAdapter(abc.ABC):
    """智能体适配器抽象基类 — 所有agent adapter继承此类"""

    @abc.abstractmethod
    def scan_recent_activity(self, since_timestamp: datetime) -> list[RecallEvent]:
        """扫描since_timestamp之后的agent活动，返回唤起事件列表"""
        pass

    @abc.abstractmethod
    def get_agent_id(self) -> str:
        """返回此adapter对应的agent标识"""
        pass


class HermesAdapter(AgentAdapter):
    """Hermes Agent适配器 — 扫描session jsonl日志"""

    def __init__(self, sessions_dir: str = None):
        self.sessions_dir = sessions_dir or os.path.expanduser('~/.hermes/sessions')
        self.agent_id = 'hermes'

    def get_agent_id(self) -> str:
        return self.agent_id

    def scan_recent_activity(self, since_timestamp: datetime) -> list[RecallEvent]:
        events = []
        sessions_path = Path(self.sessions_dir)

        if not sessions_path.exists():
            return events

        # 找到since_timestamp之后修改过的session文件
        for session_file in sessions_path.glob('*.jsonl'):
            if session_file.stat().st_mtime < since_timestamp.timestamp():
                continue

            try:
                events.extend(self._parse_session(session_file, since_timestamp))
            except Exception as e:
                # 单个session解析失败不影响整体扫描
                print(f"[RecallCapture] Error parsing {session_file.name}: {e}")
                continue

        return events

    def _parse_session(self, session_file: Path, since_timestamp: datetime) -> list[RecallEvent]:
        """解析单个session文件，提取assistant turn中的内容"""
        events = []
        content_hashes_seen = set()  # 同一session内去重

        with open(session_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # 只处理assistant turn（agent的推理输出包含引用的知识）
                if entry.get('role') != 'assistant':
                    continue

                # 检查timestamp是否在since之后
                ts = entry.get('timestamp')
                if not ts:
                    continue

                try:
                    entry_time = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    if entry_time.tzinfo:
                        entry_time = entry_time.astimezone(timezone.utc).replace(tzinfo=None)
                except (ValueError, AttributeError):
                    continue

                if entry_time < since_timestamp:
                    continue

                # 提取content文本
                content = entry.get('content', '')
                if not content or not isinstance(content, str):
                    continue

                # content可能是多段文本（有些session格式是list of dicts）
                if isinstance(content, list):
                    text_parts = []
                    for part in content:
                        if isinstance(part, dict) and part.get('type') == 'text':
                            text_parts.append(part.get('text', ''))
                        elif isinstance(part, str):
                            text_parts.append(part)
                    content = '\n'.join(text_parts)

                if not content:
                    continue

                # 从content中提取可能的记忆引用片段
                snippets = self._extract_snippets(content)

                for snippet in snippets:
                    h = hashlib.md5(snippet.encode('utf-8')).hexdigest()[:16]
                    if h in content_hashes_seen:
                        continue
                    content_hashes_seen.add(h)

                    events.append(RecallEvent(
                        entry_content_hash=h,
                        agent_id=self.agent_id,
                        timestamp=entry_time,
                        source='session_log',
                        confidence=0.7,  # session日志匹配confidence稍低
                        context_snippet=snippet,
                    ))

        return events

    def _extract_snippets(self, content: str) -> list[str]:
        """从assistant content中提取可能是记忆引用的片段
        
        策略：将连续有意义段落合并成snippet块（而不是逐行），每块200-500字
        """
        # 按换行分割
        lines = content.split('\n')
        
        # 过滤无意义行，保留有意义行
        meaningful_lines = []
        for line in lines:
            line = line.strip()
            if len(line) < 10:          # 太短
                continue
            if line.startswith('{') and line.endswith('}'):  # JSON
                continue
            if line.startswith('```') or line.startswith('#!/'):  # 代码
                continue
            if line.startswith('***') or line.startswith('---') and len(line) < 20:  # 分隔符
                continue
            meaningful_lines.append(line)
        
        if not meaningful_lines:
            return []
        
        # 合并连续行成snippet块——每块最多500字
        snippets = []
        current_block = ''
        for line in meaningful_lines:
            if len(current_block) + len(line) > 500 and current_block:
                snippets.append(current_block.strip())
                current_block = line
            else:
                current_block += '\n' + line if current_block else line
        
        if current_block.strip():
            snippets.append(current_block.strip())
        
        # 如果snippet太少（说明内容很短），直接用整段content的前500字
        if len(snippets) == 0 and len(content) > 50:
            snippets.append(content[:500])
        
        return snippets