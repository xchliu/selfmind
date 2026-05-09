# SelfMind 🧠

**个人专属 AI 记忆库 — 可见 · 可移植 · 可修改**

基于认知心理学的 AI 记忆可视化系统，记录记忆的演变过程。

## Quick Start

### Docker (推荐)

```bash
# 1. 克隆仓库
git clone https://github.com/xchliu/selfmind.git
cd selfmind

# 2. 配置环境
cp .env.example .env
# 编辑 .env，设置你的数据目录路径

# 3. (可选) 自定义配置
cp config.example.json config.json
# 编辑 config.json，调整分类、wiki路径等

# 4. 启动
docker compose up -d

# 5. 打开浏览器
open http://localhost:3002
```

### 本地运行

```bash
# 1. 克隆仓库
git clone https://github.com/xchliu/selfmind.git
cd selfmind

# 2. (可选) 自定义配置
cp config.example.json config.json

# 3. 直接启动（纯Python，无需pip install）
python3 server.py

# 4. 打开浏览器
open http://localhost:3002
```

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SELFMIND_PORT` | 3002 | 服务端口 |
| `MEMORIES_PATH` | ~/.hermes/memories | 记忆文件目录 |
| `SKILLS_PATH` | ~/.hermes/skills | 技能文件目录 |
| `WIKI_PATH` | ~/Documents/aiworkspace/wiki | Wiki知识库目录 |
| `HONCHO_ENABLED` | true | 是否启用Honcho数据源 |
| `HONCHO_API_URL` | http://host.docker.internal:8000/v3 | Honcho API地址 |
| `LLM_BASE_URL` | https://api.openai.com/v1 | LLM API地址（AI分析功能需要） |

详见 [.env.example](.env.example)

## 数据源

SelfMind 从4个数据源采集记忆：

1. **记忆文件** — MEMORY.md / USER.md（§分隔条目 + [分类/子类]标签）
2. **Wiki知识库** — markdown文件（YAML frontmatter + 内容）
3. **Honcho**（可选） — 语义观察、归纳推理、矛盾检测
4. **技能目录** — SKILL.md文件（YAML frontmatter）

所有数据源统一采集到 SQLite，记录演变过程（版本号、衰减分、时间线）。

## 文档

- [完整README](docs/README.md) — 特性详解、架构说明
- [产品需求文档](docs/PRD.md)
- [路线图](docs/ROADMAP.md)
- [更新日志](docs/CHANGELOG.md)
- [记忆分类设计](docs/MEMORY_TAXONOMY.md)

## License

MIT