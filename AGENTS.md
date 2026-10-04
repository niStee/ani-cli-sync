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
4. **Zero Third-Party Runtime Dependencies**: Implemented strictly with standard library (`urllib.request`, `json`, `argparse`, `subprocess`, `pathlib`, `concurrent.futures`).
5. **Automated Subtitle Fallback & Dual-Track Pipeline**: Inspects stream tracks (detecting forced tracks `< 50` cues vs. full dialogue). When target tracks are missing or signs-only, translates the base English track concurrently via local LiteLLM proxy (`deepseek-v4-flash`), producing synchronized German dialogue (`--sid=1`, bottom) and Traditional Chinese + Hanyu Pinyin (`--secondary-sid=2`, top) with persistent caching in `~/.cache/ani-cli/subtitles/`.

## Episode Offset Resolution & Precedence

Some scrapers (gogoanime / AniDB) use absolute continuous episode numbering across seasons, while AniList
tracks each season starting from episode 1. `resolve_episode_offset()` resolves the correct scraper episode:

1. `_EPISODE_OFFSETS` static table match (highest priority, supports search overrides)
2. `compute_prequel_offset()` PREQUEL-chain traversal (lazy-queried and cached per `media_id`)
3. Identity (`anilist_ep`)

| Show / Season | AniList ep range | Scraper ep range | Offset |
|---|---|---|---|
| Frieren: Beyond Journey's End Season 2 | 1–10 | 29–38 | +28 |
| Slime Season 2 | 1–12 | 1–12 | +0 |
| Slime Season 2 Part 2 | 1–12 | 1–12 | +0 |
| Slime Season 3 | 1–24 | 1–24 | +0 |
| Slime Season 4 | 1–24 | 1–24 | +0 |

**Static Overrides**: To force a specific search string or override automatic chain resolution, append a tuple to `_EPISODE_OFFSETS` in `cli.py`. Standard multi-season shows are computed automatically.

## Commands & Testing

```bash
# Run unit test suite
PYTHONPATH=src python3 -m unittest discover -s tests

# Lint
ruff check src/ tests/

# Lint debt ratchet (what CI gates on)
python3 scripts/ruff_count_ratchet.py
python3 scripts/ruff_count_ratchet.py --update          # lower the baseline after a cleanup
python3 scripts/ruff_count_ratchet.py --base-ref <sha>  # fail if the PR raised the allowance

# Install locally as editable package
pip install -e .

# CLI usage
ani-cli-sync            # Interactive fzf selection (alias: ani-sync)
ani-cli-sync list       # List currently watching
ani-cli-sync set <title> <ep>  # Update progress (AniList ep, NOT scraper ep)
ani-cli-sync login      # OAuth setup
ani-cli-sync -a         # Watch with autoplay
ani-cli-sync watch --sub-delay=-3.8 "Attack on Titan"  # Per-episode, measured per release (see below)
```

## Subtitle Sync Offset (`--sub-delay`)

Some releases ship **English subtitles timed to the English dub** while the audio track is
**Japanese original**. The subs then read as drifting even though mpv reports `A-V: 0.000`
(mpv only tracks demuxer PTS, not dialogue alignment).

`--sub-delay=<seconds>` shifts subtitle presentation. **Negative pulls subs earlier.**

Defaults to `0` (no flag emitted). Override with `ANI_CLI_SYNC_SUB_DELAY`.

### The offset is per-episode, not per-show

Measured on Attack on Titan S1, same release, same provider:

| Episode | First sub cue | JP audio onset | Offset |
|---|---|---|---|
| Ep 1 | `00:00:41.870` | ~38s | `-3.8` |
| Ep 2 | `00:00:21.540` | ~22s | `~0` |

**Do not carry an offset across episodes, and never treat it as a property of the series.**
Ep 1's subtitle file is dub-timed; ep 2's is already aligned to the Japanese audio. A flag
tuned on one episode actively mis-times the next -- `-3.8` on ep 2 pushed the first line to
`17.7s`, roughly 4s ahead of the dialogue.

A per-show default is therefore actively harmful, including via `ANI_CLI_SYNC_SUB_DELAY`.
Determine the value per episode.

### Measuring the offset

Cheapest reliable method: compare the **first subtitle cue** against the **first audible
Japanese line**. The cue timestamp is exact and needs no tooling:

```bash
python3 -c "
import sys; sys.path.insert(0,'src')
from ani_cli_sync.subtitles import resolve_stream_info
i = resolve_stream_info('Shingeki no Kyojin', 2)
print(i.subtitles[0]['src'])
" # then curl it with -e 'https://zokoanime.video/' and read the first cue
```

`offset = first_cue - audio_onset`, so a negative result means the subs are late and must be
pulled earlier. Fine-tune in mpv with `z` / `Z` (-0.1s / -1s) and `x` / `X` (+0.1s / +1s).

Automating the audio side is not currently practical: the HLS segments are served with a
`.ts.jpg` extension that ffmpeg rejects (`not in allowed_segment_extensions`), so
`silencedetect` cannot read the stream without a workaround.

**Verify before choosing a value.** Compare the first cue of each candidate track; if every
English track shares one first-cue timestamp they are all cut to the same timing, and there
is no better track to switch to:

```bash
python3 -c "
import sys; sys.path.insert(0,'src')
from ani_cli_sync.subtitles import resolve_stream_info
info = resolve_stream_info('Shingeki no Kyojin', 1)
for s in info.subtitles: print(s['label'], s['src'])
"
```

Note the scraper mislabels `lang` (Portuguese and Spanish tracks report `lang: 'en'`),
so select tracks by `label`, never by `lang` alone. There is frequently no Japanese
subtitle track to borrow timings from.

Fine-tune live in mpv with `z` / `Z` (-0.1s / -1s) and `x` / `X` (+0.1s / +1s).

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

## Repository topology
- canonical: GitHub (niStee/ani-cli-sync) — all changes land via PR to main
- mirror: Codeberg (codeberg.org/niStee/ani-cli-sync) — automated push mirror via
  .github/workflows/mirror-codeberg.yml; receives main + tags only
- never push directly to main; never push to Codeberg directly
- tags are immutable once pushed; never rewrite or delete a mirrored tag
- mirror repair path: re-run the workflow (workflow_dispatch), not local
  pushes
- operations runbook: niStee/network-infra → codeberg-github-migration.md
## Auto-merge policy

Auto-merge policy: see ai-infra `docs/AUTOMERGE.md` (<https://github.com/niStee/ai-infra/blob/main/docs/AUTOMERGE.md>); agents arm auto-merge only per its Tier-1 preconditions.

## CI Gates

| Gate | Required check | Enforces |
|---|---|---|
| `lint` job in `ci.yml` | `lint` (after it is added to required contexts) | ruff violation count equals `scripts/ruff_count_baseline.txt` |
| `test` / `matrix-test` | `test`, `matrix-test (3.10-3.13)` | unit suite on Python 3.10-3.13 |
| `scorecard`, `semgrep`, `gitleaks` | `Scorecard Security Analysis`, `scan` | supply-chain, SAST, secret scan |

### Ruff ratchet

`scripts/ruff_count_ratchet.py` gates on a **count**, not on ruff's exit code. The rules
that matter:

- The count must **equal** the baseline, not merely be below it. Failing only on an
  increase lets an unrecorded decrease leave slack that absorbs a later regression.
- The baseline may only fall, via `--update`. `--base-ref` fails a PR that widens the
  allowance in the same commit that adds the findings.
- Scope is **git-tracked** files (`git ls-files`), never a directory walk. A walk also
  visits untracked scratch, nested worktrees and vendored caches, reporting phantom
  regressions that do not exist in CI.
- Exit codes are distinct and never collapsed: `0` ok, `1` regression, `2` config error,
  `3` external failure (ruff could not run). A ratchet that fails open is worse than none.

Lower the baseline deliberately as findings are fixed:

```bash
python3 scripts/ruff_count_ratchet.py --update
```

### The local pre-commit hook is not this gate

The global git hook (ai-infra managed, `core.hooksPath`) runs `ruff check --quiet .`. Two
differences from the CI ratchet, both of which make it weaker:

- It is a **directory walk**, so untracked scratch and nested worktrees inflate it.
- It is guarded by `command -v ruff`, so with ruff absent it **silently passes**.

CI is the only enforced lint signal in this repository.

### Merge queue

`ci.yml`, `scorecard.yml`, `semgrep.yml` and `gitleaks.yml` all carry a `merge_group`
trigger. Without it, a merge queue forms, waits for a required check that never reports,
and holds the PR -- the single most common merge-queue failure.

Required-check names are matched by plain string, so renaming a job in a workflow while
the ruleset still points at the old name stalls the queue with no error. Keep the job
names `test`, `matrix-test`, `lint`, `Scorecard Security Analysis`, `scan` stable.
