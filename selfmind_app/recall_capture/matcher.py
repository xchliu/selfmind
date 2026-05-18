"""三层匹配策略 — 将RecallEvent与SelfMind entries匹配"""
import hashlib
import re
from datetime import datetime


class RecallMatcher:
    """将agent的RecallEvent与SelfMind的entries进行匹配
    
    三层递进策略：
    1. content_hash精确匹配 — 最快最准
    2. 关键词模糊匹配 — substring匹配
    3. 语义向量匹配 — 未来扩展（embedding相似度）
    """

    def __init__(self, entries_by_hash: dict, entries_by_id: dict):
        """
        entries_by_hash: {content_hash: entry_dict} 
        entries_by_id: {entry_id: entry_dict}
        """
        self.entries_by_hash = entries_by_hash
        self.entries_by_id = entries_by_id
        
        # 为模糊匹配构建关键词索引
        self.keyword_index = {}  # {keyword_lower: [entry_ids]}
        self._build_keyword_index()

    def _build_keyword_index(self):
        """从entries的content_preview中提取关键词，建立倒排索引"""
        for entry_id, entry in self.entries_by_id.items():
            preview = entry.get('content_preview', '') or entry.get('content', '')
            if not preview:
                continue
            
            # 从preview中提取关键词
            keywords = self._extract_keywords(preview)
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower not in self.keyword_index:
                    self.keyword_index[kw_lower] = []
                self.keyword_index[kw_lower].append(entry_id)

    def _extract_keywords(self, text: str) -> list[str]:
        """从文本中提取有意义的关键词
        
        策略：提取3-30字符的词组，排除纯数字/符号
        """
        # 先从YAML格式提取description（如果有）
        keywords = []
        
        # 提取YAML description字段
        desc_match = re.search(r'description:\s*(.+)', text)
        if desc_match:
            desc = desc_match.group(1).strip()
            # 去掉引号
            desc = desc.strip('"').strip("'")
            if len(desc) > 5:
                keywords.append(desc)
        
        # 提取英文名（skill类记忆常有name字段）
        name_match = re.search(r'name:\s*(\S+)', text)
        if name_match:
            name = name_match.group(1).strip()
            if len(name) > 2:
                keywords.append(name)
        
        # 提取中文关键词（2-6字的词组）
        chinese_words = re.findall(r'[\u4e00-\u9fff]{2,6}', text)
        for w in chinese_words:
            if w not in keywords:
                keywords.append(w)
        
        # 提取英文关键词（3+字符的词）
        english_words = re.findall(r'[a-zA-Z][a-zA-Z0-9_-]{2,}', text)
        for w in english_words:
            w_lower = w.lower()
            # 排除常见无意义词
            if w_lower in ('the', 'and', 'for', 'with', 'this', 'that', 'from', 'not', 'but', 'has', 'can', 'will', 'are', 'was', 'all', 'use', 'also', 'into', 'just', 'more', 'than', 'only'):
                continue
            if w not in keywords:
                keywords.append(w)
        
        return keywords

    def match(self, recall_event) -> list[dict]:
        """将一个RecallEvent匹配到SelfMind entries
        
        Returns: [{"entry_id": ..., "confidence": ..., "method": "hash|keyword|substring}]
        """
        results = []
        snippet = recall_event.context_snippet
        
        if not snippet:
            return results
        
        # Layer 1: content_hash精确匹配（不太可能，但快速检查）
        hash_match = self._match_by_hash(recall_event)
        if hash_match:
            results.append(hash_match)
            return results
        
        # Layer 2: substring匹配 — snippet的关键片段是否出现在entry内容中
        substring_matches = self._match_by_substring(recall_event)
        if substring_matches:
            results.extend(substring_matches)
            return results
        
        # Layer 3: 关键词倒排匹配（补充）
        keyword_matches = self._match_by_keywords(recall_event)
        results.extend(keyword_matches)
        
        # Layer 4: 语义向量匹配 — TODO 未来用embedding
        
        return results

    def _match_by_substring(self, recall_event) -> list[dict]:
        """Substring匹配 — 从snippet中提取有意义的关键短语，在entry content中搜索
        
        策略：
        1. 从snippet提取3-5个最有区分度的短语（中文词组、英文术语、特殊标识符）
        2. 在所有entries的content_preview中搜索这些短语
        3. 匹配2+个短语的entry认为是被唤起了
        """
        results = []
        snippet = recall_event.context_snippet
        
        if not snippet or len(snippet) < 10:
            return results
        
        # 提取关键短语
        key_phrases = self._extract_key_phrases(snippet)
        
        if not key_phrases:
            return results
        
        # 在entries中搜索每个短语
        matched_entries = {}  # {entry_id: [matched_phrases]}
        for phrase in key_phrases:
            phrase_lower = phrase.lower()
            for entry_id, entry in self.entries_by_id.items():
                content = (entry.get('content_preview', '') or '') + ' ' + (entry.get('content', '') or '')
                content_lower = content.lower()
                
                if phrase_lower in content_lower and len(phrase_lower) >= 3:
                    if entry_id not in matched_entries:
                        matched_entries[entry_id] = []
                    matched_entries[entry_id].append(phrase)
        
        # 计算confidence：匹配短语数 / 总短语数
        total_phrases = len(key_phrases)
        for entry_id, matched_phrases in matched_entries.items():
            match_ratio = len(matched_phrases) / max(1, total_phrases)
            # 需要至少匹配2个短语 或 match_ratio >= 0.4
            if len(matched_phrases) >= 2 or match_ratio >= 0.4:
                confidence = min(0.85, match_ratio * 0.8)
                results.append({
                    'entry_id': entry_id,
                    'confidence': confidence,
                    'method': 'substring',
                })
        
        # 按confidence排序，最多返回5个
        results.sort(key=lambda x: x['confidence'], reverse=True)
        return results[:5]

    def _extract_key_phrases(self, text: str) -> list[str]:
        """从文本中提取最有区分度的关键短语
        
        策略：提取中文词组(2-6字)、英文术语(3+字)、特殊标识符(UUID/路径/类名)
        排除通用词
        """
        phrases = []
        
        # 特殊标识符：UUID、路径、类名、方法名
        special_patterns = [
            r'[a-f0-9]{8}-[a-f0-9]{4}',  # UUID prefix
            r'/[a-z_]+/[a-z_]+',           # paths
            r'[A-Z][a-zA-Z]+[A-Z][a-zA-Z]*',  # CamelCase
            r'[a-z_]+\.[a-z_]+',           # dot-separated names
        ]
        for pattern in special_patterns:
            found = re.findall(pattern, text)
            phrases.extend(found)
        
        # 中文关键词（2-6字词组）
        chinese = re.findall(r'[\u4e00-\u9fff]{2,6}', text)
        # 排除通用词
        generic_chinese = {'这个', '那个', '什么', '怎么', '可以', '需要', '已经', '还是', '不是', '就是', '但是', '而且', '因为', '所以', '如果', '虽然', '然后', '另外', '其他', '一些', '一种', '每个', '所有', '很多', '非常', '比较', '仍然', '只是', '还是'}
        for c in chinese:
            if c not in generic_chinese and c not in phrases:
                phrases.append(c)
        
        # 英文关键词（3+字母）
        english = re.findall(r'[a-zA-Z][a-zA-Z0-9_-]{2,}', text)
        generic_english = {'the', 'and', 'for', 'with', 'this', 'that', 'from', 'not', 'but', 'has', 'can', 'will', 'are', 'was', 'all', 'use', 'also', 'into', 'just', 'more', 'than', 'only', 'you', 'they', 'we', 'our', 'your', 'their', 'its', 'his', 'her', 'him', 'she', 'let', 'did', 'does', 'done', 'been', 'being', 'have', 'had', 'were', 'would', 'could', 'should', 'must', 'shall', 'may', 'might', 'need', 'want', 'make', 'made', 'get', 'got', 'give', 'given', 'take', 'took', 'know', 'knew', 'think', 'thought', 'say', 'said', 'see', 'look', 'find', 'found', 'tell', 'told', 'ask', 'come', 'go', 'know', 'way', 'one', 'two', 'new', 'now', 'old', 'see', 'way', 'who', 'did', 'get', 'let', 'say', 'too', 'use'}
        for e in english:
            if e.lower() not in generic_english and e not in phrases:
                phrases.append(e)
        
        return phrases

    def _match_by_hash(self, recall_event) -> dict | None:
        """content_hash精确匹配"""
        # RecallEvent里的entry_content_hash是从session snippet的md5前16位
        # 需要跟SelfMind entries的content_hash比对
        h = recall_event.entry_content_hash
        
        if h in self.entries_by_hash:
            entry = self.entries_by_hash[h]
            return {
                'entry_id': entry['id'],
                'confidence': 1.0,
                'method': 'content_hash',
            }
        
        # 也尝试用snippet内容重新计算hash看能否匹配完整content
        snippet = recall_event.context_snippet
        if snippet:
            # 尝试不同长度的snippet做hash
            full_hash = hashlib.md5(snippet.encode('utf-8')).hexdigest()
            if full_hash in self.entries_by_hash:
                entry = self.entries_by_hash[full_hash]
                return {
                    'entry_id': entry['id'],
                    'confidence': 0.95,
                    'method': 'content_hash_full',
                }
        
        return None

    def _match_by_keywords(self, recall_event) -> list[dict]:
        """关键词模糊匹配 — snippet中的关键词跟entry关键词倒排索引匹配"""
        results = []
        snippet = recall_event.context_snippet
        
        if not snippet:
            return results
        
        # 从snippet提取关键词
        snippet_keywords = self._extract_keywords(snippet)
        
        # 在倒排索引中查找匹配的entries
        matched_entries = {}  # {entry_id: match_count}
        for kw in snippet_keywords:
            kw_lower = kw.lower()
            if kw_lower in self.keyword_index:
                for entry_id in self.keyword_index[kw_lower]:
                    matched_entries[entry_id] = matched_entries.get(entry_id, 0) + 1
        
        # 按匹配关键词数量排序，取top 5
        if not matched_entries:
            return results
        
        sorted_matches = sorted(matched_entries.items(), key=lambda x: x[1], reverse=True)[:5]
        
        total_snippet_kw = len(snippet_keywords)
        for entry_id, match_count in sorted_matches:
            # confidence = 匹配关键词数 / snippet关键词数 * 基础系数
            confidence = min(0.8, (match_count / max(1, total_snippet_kw)) * 0.6)
            
            # 至少需要匹配2个关键词或有单个关键词完全匹配
            if match_count >= 2 or (match_count == 1 and confidence >= 0.3):
                results.append({
                    'entry_id': entry_id,
                    'confidence': confidence,
                    'method': 'keyword',
                })
        
        return results

    def match_all(self, recall_events: list) -> list[dict]:
        """批量匹配多个RecallEvent，去重合并，保留每个match的原始event信息"""
        all_matches = []
        # {entry_id: {match_info + event_timestamp + agent_id}}
        seen_entry_ids = {}
        
        for event in recall_events:
            matches = self.match(event)
            for m in matches:
                eid = m['entry_id']
                m['recall_timestamp'] = event.timestamp
                m['agent_id'] = event.agent_id
                if eid not in seen_entry_ids or m['confidence'] > seen_entry_ids[eid]['confidence']:
                    seen_entry_ids[eid] = m
        
        for eid, m in seen_entry_ids.items():
            all_matches.append(m)
        
        return all_matches