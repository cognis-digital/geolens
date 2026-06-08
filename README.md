# GEOLENS — Image geolocation toolkit — EXIF, sun-shadow, OCR, reverse-search

> Part of the **[Cognis Neural Suite](https://github.com/cognis-digital)** by [Cognis Digital](https://cognis.digital)
> MIT License · domain: `osint`

[![PyPI](https://img.shields.io/pypi/v/cognis-geolens.svg)](https://pypi.org/project/cognis-geolens/)
[![CI](https://github.com/cognis-digital/geolens/actions/workflows/ci.yml/badge.svg)](https://github.com/cognis-digital/geolens/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Image geolocation toolkit — EXIF, sun-shadow, OCR, reverse-search.

## Install

```bash
pip install cognis-geolens
```

For local development from this repo:

```bash
pip install -e .
```

## Quick start

```bash
geolens --version
geolens scan demos/                          # run against bundled demo
geolens scan demos/ --format sarif --out r.sarif --fail-on high
geolens mcp                                   # start as MCP server (Cognis.Studio / Claude Desktop / Cursor)
```

## Built-in demo scenarios

Every scenario folder includes a `SCENARIO.md` describing what it represents and what findings to expect.

- `demos/01-osint-leak-from-vacation-photo/` — see [`SCENARIO.md`](demos/01-osint-leak-from-vacation-photo/SCENARIO.md)
- `demos/02-clean-photo/` — see [`SCENARIO.md`](demos/02-clean-photo/SCENARIO.md)
- `demos/03-batch-folder-mixed/` — see [`SCENARIO.md`](demos/03-batch-folder-mixed/SCENARIO.md)

## How it fits the Cognis Neural Suite

This tool is one of 52 in the [Cognis Neural Suite](https://github.com/cognis-digital). The full suite + launcher lives at:

- Suite landing: https://cognis.digital
- All 52 repos: https://github.com/cognis-digital
- Cognis.Studio (Enterprise AI Workforce, MCP host): https://cognis.studio

Every Suite tool ships an MCP server, so Cognis.Studio agents can call them as scoped capabilities.

## License

MIT. See [LICENSE](LICENSE).

## About

**[Cognis Digital](https://cognis.digital)** — Wyoming, USA · *Making Tomorrow Better Today: Advanced Cybersecurity, AI Innovation, and Blockchain Expertise.*
