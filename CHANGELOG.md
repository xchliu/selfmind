# Changelog

All notable changes to SelfMind will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/).

---

## [0.2.0] — 2026-04-11

### Added
- Source profile support in `config.json` (`source.mode`, `active_profile`, `profiles`)
- OpenClaw memory source support (`~/.openclaw`)
- Honcho memory source support (`~/.honcho`)
- Multi-source parsing mode (`auto`) and single-profile mode (`single`)

### Changed
- Refactored backend into modules:
	- `selfmind_app/config.py`
	- `selfmind_app/parser.py`
	- `selfmind_app/http_handler.py`
- `server.py` is now a thin entrypoint
- Updated documentation to reflect standard-library HTTP backend and rule-based parsing

## [0.1.0] — 2025-04-11

### Added
- 🧠 Initial release
- Flask backend with LLM-powered memory parsing
- D3.js force-directed graph visualization
- 6 memory categories with color coding (identity, relationships, projects, rules, capabilities, environment)
- Node importance → size mapping
- Interactive hover highlighting (connected nodes + edges)
- Click-to-inspect detail panel
- Category filter bar
- Real-time search (name + description matching)
- Stats dashboard (nodes, links, categories, avg importance)
- Keyboard shortcuts (R/S/F/Escape)
- Graph data caching (data.json)
- Refresh + Save buttons
- Toast notifications (success/error/info)
- Light theme with glassmorphism UI
- SVG glow effect for high-importance nodes
- Drag-to-reposition nodes
- Zoom + pan canvas navigation
- Background grid decoration
- Support for Hermes Agent memory format (MEMORY.md + USER.md)
