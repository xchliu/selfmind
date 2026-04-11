<p align="center">
  <h1 align="center">🧠 SelfMind</h1>
  <p align="center"><strong>See what your AI remembers.</strong></p>
  <p align="center">Interactive knowledge graph for AI agent memory visualization.</p>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="#features">Features</a> ·
  <a href="#how-it-works">How It Works</a> ·
  <a href="PRD.md">PRD</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

---

## What is SelfMind?

AI agents accumulate memory over time — user preferences, project context, behavioral rules, relationship maps. But this memory is invisible. You can't see it, explore it, or understand how it's organized.

**SelfMind turns agent memory into a visual, interactive knowledge graph.**

Each memory becomes a node. Relationships become edges. Categories become colors. The result: a living map of everything your AI knows.

## Features

- 🕸️ **Force-directed graph** — D3.js powered, with physics simulation
- 🔍 **Search & filter** — Find memories by name, description, or category
- 🔌 **Multi-source memory support** — Parse from Hermes, OpenClaw, and Honcho profiles
- 🎨 **Color-coded categories** — Identity, relationships, projects, rules, tools, environment
- 📊 **Stats dashboard** — Node count, link count, category distribution
- 💾 **Persistent cache** — Parse once, load instantly
- ⌨️ **Keyboard shortcuts** — `Cmd/Ctrl+F` search, `Esc` close detail panel
- 🧊 **Glassmorphism UI** — Clean, modern light theme with backdrop blur

## Quick Start

### Prerequisites

- Python 3.8+

### Install & Run

```bash
git clone https://github.com/pinkpixel-dev/selfmind.git
cd selfmind
pip install -r requirements.txt

# Launch
python server.py
```

Open **http://localhost:3002** in your browser. Done.

### Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `HERMES_HOME` | `~/.hermes` | Hermes profile home directory |
| `OPENCLAW_HOME` | `~/.openclaw` | OpenClaw profile home directory |
| `HONCHO_HOME` | `~/.honcho` | Honcho profile home directory |
| `SELFMIND_SOURCE_MODE` | `auto` | `auto` reads all configured profiles, `single` reads one |
| `SELFMIND_PROFILE` | `hermes` | Active profile name when source mode is `single` |

### Source Profiles (`config.json`)

SelfMind now supports source profiles. You can parse one or many memory systems in the same graph.

Create your local config first:

```bash
cp config.example.json config.json
```

```json
{
  "source": {
    "mode": "auto",
    "active_profile": "hermes",
    "profiles": {
      "hermes": {
        "home": "~/.hermes",
        "memory_files": ["memories/MEMORY.md", "memories/USER.md"]
      },
      "openclaw": {
        "home": "~/.openclaw",
        "memory_files": ["memories/MEMORY.md", "memories/USER.md"]
      },
      "honcho": {
        "home": "~/.honcho",
        "memory_files": ["memories/MEMORY.md", "memories/USER.md"]
      }
    }
  }
}
```

## How It Works

```
Memory Profiles            Backend Modules              Browser
┌──────────────┐    read   ┌────────────────────┐ JSON ┌──────────────┐
│ ~/.hermes    │ ───────→ │ config.py          │ ───→ │  index.html  │
│ ~/.openclaw  │          │ parser.py          │      │  D3.js graph │
│ MEMORY.md    │          │ http_handler.py    │      │              │
└──────────────┘          │ server.py (entry)  │      └──────────────┘
                          └────────────────────┘
```

1. **Load config** — Resolve enabled source profiles from `config.json`
2. **Parse** — Read markdown memory files (separated by `§`)
3. **Analyze** — Classify each memory entry and extract relationships via rule matching
4. **Cache** — Results saved to `data.json` for instant reload
5. **Render** — D3.js force-directed graph with interactive exploration

### Memory File Format

SelfMind reads memories in a simple markdown format:

```markdown
First memory entry content here
§
Second memory entry — can be multi-line
with **markdown** formatting
§
Third memory entry
```

Each `§` on its own line separates individual memory entries. Supports Hermes, OpenClaw, and Honcho memory profiles via `config.json`.

### Backend Structure

```text
selfmind_app/
├── config.py        # default config, profile loading, legacy config migration
├── parser.py        # section parsing + graph building
└── http_handler.py  # API endpoints and refresh/save handlers
server.py            # minimal entrypoint
```

## Interactions

| Action | Effect |
|--------|--------|
| **Hover** a node | Highlights connected nodes and edges |
| **Click** a node | Opens detail panel with description |
| **Drag** a node | Repositions it (pins in place) |
| **Double-click** | Releases pinned node |
| **Scroll wheel** | Zoom in/out |
| **Drag canvas** | Pan the view |

## Node Categories

| Category | Color | Contains |
|----------|-------|----------|
| 🔴 Core Identity | `#ff6b6b` | Agent's self-definition |
| 🟠 Relationships | `#ffa502` | People, teams, connections |
| 🟢 Projects | `#2ed573` | Active work, tasks, goals |
| 🔵 Behavioral Rules | `#1e90ff` | Guidelines, red lines, principles |
| 🟣 Capabilities | `#a55eea` | Tools, skills, integrations |
| ⚪ Environment | `#778ca3` | Config, timezone, system info |

## Roadmap

- [ ] Edit memories directly from the graph (write back to .md)
- [ ] Dark/light theme toggle
- [ ] Save node positions across sessions
- [ ] Timeline view (memory creation order)
- [ ] Support more agent frameworks (LangChain, AutoGen, etc.)
- [ ] Memory health analysis (redundancy & conflict detection)
- [ ] Export as image / PDF
- [ ] Plugin system for custom memory sources

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE) — use it however you want.

---

<p align="center">
  Built with 🧠 by <a href="https://github.com/pinkpixel-dev">PinkPixel</a>
</p>
