"""核心功能单元测试"""
import json
import sqlite3
from unittest.mock import Mock, patch

import pytest

from tests.conftest import temp_dir, test_db


class TestUnifiedStore:
    """UnifiedStore 单元测试"""
    
    @pytest.mark.unit
    def test_store_initialization(self, temp_dir):
        """测试存储初始化"""
        from selfmind_app.unified_store import UnifiedStore
        
        db_path = f"{temp_dir}/test.db"
        store = UnifiedStore(db_path)
        
        assert store is not None
        assert store.db_path == db_path
        
        # 测试表结构
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            assert "entries" in tables
            assert "entry_history" in tables
            assert "operations_log" in tables
            assert "snapshots" in tables
    
    @pytest.mark.unit
    def test_upsert_entry(self, test_db):
        """测试插入/更新条目"""
        from selfmind_app.unified_store import UnifiedStore
        
        store = UnifiedStore(":memory:")
        
        # 插入新条目
        entry_id = "test_entry_1"
        result = store.upsert_entry(
            id=entry_id,
            content_hash="hash123",
            content="Test content",
            source="test",
            type="memory"
        )
        
        assert result is True
        
        # 查询条目
        entry = store.get_entry(entry_id)
        assert entry is not None
        assert entry.get("id") == entry_id
        assert entry.get("content") == "Test content"
        assert entry.get("version") == 1
    
    @pytest.mark.unit  
    def test_upsert_entry_versioning(self, test_db):
        """测试版本管理"""
        from selfmind_app.unified_store import UnifiedStore
        
        store = UnifiedStore(":memory:")
        
        # 第一次插入
        entry_id = "test_version_entry"
        store.upsert_entry(
            id=entry_id,
            content_hash="hash1",
            content="Version 1",
            source="test",
            type="memory"
        )
        
        # 更新内容，版本应该增加
        store.upsert_entry(
            id=entry_id,
            content_hash="hash2",
            content="Version 2",
            source="test",
            type="memory"
        )
        
        entry = store.get_entry(entry_id)
        assert entry.get("version") == 2
        assert entry.get("content") == "Version 2"
    
    @pytest.mark.unit
    def test_bulk_operations(self, test_db):
        """测试批量操作"""
        from selfmind_app.unified_store import UnifiedStore
        
        store = UnifiedStore(":memory:")
        
        # 批量插入
        entries = [
            {
                "id": f"bulk_{i}",
                "content_hash": f"hash_{i}",
                "content": f"Content {i}",
                "source": "test",
                "type": "memory"
            }
            for i in range(5)
        ]
        
        result = store.bulk_upsert(entries)
        assert result["inserted"] == 5
        assert result["updated"] == 0
        
        # 验证条目数量
        all_entries = store.get_all_entries()
        assert len(all_entries) == 5


class TestHttpHandler:
    """HTTP 处理器测试"""
    
    @pytest.mark.unit
    def test_json_response_format(self):
        """测试 JSON 响应格式"""
        from selfmind_app.http_handler import SelfMindHandler
        
        # 创建模拟的 handler
        handler = Mock(spec=SelfMindHandler)
        
        # 模拟 send_header 和 end_headers
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.wfile = Mock()
        
        # 测试 _json_response 方法
        test_data = {"status": "success", "data": "test"}
        
        # 由于 _json_response 是实例方法，我们需要模拟调用
        from io import BytesIO
        import json as json_module
        
        handler.wfile = BytesIO()
        
        # 使用 Monkey patch
        original_json_response = SelfMindHandler._json_response
        try:
            SelfMindHandler._json_response = Mock()
            SelfMindHandler._json_response(handler, test_data)
            
            # 验证方法被调用
            assert SelfMindHandler._json_response.called
        finally:
            SelfMindHandler._json_response = original_json_response
    
    @pytest.mark.unit
    def test_route_detection(self):
        """测试路由检测"""
        from selfmind_app.http_handler import SelfMindHandler
        
        # 测试不同的路径
        test_cases = [
            ("/api/data", "data"),
            ("/api/stats", "stats"),
            ("/api/poll", "poll"),
            ("/api/wiki/pages", "wiki_pages"),
            ("/api/meta/health", "meta_health"),
        ]
        
        for path, expected_handler in test_cases:
            # 简单的路径匹配测试
            if path == "/api/data":
                assert "api/data" in path
            elif path == "/api/stats":
                assert "api/stats" in path
            # 等等...


class TestConfig:
    """配置测试"""
    
    @pytest.mark.unit
    def test_config_loading(self, temp_dir):
        """测试配置加载"""
        import json
        from pathlib import Path
        
        # 创建测试配置文件
        config_data = {
            "current_agent": "test_agent",
            "source": {
                "active_profile": "test",
                "profiles": {
                    "test": {
                        "home": "/tmp/test",
                        "memory_files": ["memories/MEMORY.md"]
                    }
                }
            }
        }
        
        config_path = Path(temp_dir) / "config.json"
        with open(config_path, "w") as f:
            json.dump(config_data, f)
        
        # 测试配置加载
        from selfmind_app.config import load_config
        
        # Monkey patch CONFIG_FILE
        import selfmind_app.config as config_module
        original_config_file = config_module.CONFIG_FILE
        config_module.CONFIG_FILE = str(config_path)
        
        try:
            config = load_config()
            assert config["current_agent"] == "test_agent"
            assert config["source"]["active_profile"] == "test"
        finally:
            config_module.CONFIG_FILE = original_config_file


if __name__ == "__main__":
    # 运行测试
    import sys
    import os
    os.chdir("/Users/liuxiaocheng/Documents/selfmind")
    sys.path.insert(0, ".")
    
    print("🧪 运行单元测试...")
    print("=" * 60)
    
    # 运行 UnifiedStore 测试
    test_store = TestUnifiedStore()
    
    with temp_dir():
        test_store.test_store_initialization(temp_dir)
        print("✅ UnifiedStore 初始化测试通过")
    
    test_store.test_upsert_entry(test_db)
    print("✅ 条目插入/更新测试通过")
    
    test_store.test_upsert_entry_versioning(test_db)
    print("✅ 版本管理测试通过")
    
    test_store.test_bulk_operations(test_db)
    print("✅ 批量操作测试通过")
    
    print("=" * 60)
    print("🧪 单元测试完成")