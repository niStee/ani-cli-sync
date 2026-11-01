# Design

## Context

Pinned main `87314dc54de181b928a49c2711f3783efca5c532` sums HLS `#EXTINF` seconds in `_probe_duration` (`src/ani_cli_sync/cli.py:686-717`), then calls `_should_advance` after a zero player exit (`:1032-1036`). If HLS duration is `None`, `_should_advance` uses 1150 seconds minus known skips (`:621-683`). The watchlist and global-search queries request `episodes` but not `duration`; `find_sequel` likewise omits it. The selected media ID is parsed once, then replaced on sequel rollover (`:882-889`, `:1102-1108`).

Issue #60 historically mentioned 1400 seconds and worried that sequel duration might require another query. Both are stale: pinned main uses 1150 seconds, and the existing sequel relation query can carry `duration` in its node. No VAD work remains in this package; the issue records real validation on 2026-10-05.

## Goals / Non-Goals

**Goals:**
- Better duration evidence on paths without `stream_info`, with deterministic precedence and no unsafe zero threshold.
- Exact selected-media and sequel metadata propagation using existing requests.
- Preserve every existing stop/ratio guarantee.

**Non-Goals:**
- A second media query per episode, live probing, a new duration source, HLS parser rewrite, VAD/subtitle/dependency work, or broad watch-loop refactoring.

## Decisions

### Decision 1: Resolve duration in strict evidence order

Use the first usable value only:

1. A positive HLS total returned by the existing probe.
2. `Media.duration` when it is a positive integer, excluding booleans, converted once as `minutes * 60` seconds.
3. The unchanged 1150-second constant.

HLS remains authoritative even when AniList metadata is present and different: AniList describes a general episode length, not the selected release. Invalid HLS results and absent `stream_info` count as unknown and advance to metadata; invalid metadata advances to the constant. No zero/negative/non-finite value may produce an immediate-completion threshold.

The existing 70% skip-aware and 80% no-skip calculations then apply to whichever duration won. Known skips are subtracted under the existing rules. The constant remains `max(0, 1150 - skip_seconds)` and is not multiplied by a ratio. This preserves current behavior exactly at the last tier.

**Alternative:** Always prefer AniList because it avoids a playlist request. Rejected because release-specific HLS timing is stronger evidence and the probe already exists.

### Decision 2: Carry metadata with the existing selected-media context

Add `duration` to the existing `Media` selection in `get_watching_list` and `search_anime`. Keep it out of the display/fzf text: it is metadata, not user identity, and the existing line format remains stable. During selection, retain a per-run `media_duration_minutes` derived from the selected entry/media object and the selected media ID.

For a watchlist match, read that entry's `media.duration`; for the global-search fallback, read the returned media's `duration`; for fzf/manual selection, retain the mapping from the original selected entry rather than attempting a title lookup. This avoids a new request and preserves selected-media identity.

**Alternative:** Append duration to `selected_line` delimiters. Rejected because it unnecessarily changes a parsing protocol used throughout the watch loop and tests.

### Decision 3: Replace, never inherit, on sequel rollover

Add `duration` to `find_sequel`'s existing relation node query. When rollover assigns `media_id = sequel_id`, also replace the duration context with `sequel_node.duration`. A missing/invalid sequel value becomes unknown; the previous season's minutes must not leak into the sequel. The existing relation request therefore supplies sequel metadata with no additional completion-time query.

Each zero-exit iteration resolves HLS first and otherwise uses the current media's metadata. Do not cache a resolved seconds value across episodes: HLS is per episode, and media duration context changes at rollover.

### Decision 4: Keep safety gates before duration work

A non-zero player exit still stops immediately, reports the exit, preserves progress, and skips HLS probing. No AniList duration fallback can override it. Metadata is carried from existing responses rather than fetched after every player exit, so no per-episode AniList call is introduced on either exit path.

Malformed metadata is not a fatal playback error; it falls through to the conservative constant. Do not change the existing HLS 15-second fetch, its failure behavior, or the no-sub-fallback command path.

## Test and sensitivity matrix (synthetic/hermetic only)

GLM derives focused `unittest` cases from the delta and extends existing `tests/test_autoplay_stop.py`, `tests/test_subdelay_auto.py`, and/or `tests/test_cli.py` only where their seams already exist. Every guard pair has a recorded mutation probe: weaken the stated guard, see focused red, restore, see green with implementation.

| ID | Positive evidence | Negative guard / probe |
|---|---|---|
| D01 | HLS 1463s with metadata 24 minutes uses HLS thresholds | Override HLS with metadata; threshold/advance case must fail |
| D02 | Unknown HLS + 24 minutes gives 1440s base; 80% boundary advances | Fall through to 1150s; 1150s elapsed must not be accepted as 80% of 1440s |
| D03 | Unknown HLS + 24 minutes + 180s skips uses 70% of 1260s | Skip-aware ratio or skip subtraction removed; boundary case fails |
| D04 | Valid 1-minute metadata converts to 60 seconds | Treat minutes as seconds; exact threshold assertion fails |
| D05 | Null/missing metadata uses 1150 minus skips | Missing treated as zero or exception escapes; fallback pair fails |
| D06 | Zero, negative, boolean, float, string, NaN/infinity metadata each use 1150 | Generic truthy/numeric coercion accepted; each invalid value must not lower/change threshold |
| D07 | HLS zero/None and valid metadata use metadata | HLS failure made fatal or metadata skipped; fallback pair fails |
| D08 | Non-zero exit with HLS/metadata/constant stops and reports exit | Exit guard bypassed; full-elapsed case fails and no probe/update occurs |
| D09 | Existing HLS/no-skip 80%, HLS/skip 70%, and unknown constant cases remain green | Any ratio/fallback edit detected by existing plus boundary tests |
| D10 | Watchlist selected media 24 minutes is used on no-stream path | Duration omitted from existing query or lost during selection; command-level threshold fails |
| D11 | Global-search selected media supplies its duration | Search path drops metadata; no extra query is permitted to hide it |
| D12 | Fzf/manual selection uses the originally selected entry's duration | Last-list-entry or title-derived value substituted; differing entries expose it |
| D13 | Sequel duration 30 minutes replaces prior 24 minutes after rollover | Previous season retained; second playback threshold/call arguments fail |
| D14 | Sequel null/invalid duration falls to constant, not previous media | Missing field inherits old value; differing previous metadata exposes it |
| D15 | Existing watchlist/search/sequel query responses include `duration` with no new request | Count API calls per episode; an extra media query fails the test |
| D16 | Non-zero player exit performs no HLS probe and no progress update | Existing hermetic test remains; metadata cannot cause a new fetch/update |

D06's non-finite values are defensive synthetic inputs even though valid GraphQL `Int` cannot contain them; they protect the public helper boundary without asserting the remote API emits invalid JSON. D10-D15 may use mocks at existing API boundaries but must assert observable threshold/update/probe behavior, not merely internal assignments.

At minimum record sensitivity probes for HLS precedence, valid-minute conversion, invalid-value rejection, ratio preservation, non-zero stop, selected-entry propagation, sequel replacement, and no-extra-call count. Never perform a live VAD, player, CDN, AniList, or credential call.

## GLM-5.3 test brief - after GPT spec approval

Translate the modified requirement and D01-D16 into positive/negative tests with deterministic clocks and mocked HLS/AniList/player boundaries. First demonstrate intended red on pinned implementation where behavior is new, and preserve existing green characterization for unchanged rules. Record each sensitivity probe and restore the implementation after it. Do not change canonical specs, write production code, install extras, or use live services. Freeze tests and probe evidence for GPT review; MiniMax remains blocked until that review.

## MiniMax-M3.1-Flash implementation brief - after GPT test review

Make the smallest change in `cli.py`: request `duration` in the three existing query shapes, retain selected-media metadata without changing display lines, normalize valid positive integer minutes, resolve HLS -> metadata -> 1150 per zero-exit iteration, and replace metadata on sequel rollover. Preserve frozen tests byte-for-byte unless GPT authorizes a correction. Do not add a per-episode request, new dependency, broad helper rewrite, or VAD work. Update the AGENTS autoplay fallback paragraph and any directly affected code comments to describe all three tiers without changing unrelated docs. Run focused tests, then `PYTHONPATH=src python3 -m unittest discover -s tests`, `ruff check .`, and `python3 scripts/ruff_count_ratchet.py`; report actual results and any pre-existing failure separately.

## Practice review (sources read 2026-10-30)

- [AniList `Media` reference, current docs.anilist.co](https://docs.anilist.co/reference/object/media), live page without a shown publication date: **confirmed** nullable `duration: Int` is the general length of each anime episode in minutes; it is not release-specific evidence.
- [AniList `Media` GitBook reference](https://anilist.gitbook.io/anilist-apiv2-docs/docs/reference/object/media.md), live page without a shown publication date: **confirmed** the same nullable integer/unit semantics in a second official rendering.
- [RFC 8216, August 2017, sections 4.1 and 4.3.2.1](https://datatracker.ietf.org/doc/html/rfc8216#section-4.3.2.1): **confirmed** a media playlist's duration is the sum of segment durations and `EXTINF` values are seconds; adopt HLS as the primary existing source.
- [Issue #60 and its 2026-10-05 updates](https://github.com/niStee/ani-cli-sync/issues/60), read 2026-10-30: **needs-precision** on historical 1400s and extra-query concern; pinned source shows 1150s and an existing sequel query, while VAD validation is recorded complete.

**Reuse check: adopt.** Reuse existing HLS probing, AniList queries, selection context, `_should_advance`, and unittest seams. No duration library, media probe dependency, metadata service, or extra GraphQL request is needed.

## Risks / Trade-offs

- **Risk:** General AniList minutes differ from a special release. **Mitigation:** HLS always wins; metadata is only fallback evidence.
- **Risk:** A zero/malformed value allows instant advancement. **Mitigation:** positive-integer validation and D06/D14 probes.
- **Risk:** Prior-season duration leaks after rollover. **Mitigation:** replace both ID and duration together and test different values.
- **Risk:** Hidden per-episode network regression. **Mitigation:** only extend existing queries and assert request counts.
- **Risk:** Existing watch tests assume missing fields. **Mitigation:** missing/null remains supported and uses the unchanged constant.

## Migration Plan

No user action, data migration, config change, or new dependency. Existing valid HLS behavior and constant-only responses retain their thresholds; missing metadata is backward compatible. No live migration validation is part of this package.

## Traceability

- Precedence/conversion/invalid metadata: modified requirement scenarios 1-7; D01-D09; tasks 1-2.
- Selection/sequel/no-extra-request: scenarios 8-11; D10-D16; tasks 1-2.
- Non-zero/ratios: retained canonical requirements and modified abnormal-exit scenario; D08-D09; tasks 1-3.
- Documentation and final checks: proposal Impact; tasks 2.3-3.2.
