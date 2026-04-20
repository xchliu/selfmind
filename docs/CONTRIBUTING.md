# Contributing to SelfMind

Thanks for your interest in contributing! Here's how to get started.

## Getting Started

1. **Fork** the repo and clone your fork
2. **Install** dependencies: `pip install -r requirements.txt`
3. **Run** the dev server: `python server.py`
4. Open `http://localhost:3002` and verify it works

## Project Structure

```
selfmind/
├── index.html             # Frontend — single-page app (HTML + CSS + JS)
├── server.py              # Backend entrypoint (HTTP server bootstrap)
├── selfmind_app/
│   ├── config.py          # Config loading, profile selection, legacy migration
│   ├── parser.py          # Memory parsing + graph building
│   └── http_handler.py    # API handlers
├── config.json            # Runtime config (source profiles)
├── data.json              # Graph data cache (auto-generated)
└── PRD.md                 # Product requirements (design spec)
```

- **Frontend** is a single HTML file with inline CSS and JavaScript. No build tools.
- **Backend** uses Python standard library HTTP server with modular parsing/config layers.
- Built-in source profiles: `hermes`, `openclaw`, `honcho`.

## How to Contribute

### Bug Reports

Open an issue with:
- What you expected
- What actually happened
- Browser + OS info
- Console errors (if any)

### Feature Requests

Open an issue describing:
- The problem you're trying to solve
- Your proposed solution
- Any alternatives you've considered

### Code Changes

1. Create a branch: `git checkout -b feature/my-feature`
2. Make your changes
3. Test locally — make sure the graph renders correctly
4. Commit with a clear message: `git commit -m "Add: description of change"`
5. Push and open a Pull Request

### Commit Messages

Use prefixes:
- `Add:` — new feature
- `Fix:` — bug fix
- `Improve:` — enhancement to existing feature
- `Refactor:` — code restructuring
- `Docs:` — documentation only
- `Style:` — formatting, no logic change

## Code Style

### Python (backend)
- Follow PEP 8
- Use type hints where practical
- Keep functions focused and documented

### JavaScript (index.html)
- Vanilla JS only — no frameworks, no build step
- D3.js v7 via CDN
- Use `const`/`let`, never `var`
- Descriptive function and variable names

### CSS (index.html)
- Inline in `<style>` block
- Use CSS custom properties for theme values (future)
- Prefer `rgba()` for transparency
- Mobile-responsive where practical

## Design Principles

1. **Zero config** — Should work out of the box with sensible defaults
2. **Single file** — Frontend stays in one HTML file. No bundlers.
3. **Minimal dependencies** — Backend uses Python stdlib only
4. **Offline-first** — Graph data is cached locally; no external model required
5. **Readable code** — Clarity over cleverness

## Adding a New Memory Source

To support a new agent framework's memory format:

1. Add/extend profile config in `selfmind_app/config.py`
2. Add parsing logic in `selfmind_app/parser.py`
3. Keep API behavior unchanged in `selfmind_app/http_handler.py`
4. Parse the format into the standard `{nodes, links}` structure
5. Follow the existing node schema (`id`, `label`, `category`, `description`)
6. Submit a PR with a sample memory file for testing

## Questions?

Open an issue or start a discussion. We're friendly. 🧠
