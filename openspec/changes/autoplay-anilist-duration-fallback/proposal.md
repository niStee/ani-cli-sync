# Proposal

## Why

[Issue #60](https://github.com/niStee/ani-cli-sync/issues/60) leaves one open item: when no stream duration is available, autoplay uses one flat threshold even though AniList already supplies a general episode duration in minutes. This particularly affects `--dub` and `--no-sub-fallback`, where stream metadata is unavailable. The real-VAD validation item is complete and is not part of this change.

## What Changes

- Establish explicit duration precedence: positive HLS playlist duration first, valid positive integer AniList `Media.duration * 60` second, and the current 1150 seconds minus known skips last.
- Carry the selected media's duration through all selection routes and replace it with the sequel's duration during rollover.
- Add `duration` to existing AniList watchlist, global-search, and sequel queries, without an additional per-episode metadata request.
- Reject null, boolean, non-integer, zero, negative, and non-finite duration metadata instead of allowing an automatic threshold of zero.
- Preserve the 70% skip-aware and 80% no-skip ratios and the unconditional non-zero-exit stop.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `autoplay-completion-threshold`: unknown-HLS playback can use AniList's general per-episode duration before the constant last resort.

## Impact

The later behavioral change is bounded to `src/ani_cli_sync/cli.py`, focused autoplay/watch/sequel tests, and the existing autoplay documentation statements that describe duration fallback. No dependency or API-call-per-episode is added.

## Out of scope

VAD validation or redesign, subtitle changes, ffprobe/player-duration APIs, changing either completion ratio, changing abnormal-exit semantics, retries, live playback, and live AniList calls. Under the pilot, GPT orchestrator spec/test reviews gate GLM-5.3 tests and MiniMax-M3.1-Flash implementation; final human acceptance remains required.
