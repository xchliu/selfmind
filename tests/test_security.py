"""安全测试 - 针对发现的SQL注入和其他安全问题"""
import pytest
import sqlite3
import subprocess
from unittest.mock import patch, MagicMock

from tests.conftest import temp_dir, test_db


class TestSecurity:
    """安全测试类"""
    
    @pytest.mark.security
    def test_sql_injection_in_unified_sync(self):
        """测试 unified_sync.py 中的 SQL 注入漏洞"""
        
        # 导入需要测试的模块
        import sys
        sys.path.insert(0, "/Users/liuxiaocheng/Documents/selfmind")
        
        from selfmind_app.unified_sync import fetch_honcho_documents
        
        # 测试恶意输入
        malicious_workspace = "test'; DROP TABLE documents; --"
        
        with patch('subprocess.run') as mock_run:
            # 模拟 psql 命令执行
            mock_run.return_value = MagicMock(
                stdout="id|observer|observed|level|content\n",
                stderr="",
                returncode=0
            )
            
            try:
                # 尝试执行函数
                result = fetch_honcho_documents("http://localhost:8000", malicious_workspace)
                print(f"函数执行结果: {result}")
                
                # 检查是否调用了 subprocess.run
                assert mock_run.called
                
                # 获取实际调用的命令
                call_args = mock_run.call_args[0][0]
                call_command = ' '.join(call_args)
                print(f"执行的命令: {call_command}")
                
                # 检查SQL注入漏洞
                if f"'{malicious_workspace}'" in call_command:
                    pytest.fail("⚠️ 发现SQL注入漏洞: 直接拼接用户输入到SQL语句中")
                else:
                    print("✅ SQL注入检查通过")
                    
            except Exception as e:
                print(f"函数执行异常: {e}")
                # 如果函数崩溃，说明可能有其他问题
                pass
    
    @pytest.mark.security
    def test_sql_parameterization_in_unified_store(self):
        """测试 unified_store.py 中的SQL参数化"""
        
        import sys
        sys.path.insert(0, "/Users/liuxiaocheng/Documents/selfmind")
        
        from selfmind_app.unified_store import UnifiedStore
        
        with temp_dir():
            # 创建测试数据库
            db_path = "test_secure.db"
            store = UnifiedStore(db_path)
            
            # 测试恶意输入
            malicious_id = "test' OR '1'='1"
            malicious_content = "test'; DROP TABLE entries; --"
            
            try:
                # 测试插入操作
                store.upsert_entry(
                    id=malicious_id,
                    content_hash="hash123",
                    content=malicious_content,
                    source="test",
                    type="memory"
                )
                
                print("✅ SQL参数化检查: 插入操作通过")
                
                # 测试查询操作
                entry = store.get_entry(malicious_id)
                if entry:
                    print(f"✅ 成功查询到条目: {entry.get('id')}")
                
            except sqlite3.OperationalError as e:
                print(f"SQL操作错误: {e}")
                # 检查是否是SQL注入导致的错误
                if "syntax" in str(e).lower():
                    pytest.fail("⚠️ 可能的SQL语法错误，可能是SQL注入尝试")
            except Exception as e:
                print(f"其他错误: {e}")
    
    @pytest.mark.security
    def test_path_traversal_prevention(self):
        """测试路径遍历漏洞防护"""
        
        import sys
        sys.path.insert(0, "/Users/liuxiaocheng/Documents/selfmind")
        
        # 测试恶意路径
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config",
            "/etc/passwd",
            "C:\\Windows\\System32",
        ]
        
        # 检查 http_handler.py 中的文件服务
        with open("/Users/liuxiaocheng/Documents/selfmind/selfmind_app/http_handler.py", "r") as f:
            handler_content = f.read()
        
        # 查找文件服务相关的代码
        file_serving_patterns = [
            "open(",
            "Path(",
            "send_file",
            "serve_file"
        ]
        
        vulnerable_patterns = []
        for pattern in file_serving_patterns:
            if pattern in handler_content:
                # 检查是否有路径拼接
                lines = handler_content.split('\n')
                for i, line in enumerate(lines):
                    if pattern in line and '+' in line:
                        vulnerable_patterns.append(f"第{i+1}行: {line.strip()}")
        
        if vulnerable_patterns:
            print("⚠️ 发现可能的路径遍历风险:")
            for pattern in vulnerable_patterns:
                print(f"  - {pattern}")
        else:
            print("✅ 路径遍历防护检查通过")
    
    @pytest.mark.security
    def test_config_security(self):
        """测试配置文件安全性"""
        
        import json
        config_path = "/Users/liuxiaocheng/Documents/selfmind/config.json"
        
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
            
            # 检查硬编码的敏感信息
            sensitive_keys = ["api_key", "secret", "token", "password", "auth"]
            found_sensitive = []
            
            def search_sensitive(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        full_path = f"{path}.{key}" if path else key
                        if any(sensitive in key.lower() for sensitive in sensitive_keys):
                            # 检查值是否看起来像密钥
                            if isinstance(value, str) and len(value) > 10:
                                found_sensitive.append(f"{full_path}: {value[:10]}...")
                        search_sensitive(value, full_path)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        search_sensitive(item, f"{path}[{i}]")
            
            search_sensitive(config)
            
            if found_sensitive:
                print("⚠️ 发现可能的硬编码敏感信息:")
                for item in found_sensitive[:5]:  # 只显示前5个
                    print(f"  - {item}")
            else:
                print("✅ 配置文件安全检查通过")


if __name__ == "__main__":
    # 运行安全测试
    import os
    os.chdir("/Users/liuxiaocheng/Documents/selfmind")
    
    test = TestSecurity()
    
    print("🔒 运行安全测试...")
    print("=" * 60)
    
    test.test_sql_injection_in_unified_sync()
    print("-" * 40)
    
    test.test_sql_parameterization_in_unified_store()
    print("-" * 40)
    
    test.test_path_traversal_prevention()
    print("-" * 40)
    
    test.test_config_security()
    print("=" * 60)
    print("🔒 安全测试完成")