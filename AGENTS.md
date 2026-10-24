# AGENTS.md — ani-cli-sync

> Parent: [~/Projects/AGENTS.md](../AGENTS.md) — multi-repo index, forge remotes, CI/CD matrix.

Automated AniList synchronization wrapper for [`ani-cli`](https://github.com/pystardust/ani-cli).

## Project Overview

- **Stack**: Python `>=3.10` (standard library only, zero external runtime dependencies)
- **Packaging**: Standard `pyproject.toml` with `hatchling` build backend
- **Primary Remote**: `git@github.com:niStee/ani-cli-sync.git` (GitHub public)
- **Mirror Remote**: `git@codeberg.org:niStee/ani-cli-sync.git` (Codeberg private mirror)
- **License**: Apache-2.0
- **Entry-points**: both `ani-cli-sync` and `ani-sync` are registered aliases for the same `main()`

## Key Architectural Principles

1. **Watchlist-First Context Resolution**: Matches anime titles against active `CURRENT` watchlist before falling back to global AniList search to prevent accidental clobbering of completed seasons.
2. **Multi-Season Scraping Offset Handling**: Bridges AniList discrete season numbering with scraper backend continuous numbering via strict 3-tier precedence:
   - **Tier 1 (Explicit Table)**: `_EPISODE_OFFSETS` static overrides (can specify custom search queries).
   - **Tier 2 (Computed Chain)**: `compute_prequel_offset()` traverses AniList's relation graph for preceding `TV`/`ONA` nodes, summing total episodes (with cycle protection, depth limit 10, and ambiguity checks).
   - **Tier 3 (Identity)**: Fallback 1-to-1 numbering.
3. **Completion, Boundary Enforcement & Sequel Rollover**: Auto-transitions status to `COMPLETED` when `ep >= total`. Queries AniList for released TV/ONA sequels with a clobber guard (resumes at `progress + 1` if already in list, prompts in interactive mode or seamlessly continues in `--autoplay`).
4. **Zero Third-Party Runtime Dependencies**: Implemented strictly with standard library (`urllib.request`, `json`, `argparse`, `subprocess`, `pathlib`, `concurrent.futures`).
5. **Automated Subtitle Fallback & Dual-Track Pipeline**: Inspects stream tracks (detecting forced tracks `< 50` cues vs. full dialogue). When target tracks are missing or signs-only, translates the base English track concurrently via local LiteLLM proxy (`minimax-m3.1-flash`, measured; override with `ANI_CLI_SYNC_LLM_MODEL`), producing synchronized German dialogue (`--sid=1`, bottom) and Traditional Chinese + Hanyu Pinyin (`--secondary-sid=2`, top) with persistent caching in `~/.cache/ani-cli/subtitles/`.

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
| Attack on Titan: The Final Season Part 1 | 1–16 | 1–16 | +0 |
| Attack on Titan: The Final Season Part 2 | 1–12 | 1–12 | +0 |

**Static Overrides**: To force a specific search string or override automatic chain resolution, append a tuple to `_EPISODE_OFFSETS` in `cli.py`. Standard multi-season shows are computed automatically.

**Entry order is load-bearing.** The table is scanned linearly and the first
fragment match wins, so a longer, more specific fragment must be listed
before a shorter one it contains. *Attack on Titan* is the concrete case: the
Part 1 fragment (`Attack on Titan Final Season`) is a substring of the Part 2
display title, so the Part 2 entries must precede the Part 1 entries. Every
entry also carries a season bound, so an out-of-range AniList episode is not
remapped into a neighbouring season.

## Subtitle Translation & Synchronization Architecture

See [ADR-001: Battletested Architecture for Subtitle Translation, Neural VAD Sync, and Playback Integrity](docs/adr/ADR-001-media-subtitle-translation-and-sync.md) for full architectural decisions and anti-pattern mitigations.

### Translation Model Cascade & Failover

Translation runs through the local LiteLLM proxy in `subtitles.py`, batched
(`batch_size=50`, 5 workers), with **no `max_tokens` and no reasoning control in the request**.
The default model must be non-reasoning: a reasoning model spends its budget before
emitting any content, and a 50-cue batch then does not finish inside the socket timeout.

A tiered model failover cascade (`DEFAULT_FALLBACK_MODELS = ("minimax-m3.1-flash", "gemini-3.1-flash-lite")`) protects against quota exhaustion:
- **HTTP 429 Quota Exhaustion**: Fast-fails immediately without retrying the exhausted model, advancing the episode translation to the next candidate model.
- **HTTP 502/503 Transient Errors**: Bounded retry with exponential backoff before escalating to the next candidate.
- **Override Precedence**: `ANI_CLI_SYNC_LLM_MODELS` (comma-separated list) > `ANI_CLI_SYNC_LLM_MODEL` (single override) > `DEFAULT_FALLBACK_MODELS`.

### Model Governance Contract (the rule that catches dead handles)

A model handle is only usable if it is **registered in ai-infra's
`home/dot_config/litellm/model-governance.json`**. The local LiteLLM gateway
validates every requested handle against that registry and **fails closed**
on an undeclared model, so an unregistered name never reaches a provider.

Consequences for this repo:

- Every member of `DEFAULT_FALLBACK_MODELS` MUST be registered in
  `model-governance.json` and reachable at `http://localhost:4000/v1`. A
  default member that the gateway rejects as unknown is a dead failover: the
  cascade walks into it only when it matters most (a quota event on the
  primary), burning a retry per dead entry before it can advance.
- The registry lives in **ai-infra**, not here. This repo consumes handles;
  it never edits the gateway config or the registry.
- **Before adding or changing a cascade member, verify it against the live
  gateway**, not against memory. Read-only probe, no generation:

  ```bash
  curl -s http://localhost:4000/v1/models | python3 -c "import json,sys; print([m['id'] for m in json.load(sys.stdin)['data']])"
  ```

  A handle that is absent from that list answers HTTP 400 and is unusable.
- The offline source of truth for "is this handle registered" is the vendored
  list in `src/ani_cli_sync/model_registry.py`, checked by
  `tests/test_model_registry.py`. The live probe above is the cross-check;
  the vendored list is what CI can assert without a running proxy.

**Lesson (2026-10-24):** the cascade shipped `gemini-2.5-flash` and
`llm-tower` after both were removed from the gateway on 2026-07-21 (ai-infra
commit `1f26d7a`). They answered HTTP 400 for months, unnoticed, because
the cascade is only exercised on a quota exhaustion. A guard test now pins
every default member against the vendored registry.

Measured 2026-10-24, one real 50-cue batch per model through the shipped code path
(against the local proxy):

| model | wall | note |
|---|---|---|
| `gemini-3.1-flash-lite` | 2.9s | secondary fallback; fastest; no same-model backup |
| `minimax-m3.1-flash` | 15.9s | primary default; Token Plan; same-model Go backup |
| `minimax-m3` | 7.6s | qualified but superseded by the M3.1 generation |
| `gemini-3.8-flash` | 9.2s | HTTP 429 quota exhausted on this workload |
| `qwen-3.8-flash` | 39.6s | correct output, too slow to sit in front of playback |
| `glm-5.3-flash` | 45.0s | exceeds the 45s per-batch socket timeout |
| `minimax-m2.7-highspeed` | 29.9s | Token Plan |
| `minimax-m2.7` | 31.8s | Token Plan |
| `deepseek-v4-flash` | 139.4s | reasoning model; stalls the episode |
| `gemini-3.6-flash` | - | HTTP 400 on this workload |

A cold `prepare_subtitles` for a 319-cue episode is **~34s**. Two failure modes are bounded on
purpose: `timeout=45s` per batch, `retries=1` (LiteLLM already retries internally), and
`translate_cues_llm` aborts without waiting for in-flight siblings. The earlier
`with ThreadPoolExecutor` return path shut the executor down with `wait=True`, so a known
failure still cost the slowest sibling's full budget -- that was a 180s stall.

The OpenCode Go `backup-minimax-*` deployments are `rpm: 2, max_parallel_requests: 1`, so a
failover onto them serialises 5 batch workers and is a latency trap for this workload; the
direct Token Plan deployments are the ones that matter. `llm-tower` is **not** a
translation endpoint: its inference ports do not answer, and the fleet manifest
deploys only `actions-runner` to that node, so no fleet health check maintains it.


## Commands & Testing

```bash
# Run unit test suite
PYTHONPATH=src python3 -m unittest discover -s tests

# Lint (the baseline is 0: the whole tracked repo must be ruff-clean)
ruff check .

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
ani-cli-sync watch --sub-sync=auto "Attack on Titan"   # Measure and apply the offset automatically
```

## Autoplay Stop Semantics

`--autoplay` advances to the next episode only on **positive evidence that the episode
played through**. Closing the player window must always stop the chain, never skip an episode.

| mpv exit | elapsed watch time | outcome |
|---|---|---|
| non-zero | any | **stop** - treated as the user closing the player |
| 0 | `>= 85%` of effective duration (`duration - skip_seconds`) when skips present | advance |
| 0 | `>= 80%` of probed duration when skips absent | advance |
| 0 | otherwise (user closed early) | **stop** |
| 0 | duration unknown | advance only at `>= 1150s - skip_seconds` |

The duration is summed from the HLS media playlist (`#EXTINF`). When automated intro/outro
skips occur (`ani-skip`), `skip_seconds` is subtracted so an episode with skipped OP (~90s)
and ED (~90s) is not falsely classified as an early quit. Without skip metadata, an 80%
baseline (matching PlexTraktSync and Trakt standards) allows manual skips without stalling.
When probing fails or in the `no_sub_fallback` path, the 1150s fallback (~19.2 minutes) applies.

**Why the previous logic was wrong.** It advanced on any non-zero exit (so closing mpv
skipped the episode) and treated any zero exit past a flat `600s` threshold as "finished",
which advanced even when the user had closed the window early. Both are corrected by
`_should_advance()` in `cli.py`, covered by `tests/test_autoplay_stop.py`.

## Subtitle Sync Offset (`--sub-delay`)

Some releases ship **English subtitles timed to the English dub** while the audio track is
**Japanese original**. The subs then read as drifting even though mpv reports `A-V: 0.000`
(mpv only tracks demuxer PTS, not dialogue alignment).

`--sub-delay=<seconds>` shifts subtitle presentation. **Negative pulls subs earlier.**

Defaults to `0` (no flag emitted). Override with `ANI_CLI_SYNC_SUB_DELAY`.

### The offset is per-episode, not per-show

Measured and playback-verified on Attack on Titan S1, same release, same provider:

| Episode | First sub cue | JP audio onset | Offset | Verified |
|---|---|---|---|---|
| Ep 1 | `00:00:41.870` | ~38s | `-3.8` | yes |
| Ep 2 | `00:00:21.540` | ~22s | `0` (no flag) | yes |

Ep 2's own subtitle file is already aligned to the Japanese audio, so it needs no shift at
all. Do not assume a show that needed a shift on one episode needs it on the next.

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

### Automating the measurement: `--sub-sync=auto`

`--sub-sync=auto` measures the offset per episode and applies it, for the case where you do
not want to hand-measure every release. Default is `off`; override with
`ANI_CLI_SYNC_SUB_SYNC=auto`. An explicit non-zero `--sub-delay` always wins and suppresses
measurement entirely.

```bash
uv tool install "ani-cli-sync[subsync]"   # optional extra, pulls torch via silero-vad
ani-cli-sync watch --sub-sync=auto "Attack on Titan"
```

It is **off by default and reports rather than guesses**: if the VAD finds no speech, the
subtitle file has no first cue, or the resulting offset is implausible (>60s), it prints the
reason and leaves timing unchanged. A missing extra is likewise a no-op, not an error.

**How it measures.** `offset = first_speech_onset - first_cue`, using the primary subtitle
track (`sub_plan.sub_files[0]`, same track selection as `--sub-delay`).

Measured per episode, inside the watch loop. The offset is a property of one subtitle file,
so the result is held in a per-episode local and never written back into `--sub-delay`:
doing so would make the next iteration treat it as a manual value, skip its measurement,
and replay the previous episode's shift on it. AoT ep1 wants `-3.37` and ep2 wants `+0.25`;
carrying ep1's value across mis-times ep2 by seconds.

**Requires the subtitles path.** Measurement runs inside the subtitle-fallback branch, so
`--dub` and `--no-sub-fallback` skip it silently and leave timing unchanged.

**Measured against the real VAD** (validated 2026-10-05, AoT S1 ep6, silero-vad 6.2.3):
one measurement takes ~9s, and the pipeline decodes, runs the VAD and compares cues as
documented. Two real-world limits were found that way:

1. **The subtitle CDN requires the stream's Referer.** hls.dramahot.top answers `403` to a
   subtitle URL carrying only a User-Agent and `200` with `Referer: <stream referrer>`.
   mpv already sends it (`--referrer`), which is why playback shows subtitles while a bare
   fetch does not. `measure_offset` forwards `stream_info.referrer` to `_first_cue`; without
   it every episode reports "no cues in the subtitle file". `subtitles.fetch_vtt_text` has
   the same omission and is tracked separately.
2. **An opening-theme lyric as the first cue makes the measurement meaningless.** On ep6 the
   first eight cues are italicised OP lyrics (`intro_skip` is 15-90s); the first real dialogue
   cue is at 108.41s while the first cue is at 31.66s. Against a first speech onset of
   116.48s that yields `+84.8s`, which `MAX_PLAUSIBLE_OFFSET` rejects as "likely a different
   cut" -- correctly, since shifting by 84s would be catastrophic. The gate is what makes the
   feature safe, but it also means **the measurement only applies when the first subtitle is
   dialogue, not a lyric.** Skipping cues inside the known `intro_skip` window would widen
   coverage, at the cost of accuracy: the first post-OP cue often precedes the first spoken
   line by seconds of visual cold open, so the offset gets less trustworthy exactly where it
   gets more applicable. Not done deliberately; tracked as a follow-up.

**Why a neural VAD and not `silencedetect`.** Anime openings carry a loud music bed, so
energy-based silence detection locks onto the music rather than the narration. Silero was
measured at 101x realtime (300s of audio in 2.97s) and matched the hand-measured values:
AoT ep1 `-3.37` vs `-3.8` verified (error 0.43), ep2 `+0.25` vs `0` verified (error 0.25).
Whole-file correlation tools (`ffsubsync`, WebRTC-style alignment) were rejected: a flat
correlation plateau over anime dialogue produces boundary-saturating, unusable results.

**Reading the HLS stream.** Segments are served with a `.ts.jpg` extension that ffmpeg's
format probe rejects. `-extension_picky 0` is required; `-allowed_segment_extensions ALL`
alone is **not** sufficient, because it does not bypass the probe.

**Not done:** intro/OP-skip detection is deliberately separate and not attempted here.

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

## Spec-driven development (pilot)

Behavior changes are specified before they are built, with OpenSpec (pinned in
`mise.toml`; run `openspec` from this repository). Start with the propose
workflow (`/opsx:propose` in Claude Code, `$openspec-propose` in Codex,
`/opsx-propose` in OpenCode), get the proposal reviewed, then apply it.
`openspec/specs/` is the current, agreed behavior; `openspec/changes/` holds
proposals in flight. The project rules every proposal must follow (tests from
scenarios, positive/negative pairs with sensitivity probes, when a proposal is
needed, ADRs) live in `openspec/config.yaml`. Plans in issue comments are not the
spec: if an issue and `openspec/specs/` disagree, the spec wins until a reviewed
change says otherwise.

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

### The local pre-commit hook is stricter than this gate

The global git hook (ai-infra managed, `core.hooksPath`) lints the **staged snapshot** of
each staged Python file, per file:

```bash
git show ":$p" | ruff check --quiet --stdin-filename="$p" -
```

There is **no baseline allowance**. A staged file that carries pre-existing findings
blocks the commit even when the change under review adds none. So the hook is stricter
than the CI ratchet, which only compares a repo-wide count against the baseline.

Consequences:

- A commit that stages a file with existing findings needs those findings cleared
  (or the baseline lowered via `--update`) first. Do not reach for `--no-verify`:
  CI's ratchet is the enforced signal, and bypassing the hook locally hides a real
  gate instead of resolving it.
- The hook fails loudly when `ruff` is absent (it requires the staged Python set to be
  lintable). The CI ratchet, by contrast, exits `3` (external failure) rather than
  silently passing when ruff cannot run.
- The pre-push hook's Python block is guarded by
  `ls pyproject.toml setup.cfg requirements*.txt`, and `ls` exits non-zero when **any**
  named file is missing. This repository has `pyproject.toml` but neither `setup.cfg` nor
  `requirements*.txt`, so the whole Python block (ruff + pytest) is skipped at push
  time. Do not rely on that: it is an accident of the file layout, not a policy.

CI is the only *enforced* lint signal in this repository, but the local hook is a real
gate in practice. Keep the working tree ruff-clean so both pass.

### Merge queue

`ci.yml`, `scorecard.yml`, `semgrep.yml` and `gitleaks.yml` all carry a `merge_group`
trigger. Without it, a merge queue forms, waits for a required check that never reports,
and holds the PR -- the single most common merge-queue failure.

Required-check names are matched by plain string, so renaming a job in a workflow while
the ruleset still points at the old name stalls the queue with no error. Keep the job
names `test`, `matrix-test`, `lint`, `Scorecard Security Analysis`, `scan` stable.
