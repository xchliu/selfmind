"""RecallScanner — 主扫描引擎，协调adapter扫描 + matcher匹配 + store记录"""
import os
import time
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from loguru import logger

from .adapter import HermesAdapter, AgentAdapter, RecallEvent
from .matcher import RecallMatcher


class RecallScanner:
    """记忆唤起扫描引擎
    
    流程：adapter扫描agent活动 → matcher匹配SelfMind entries → store记录recall
    """

    def __init__(self, store, adapters: list[AgentAdapter] = None, scan_interval_minutes: int = 5):
        self.store = store
        self.adapters = adapters or [HermesAdapter()]
        self.scan_interval = timedelta(minutes=scan_interval_minutes)
        self.last_scan_time = None
        self._load_last_scan_time()

    def _load_last_scan_time(self):
        """从文件读取上次扫描时间"""
        scan_file = Path(self.store.db_path).parent / 'recall_scan_state.json'
        try:
            if scan_file.exists():
                with open(scan_file, 'r') as f:
                    state = json.load(f)
                self.last_scan_time = datetime.fromisoformat(state['last_scan_time'])
            else:
                # 第一次扫描，取最近30天（覆盖所有历史session数据）
                self.last_scan_time = datetime.now(timezone.utc).astimezone().replace(tzinfo=None) - timedelta(days=30)
        except Exception:
            self.last_scan_time = datetime.now(timezone.utc).astimezone().replace(tzinfo=None) - timedelta(days=30)

    def _save_last_scan_time(self):
        """保存扫描时间到文件"""
        now = datetime.now(timezone.utc).astimezone().replace(tzinfo=None)
        scan_file = Path(self.store.db_path).parent / 'recall_scan_state.json'
        try:
            with open(scan_file, 'w') as f:
                json.dump({'last_scan_time': now.isoformat()}, f)
        except Exception as e:
            logger.warning(f"Failed to save recall_scan_state: {e}")
        self.last_scan_time = now

    def scan(self) -> dict:
        """执行一次完整扫描
        
        Returns: {
            'events_found': int,
            'entries_matched': int,
            'recalls_recorded': int,
            'adapters_scanned': int,
            'scan_duration_ms': int,
        }
        """
        start_time = time.time()
        since = self.last_scan_time or datetime.now() - timedelta(hours=1)
        since = since.replace(tzinfo=None)

        logger.info(f"[RecallScanner] Starting scan since {since}")

        # Step 1: 各adapter扫描agent活动
        all_events = []
        for adapter in self.adapters:
            try:
                events = adapter.scan_recent_activity(since)
                logger.info(f"[RecallScanner] {adapter.get_agent_id()}: found {len(events)} events")
                all_events.extend(events)
            except Exception as e:
                logger.error(f"[RecallScanner] Adapter {adapter.get_agent_id()} error: {e}")

        # Step 2: 加载SelfMind entries构建matcher
        entries_by_hash, entries_by_id = self._load_entries()
        matcher = RecallMatcher(entries_by_hash, entries_by_id)

        # Step 3: 匹配events到entries
        matches = matcher.match_all(all_events)
        logger.info(f"[RecallScanner] Matched {len(matches)} entries from {len(all_events)} events")

        # Step 4: 记录recall到store
        recalls_recorded = self._record_recalls(all_events, matches)

        # Step 5: 更新衰减分数（recall会影响recency）
        self.store.compute_decay_scores()

        # Step 6: 保存扫描时间
        self._save_last_scan_time()

        duration_ms = int((time.time() - start_time) * 1000)
        result = {
            'events_found': len(all_events),
            'entries_matched': len(matches),
            'recalls_recorded': recalls_recorded,
            'adapters_scanned': len(self.adapters),
            'scan_duration_ms': duration_ms,
        }
        logger.info(f"[RecallScanner] Scan complete: {result}")
        return result

    def _load_entries(self) -> tuple[dict, dict]:
        """从store加载所有活跃entries，构建两个索引"""
        entries_by_hash = {}
        entries_by_id = {}

        try:
            rows = self.store.conn.execute(
                "SELECT id, content_hash, content_preview, content FROM entries WHERE status = 'active'"
            ).fetchall()
            for row in rows:
                entry = {
                    'id': row[0],
                    'content_hash': row[1],
                    'content_preview': row[2] or '',
                    'content': row[3] or '',
                }
                entries_by_id[row[0]] = entry
                if row[1]:
                    entries_by_hash[row[1]] = entry
        except Exception as e:
            logger.warning(f"[RecallScanner] Failed to load entries: {e}")

        return entries_by_hash, entries_by_id

    def _record_recalls(self, events: list[RecallEvent], matches: list[dict]) -> int:
        """将匹配结果记录到agent_recall_log表
        
        同时记录：匹配到的entries的recall + 未匹配的events（作为原始数据留存）
        """
        recorded = 0

        # 记录匹配到的entries
        for match in matches:
            entry_id = match['entry_id']
            confidence = match['confidence']
            method = match['method']
            agent_id = match.get('agent_id', 'unknown')
            timestamp = match.get('recall_timestamp', datetime.now())
            
            if isinstance(timestamp, datetime):
                ts_str = timestamp.isoformat()
            else:
                ts_str = str(timestamp)

            try:
                self.store.conn.execute(
                    """INSERT INTO agent_recall_log 
                    (entry_id, agent_id, timestamp, source, confidence, context_snippet, match_method)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (entry_id, agent_id, ts_str, 'session_log', confidence, '', method)
                )
                recorded += 1
            except Exception as e:
                logger.warning(f"[RecallScanner] Failed to record recall for entry {entry_id}: {e}")

        # 对匹配到的entries，更新entries表的last_recalled字段
        for match in matches:
            entry_id = match['entry_id']
            timestamp = match.get('recall_timestamp', datetime.now())
            if isinstance(timestamp, datetime):
                ts_str = timestamp.isoformat()
            else:
                ts_str = str(timestamp)

            try:
                self.store.conn.execute(
                    "UPDATE entries SET last_recalled = ? WHERE id = ?",
                    (ts_str, entry_id)
                )
            except Exception as e:
                logger.warning(f"[RecallScanner] Failed to update last_recalled for entry {entry_id}: {e}")

        try:
            self.store.conn.commit()
        except Exception:
            pass

        return recorded

    def get_recall_stats(self) -> dict:
        """获取recall统计信息"""
        stats = {
            'total_recalls': 0,
            'entries_recalled': 0,
            'agents': {},
            'last_scan': self.last_scan_time.isoformat() if self.last_scan_time else None,
        }

        try:
            stats['total_recalls'] = self.store.conn.execute("SELECT COUNT(*) FROM agent_recall_log").fetchone()[0]

            stats['entries_recalled'] = self.store.conn.execute("SELECT COUNT(DISTINCT entry_id) FROM agent_recall_log").fetchone()[0]

            for row in self.store.conn.execute(
                "SELECT agent_id, COUNT(*) FROM agent_recall_log GROUP BY agent_id"
            ).fetchall():
                stats['agents'][row[0]] = row[1]
        except Exception:
            pass

        return stats

    def get_entry_recall_history(self, entry_id: str) -> list[dict]:
        """获取某个entry的recall历史"""
        history = []
        try:
            for row in self.store.conn.execute(
                """SELECT agent_id, timestamp, source, confidence, match_method 
                FROM agent_recall_log WHERE entry_id = ? ORDER BY timestamp DESC""",
                (entry_id,)
            ).fetchall():
                history.append({
                    'agent_id': row[0],
                    'timestamp': row[1],
                    'source': row[2],
                    'confidence': row[3],
                    'match_method': row[4],
                })
        except Exception:
            pass
        return history