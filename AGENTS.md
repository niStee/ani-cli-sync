# AGENTS.md — ani-cli-sync

> Parent: [~/Projects/AGENTS.md](../AGENTS.md) — multi-repo index, forge remotes, CI/CD matrix.

Automated AniList synchronization wrapper for [`ani-cli`](https://github.com/pystardust/ani-cli).

## Project Overview

- **Stack**: Python `>=3.10` (standard library only, zero external runtime dependencies)
- **Packaging**: Standard `pyproject.toml` with `hatchling` build backend
- **Primary Remote**: `git@github.com:niStee/ani-cli-sync.git` (GitHub private)
- **Mirror Remote**: `git@codeberg.org:niStee/ani-cli-sync.git` (Codeberg private mirror)
- **License**: MIT

## Key Architectural Principles

1. **Watchlist-First Context Resolution**: Matches anime titles against active `CURRENT` watchlist before falling back to global AniList search to prevent accidental clobbering of completed seasons.
2. **Multi-Season Scraping Offset Handling**: Transparently bridges AniList discrete season numbering with scraper backend absolute episode counts (e.g. AniDB continuous offsets).
3. **Completion & Boundary Enforcement**: Auto-transitions status to `COMPLETED` when `ep >= total` and prevents autoplay loops past season finales.
4. **Zero Third-Party Runtime Dependencies**: Implemented strictly with standard library (`urllib.request`, `json`, `argparse`, `subprocess`, `pathlib`).

## Commands & Testing

```bash
# Run unit test suite
PYTHONPATH=src python3 -m unittest discover -s tests

# Install locally as editable package
pip install -e .

# CLI usage
ani-cli-sync            # Interactive fzf selection
ani-cli-sync list       # List currently watching
ani-cli-sync set <title> <ep> # Update progress
ani-cli-sync login      # OAuth setup
```
