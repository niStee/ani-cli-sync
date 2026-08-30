# AGENTS.md — ani-cli-sync

> Parent: [~/Projects/AGENTS.md](../AGENTS.md) — multi-repo index, forge remotes, CI/CD matrix.

Automated AniList synchronization wrapper for [`ani-cli`](https://github.com/pystardust/ani-cli).

## Project Overview

- **Stack**: Python `>=3.10` (standard library only, zero external runtime dependencies)
- **Packaging**: Standard `pyproject.toml` with `hatchling` build backend
- **Primary Remote**: `git@github.com:niStee/ani-cli-sync.git` (GitHub public)
- **Mirror Remote**: `git@codeberg.org:niStee/ani-cli-sync.git` (Codeberg private mirror)
- **License**: MIT
- **Entry-points**: both `ani-cli-sync` and `ani-sync` are registered aliases for the same `main()`

## Key Architectural Principles

1. **Watchlist-First Context Resolution**: Matches anime titles against active `CURRENT` watchlist before falling back to global AniList search to prevent accidental clobbering of completed seasons.
2. **Multi-Season Scraping Offset Handling**: Bridges AniList discrete season numbering with scraper backend continuous numbering via strict 3-tier precedence:
   - **Tier 1 (Explicit Table)**: `_EPISODE_OFFSETS` static overrides (can specify custom search queries).
   - **Tier 2 (Computed Chain)**: `compute_prequel_offset()` traverses AniList's relation graph for preceding `TV`/`ONA` nodes, summing total episodes (with cycle protection, depth limit 10, and ambiguity checks).
   - **Tier 3 (Identity)**: Fallback 1-to-1 numbering.
3. **Completion, Boundary Enforcement & Sequel Rollover**: Auto-transitions status to `COMPLETED` when `ep >= total`. Queries AniList for released TV/ONA sequels with a clobber guard (resumes at `progress + 1` if already in list, prompts in interactive mode or seamlessly continues in `--autoplay`).
4. **Zero Third-Party Runtime Dependencies**: Implemented strictly with standard library (`urllib.request`, `json`, `argparse`, `subprocess`, `pathlib`).

## Episode Offset Resolution & Precedence

Some scrapers (gogoanime / AniDB) use absolute continuous episode numbering across seasons, while AniList
tracks each season starting from episode 1. `resolve_episode_offset()` resolves the correct scraper episode:

1. `_EPISODE_OFFSETS` static table match (highest priority, supports search overrides)
2. `compute_prequel_offset()` PREQUEL-chain traversal (lazy-queried and cached per `media_id`)
3. Identity (`anilist_ep`)

| Show / Season | AniList ep range | Scraper ep range | Offset |
|---|---|---|---|
| Frieren: Beyond Journey's End Season 2 | 1–10 | 29–38 | +28 |
| Slime Season 2 | 1–12 | 25–36 | +24 |
| Slime Season 2 Part 2 | 1–12 | 37–48 | +36 |
| Slime Season 3 | 1–24 | 49–72 | +48 |

**Static Overrides**: To force a specific search string or override automatic chain resolution, append a tuple to `_EPISODE_OFFSETS` in `cli.py`. Standard multi-season shows are computed automatically.

## Commands & Testing

```bash
# Run unit test suite (16 tests)
PYTHONPATH=src python3 -m unittest discover -s tests

# Lint
ruff check src/ tests/

# Install locally as editable package
pip install -e .

# CLI usage
ani-cli-sync            # Interactive fzf selection (alias: ani-sync)
ani-cli-sync list       # List currently watching
ani-cli-sync set <title> <ep>  # Update progress (AniList ep, NOT scraper ep)
ani-cli-sync login      # OAuth setup
ani-cli-sync -a         # Watch with autoplay
```

## Troubleshooting: Stuck AniList State

If an anime is not appearing in the fzf watchlist picker, it is not in `CURRENT` status on AniList.

**Diagnosis:**
```bash
ani-sync list           # Shows current CURRENT entries
```

**Fix — reset to CURRENT at the right AniList episode:**
```bash
# Always use the AniList episode number (1-based within the season),
# NOT the absolute scraper/AniDB episode number.
ani-sync set "Frieren: Beyond Journey's End Season 2" 1   # ep 1 of S2 = scraper ep 29
```

**If `set` returns `episode exceeds total` error**: you accidentally passed a scraper ep.
Divide the scraper ep by the offset to find the correct AniList ep (see offset table above).

**If the show was accidentally marked COMPLETED**, use `set` at the correct episode — it will
re-open it as `CURRENT` as long as `ep < total`.
