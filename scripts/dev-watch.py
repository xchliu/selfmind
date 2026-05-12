#!/usr/bin/env python3
"""SelfMind开发自动重建守护脚本
检测 selfmind_app/ 和 server.py 的文件变化，自动 docker compose build && up -d

使用方式: python3 scripts/dev-watch.py
需要在 selfmind 项目根目录下运行
"""

import os
import sys
import time
import hashlib
import subprocess

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCH_DIRS = [
    os.path.join(PROJECT_DIR, "selfmind_app"),
    os.path.join(PROJECT_DIR, "server.py"),
    os.path.join(PROJECT_DIR, "Dockerfile"),
]
POLL_INTERVAL = 2  # 秒
DEBOUNCE_SECONDS = 3  # 稳定等待时间，避免连续保存触发多次重建


def file_hash(path):
    """计算文件的快速哈希（前4096字节+修改时间+大小）"""
    try:
        st = os.stat(path)
        if os.path.isfile(path):
            with open(path, "rb") as f:
                head = f.read(4096)
            return hash((head, st.st_mtime, st.st_size))
        else:
            # 目录用 mtime
            return st.st_mtime
    except OSError:
        return 0


def collect_hashes():
    """收集所有监控文件的哈希值"""
    hashes = {}
    for watch_dir in WATCH_DIRS:
        if os.path.isfile(watch_dir):
            hashes[watch_dir] = file_hash(watch_dir)
        elif os.path.isdir(watch_dir):
            for root, dirs, files in os.walk(watch_dir):
                # 跳过 __pycache__ 和 .pyc
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for f in files:
                    if f.endswith((".py", ".json", ".yaml", ".yml", ".txt", ".md")):
                        path = os.path.join(root, f)
                        hashes[path] = file_hash(path)
    return hashes


def rebuild():
    """执行 docker compose build && up -d"""
    print(f"\n[{time.strftime('%H:%M:%S')}] 检测到文件变化，开始重建...")
    try:
        result = subprocess.run(
            ["docker", "compose", "build"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"  BUILD FAILED:\n{result.stderr}")
            return False

        result = subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print(f"  [{time.strftime('%H:%M:%S')}] 重建完成，容器已重启")
            return True
        else:
            print(f"  UP FAILED:\n{result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("  BUILD/UP TIMEOUT")
        return False


def main():
    print(f"SelfMind 开发自动重建守护")
    print(f"监控目录/文件:")
    for d in WATCH_DIRS:
        print(f"  {d}")
    print(f"轮询间隔: {POLL_INTERVAL}s | 防抖: {DEBOUNCE_SECONDS}s")
    print(f"按 Ctrl+C 退出\n")

    prev_hashes = collect_hashes()
    changed_time = 0

    try:
        while True:
            time.sleep(POLL_INTERVAL)
            current_hashes = collect_hashes()

            has_changes = False
            for path, h in current_hashes.items():
                old_h = prev_hashes.get(path)
                if old_h != h:
                    relpath = os.path.relpath(path, PROJECT_DIR)
                    print(f"  [变化] {relpath}")
                    has_changes = True

            if has_changes:
                if changed_time == 0:
                    changed_time = time.time()
                elif time.time() - changed_time >= DEBOUNCE_SECONDS:
                    rebuild()
                    prev_hashes = collect_hashes()
                    changed_time = 0
                prev_hashes = current_hashes
            else:
                if changed_time > 0 and time.time() - changed_time >= DEBOUNCE_SECONDS:
                    rebuild()
                    prev_hashes = collect_hashes()
                    changed_time = 0
    except KeyboardInterrupt:
        print("\n已退出")


if __name__ == "__main__":
    main()
