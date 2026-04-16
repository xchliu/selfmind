import copy
import json
import os
from pathlib import Path

SELFMIND_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = SELFMIND_DIR / "data.json"
CONFIG_FILE = SELFMIND_DIR / "config.json"

DEFAULT_CONFIG = {
    "source": {
        "mode": os.environ.get("SELFMIND_SOURCE_MODE", "auto"),
        "active_profile": os.environ.get("SELFMIND_PROFILE", "hermes"),
        "profiles": {
            "hermes": {
                "home": str(Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))),
                "memory_files": ["memories/MEMORY.md", "memories/USER.md"],
                "memory_files_fallback": ["memory.md", "user.md"],
            },
            "openclaw": {
                "home": str(Path(os.environ.get("OPENCLAW_HOME", Path.home() / ".openclaw"))),
                "memory_files": ["memories/MEMORY.md", "memories/USER.md"],
                "memory_files_fallback": ["memory.md", "user.md", "memories.md", "profile.md"],
            },
            "honcho": {
                "home": str(Path(os.environ.get("HONCHO_HOME", Path.home() / ".honcho"))),
                "memory_files": ["memories/MEMORY.md", "memories/USER.md"],
                "memory_files_fallback": ["memory.md", "user.md", "memories.md", "profile.md"],
            },
        },
    },
    "section_separator": "§",
    "center_node": {
        "id": "self",
        "label": "Me",
        "category": "identity",
        "description": "Center node — the owner of this memory graph",
    },
    "categories": {
        "identity": {"keywords": [], "color": "#ff6b6b", "description": "Core identity"},
        "person": {"keywords": ["人", "member", "成员", "name", "角色"], "color": "#ffa502", "description": "People & relationships"},
        "project": {"keywords": ["project", "项目", "规划", "战略", "plan"], "color": "#2ed573", "description": "Projects & plans"},
        "principle": {"keywords": ["安全", "红线", "规则", "rule", "原则", "准则", "boundary", "行为"], "color": "#1e90ff", "description": "Rules & principles"},
        "tool": {"keywords": ["tool", "工具", "日历", "calendar", "公众号", "CLI", "MCP", "API"], "color": "#a55eea", "description": "Tools & integrations"},
        "environment": {"keywords": ["timezone", "时区", "style", "风格", "偏好", "prefer", "communication"], "color": "#778ca3", "description": "Environment & preferences"},
        "memory": {"keywords": [], "color": "#95a5a6", "description": "General memories"},
        "skill": {"keywords": ["skill", "技能"], "color": "#f39c12", "description": "Skills & capabilities"},
        "skill_category": {"keywords": [], "color": "#e67e22", "description": "Skill categories"},
    },
    "relation_keywords": {
        "管理|负责|老大|boss|manager|lead": "manages",
        "同事|协作|colleague|collaborat": "collaborates",
        "使用|工具|运营|use|operate": "uses",
        "遵守|规则|原则|follow|rule": "follows",
        "关注|执行|分析|参与|work|focus": "works on",
    },
    "llm": {
        "base_url": os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
        "api_key": os.environ.get("LLM_API_KEY", ""),
        "model": os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        "max_tokens": 4096,
    },
    "documents": {
        "watch_dir": os.environ.get("SELFMIND_DOCS_DIR", ""),
    },
    "wiki": {
        "enabled": True,
        "path": os.environ.get("SELFMIND_WIKI_PATH", str(Path.home() / "Documents" / "aiworkspace" / "wiki")),
        "categories": {
            "entity": {"color": "#e74c3c", "display_name": "实体", "shape": "circle"},
            "concept": {"color": "#3498db", "display_name": "概念", "shape": "diamond"},
            "comparison": {"color": "#2ecc71", "display_name": "对比分析", "shape": "square"},
            "query": {"color": "#f39c12", "display_name": "查询结果", "shape": "triangle"},
            "summary": {"color": "#9b59b6", "display_name": "摘要", "shape": "hexagon"},
            "wiki_tag": {"color": "#95a5a6", "display_name": "标签", "shape": "circle"},
            "wiki_center": {"color": "#e67e22", "display_name": "知识中心", "shape": "circle"},
        },
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge dictionaries, mutating and returning base."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def migrate_legacy_config(user_config: dict) -> dict:
    """Map old single-source config fields into source.profiles.hermes."""
    if "source" in user_config:
        return user_config

    migrated = copy.deepcopy(user_config)
    hermes_home = migrated.pop("hermes_home", None)
    memory_files = migrated.pop("memory_files", None)
    memory_files_fallback = migrated.pop("memory_files_fallback", None)

    source_cfg = {
        "mode": "single",
        "active_profile": "hermes",
        "profiles": {
            "hermes": {
                "home": hermes_home or DEFAULT_CONFIG["source"]["profiles"]["hermes"]["home"],
                "memory_files": memory_files or DEFAULT_CONFIG["source"]["profiles"]["hermes"]["memory_files"],
                "memory_files_fallback": memory_files_fallback or DEFAULT_CONFIG["source"]["profiles"]["hermes"]["memory_files_fallback"],
            }
        },
    }
    migrated["source"] = source_cfg
    return migrated


def load_config() -> dict:
    """Load config.json and merge onto defaults."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            user_config = migrate_legacy_config(user_config)
            deep_merge(config, user_config)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  ⚠️  config.json parse error, using defaults: {exc}")
    return config


def save_default_config() -> None:
    """Create config.json using defaults if it does not exist."""
    if CONFIG_FILE.exists():
        return
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
    print("  📝 Created config.json (customize profiles/categories/source mode)")


def get_enabled_profiles(config: dict) -> list[str]:
    source_cfg = config.get("source", {})
    profiles = source_cfg.get("profiles", {})
    mode = source_cfg.get("mode", "auto")

    if mode == "single":
        active = source_cfg.get("active_profile", "hermes")
        return [active] if active in profiles else []
    return list(profiles.keys())


def describe_sources(config: dict) -> str:
    source_cfg = config.get("source", {})
    profiles = source_cfg.get("profiles", {})
    enabled = get_enabled_profiles(config)
    parts = []
    for name in enabled:
        home = profiles.get(name, {}).get("home", "")
        parts.append(f"{name}={home}")
    if not parts:
        return "none"
    return "; ".join(parts)
