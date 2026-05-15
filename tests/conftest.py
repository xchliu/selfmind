"""测试工具和夹具"""
import os
import tempfile
import sqlite3
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# 测试配置
TEST_CONFIG = {
    "current_agent": "test_agent",
    "source": {
        "active_profile": "test_profile",
        "profiles": {
            "test_profile": {
                "home": "/tmp/test_hermes",
                "memory_files": ["memories/MEMORY.md", "memories/USER.md"],
                "skills_path": "skills",
                "wiki_path": "wiki"
            }
        }
    },
    "agents": [
        {
            "id": "test_agent",
            "name": "Test Agent",
            "type": "hermes",
            "gateway": "http://localhost:9999",
            "extensions": {
                "memory_path": "/tmp/test_hermes/memories",
                "skills_path": "/tmp/test_hermes/skills",
                "wiki_path": "/tmp/test_wiki"
            }
        }
    ]
}

class TempDirectoryFixture:
    """临时目录夹具"""
    
    def __init__(self):
        self.temp_dir = None
        self.original_cwd = None
    
    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="selfmind_test_")
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # 创建必要的测试目录
        Path("memories").mkdir(exist_ok=True)
        Path("skills").mkdir(exist_ok=True)
        Path("wiki").mkdir(exist_ok=True)
        Path("data").mkdir(exist_ok=True)
        
        return self.temp_dir
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(self.original_cwd)
        # 清理临时目录
        import shutil
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

def create_test_memory_file(content=None):
    """创建测试记忆文件"""
    if content is None:
        content = """[primary/autobiographical/identity]
Name: Test User
Role: Tester

[primary/security/rules]
测试安全规则: 仅用于测试

[primary/procedural/testing]
测试流程: 1. 准备 2. 执行 3. 验证"""
    
    return content

def create_test_db(db_path=":memory:"):
    """创建测试数据库"""
    conn = sqlite3.connect(db_path)
    
    # 创建表结构（与 unified_store.py 保持一致）
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS entries (
        id TEXT PRIMARY KEY,
        content_hash TEXT NOT NULL,
        content TEXT NOT NULL,
        content_preview TEXT,
        primary_cat TEXT,
        secondary_cat TEXT,
        label TEXT,
        tags TEXT,
        source TEXT NOT NULL,
        type TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        version INTEGER DEFAULT 1,
        first_seen_at TEXT,
        updated_at TEXT,
        last_synced_at TEXT,
        access_count INTEGER DEFAULT 0,
        last_accessed TEXT,
        importance REAL DEFAULT 0.5,
        decay_score REAL DEFAULT 0.25,
        pinned INTEGER DEFAULT 0,
        metadata TEXT
    );
    
    CREATE TABLE IF NOT EXISTS entry_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        before_content TEXT,
        after_content TEXT,
        changed_at TEXT NOT NULL,
        FOREIGN KEY (entry_id) REFERENCES entries(id)
    );
    
    CREATE TABLE IF NOT EXISTS operations_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        operation TEXT NOT NULL,
        entry_id TEXT,
        detail TEXT,
        timestamp TEXT NOT NULL
    );
    
    CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_type TEXT NOT NULL,
        content TEXT NOT NULL,
        stats TEXT,
        created_at TEXT NOT NULL
    );
    """)
    
    return conn

@pytest.fixture
def temp_dir():
    """临时目录夹具"""
    with TempDirectoryFixture() as temp_dir:
        yield temp_dir

@pytest.fixture
def test_db():
    """测试数据库夹具"""
    conn = create_test_db()
    yield conn
    conn.close()

@pytest.fixture
def test_config():
    """测试配置夹具"""
    return TEST_CONFIG.copy()

@pytest.fixture
def mock_http_response():
    """模拟HTTP响应夹具"""
    
    def create_response(status_code=200, json_data=None, text=None):
        response = Mock()
        response.status_code = status_code
        response.ok = status_code < 400
        
        if json_data:
            response.json.return_value = json_data
            response.text = json.dumps(json_data)
        elif text:
            response.text = text
            response.json.side_effect = ValueError("Not JSON")
        
        return response
    
    return create_response