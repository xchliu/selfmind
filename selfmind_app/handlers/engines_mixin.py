"""Engine handler methods: consolidator, forgetter, analyzer."""

import json
import logging
import os

from selfmind_app.config import CONFIG_FILE, DATA_FILE, SELFMIND_DIR, load_config, get_enabled_profiles
from selfmind_app.consolidator import Consolidator
from selfmind_app.forgetter import ForgetterEngine
from selfmind_app.analyzer import AnalyzerEngine

logger = logging.getLogger(__name__)


class EnginesMixin:
    """Handler methods for engine operations: consolidation, forgetting, analysis."""

    def _get_consolidator(self) -> Consolidator:
        global_ref = self._get_global_consolidator_ref()
        if global_ref is None:
            from selfmind_app.http_handler import SelfMindHandler
            config = load_config()
            source_cfg = config.get("source", {})
            active = source_cfg.get("active_profile", "hermes")
            profile = source_cfg.get("profiles", {}).get(active, {})
            home = profile.get("home", "")
            memory_path = user_path = None
            for f in profile.get("memory_files", []):
                full = os.path.join(home, f)
                if os.path.exists(full):
                    if "memory" in f.lower():
                        memory_path = full
                    elif "user" in f.lower():
                        user_path = full
            store = getattr(SelfMindHandler, '_store', None)
            new_consolidator = Consolidator(store, memory_path or "", user_path)
            self._set_global_consolidator_ref(new_consolidator)
            return new_consolidator
        return global_ref

    def _get_global_consolidator_ref(self):
        """Get the module-level _consolidator reference."""
        import selfmind_app.http_handler as handler_module
        return handler_module._consolidator

    def _set_global_consolidator_ref(self, value):
        """Set the module-level _consolidator reference."""
        import selfmind_app.http_handler as handler_module
        handler_module._consolidator = value

    def _get_forgetter(self) -> ForgetterEngine:
        import selfmind_app.http_handler as handler_module
        if handler_module._forgetter is None:
            handler_module._forgetter = ForgetterEngine()
        return handler_module._forgetter

    def _get_analyzer(self) -> AnalyzerEngine:
        import selfmind_app.http_handler as handler_module
        if handler_module._analyzer is None:
            handler_module._analyzer = AnalyzerEngine()
        return handler_module._analyzer

    def _handle_consolidate_scan(self):
        c = self._get_consolidator()
        self._json_response(c.run_full_scan())

    def _handle_consolidate_duplicates(self):
        c = self._get_consolidator()
        # Use graph data (nodes/links) instead of metadataDB
        self._json_response(c.find_duplicates_from_graph())

    def _handle_consolidate_conflicts(self):
        c = self._get_consolidator()
        # TODO: Implement conflict detection for graph data
        self._json_response({"conflicts": [], "message": "Conflict detection from graph data not yet implemented"})

    def _handle_consolidate_distribution(self):
        c = self._get_consolidator()
        # Use graph data for distribution analysis
        self._json_response(c.analyze_distribution_from_graph())

    def _handle_consolidate_llm(self):
        from selfmind_app.http_handler import SelfMindHandler
        try:
            body = self._read_body()
        except Exception as exc:
            self._json_response({"error": f"Invalid JSON: {exc}"}, code=400)
            return
        entry_ids = body.get("entry_ids", [])
        task = body.get("task", "merge")
        if not entry_ids:
            self._json_response({"error": "Provide 'entry_ids' array"}, code=400)
            return
        store = getattr(SelfMindHandler, '_store', None)
        if not store:
            self._json_response({"error": "Store not available"}, code=503)
            return
        entries = [store.get_entry(eid) for eid in entry_ids]
        entries = [e for e in entries if e]
        if not entries:
            self._json_response({"error": "No valid entries found"}, code=404)
            return
        c = self._get_consolidator()
        result = c.llm_consolidate(entries, task)
        if result:
            self._json_response(result)
        else:
            self._json_response({"error": "LLM not configured"}, code=400)

    # ── Forgetter API handlers ───────────────────────────────────────

    def _handle_forget_analyze(self):
        """分析哪些记忆应该被遗忘"""
        f = self._get_forgetter()
        # Use graph data for analysis
        self._json_response(f.analyze_forget_from_graph())

    def _handle_forget_execute(self):
        """执行遗忘操作"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
        try:
            params = json.loads(body) if body else {}
        except json.JSONDecodeError:
            params = {}
        
        memory_ids = params.get('memory_ids')
        dry_run = params.get('dry_run', False)
        
        f = self._get_forgetter()
        result = f.run_forgetting(memory_ids=memory_ids, dry_run=dry_run)
        self._json_response(result)

    def _handle_forget_restore(self):
        """恢复已遗忘的记忆"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
        try:
            params = json.loads(body) if body else {}
        except json.JSONDecodeError:
            params = {}
        
        memory_id = params.get('memory_id')
        if not memory_id:
            self._json_response({"error": "Provide 'memory_id'"}, code=400)
            return
        
        f = self._get_forgetter()
        result = f.restore_memory(memory_id)
        self._json_response({"success": result, "memory_id": memory_id})

    # ── Analyzer API handlers ────────────────────────────────────────

    def _handle_analyze_patterns(self):
        """分析记忆模式"""
        a = self._get_analyzer()
        # TODO: Implement pattern analysis for graph data
        self._json_response({"patterns": [], "message": "Pattern analysis from graph data not yet implemented"})

    def _handle_analyze_graph(self):
        """更新知识图谱"""
        a = self._get_analyzer()
        # Use graph data insights
        self._json_response(a.extract_insights_from_graph())

    def _handle_analyze_importance(self):
        """分析记忆重要性"""
        a = self._get_analyzer()
        # Use graph data for importance analysis
        self._json_response(a.analyze_importance_from_graph())

    def _handle_analyze_completeness(self):
        """分析知识完整性"""
        a = self._get_analyzer()
        # Use graph data insights for completeness
        self._json_response(a.extract_insights_from_graph())

    def _handle_analyze_full(self):
        """完整分析"""
        a = self._get_analyzer()
        result = a.run_full_analysis()
        self._json_response(result)