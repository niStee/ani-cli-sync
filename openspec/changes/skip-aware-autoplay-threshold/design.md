# Design: Skip-Aware Autoplay Completion Threshold

## Context

See `proposal.md` for motivation. In `src/ani_cli_sync/cli.py`, `_should_advance(returncode, elapsed, duration)` decides whether to advance to the next episode during autoplay runs. When intro/outro skips occur, elapsed wall-clock playback time falls below `duration * 0.90` despite complete story consumption. `StreamInfo` in `src/ani_cli_sync/subtitles.py` already carries `intro_skip` and `outro_skip` tuples `(start, end)`.

## Goals / Non-Goals

**Goals:**
- Eliminate false-negative early quit detections when intro/outro segments are skipped via `ani-skip`.
- Support manual skips via an 80% fallback ratio matching industry consensus (PlexTraktSync, Trakt).
- Retain strict rejection of intentional early stops (<80% or <15 minutes).
- Zero external runtime dependencies (standard library only).

**Non-Goals:**
- Real-time MPV IPC socket monitoring or Lua daemon scripts.
- Modifying `ani-cli` upstream shell script.

## Decisions

### Decision 1: Skip-Aware Effective Duration Calculation
- **Choice**: When `stream_info` is available, compute `skip_seconds = max(0.0, intro_end - intro_start) + max(0.0, outro_end - outro_start)`. Compute `effective_duration = max(0.0, duration - skip_seconds)`. When `skip_seconds > 0`, calculate `threshold = effective_duration * 0.85`.
- **Alternatives considered**:
  - *Keep single flat percentage (e.g. 80%)*: While 80% works for standard 180s skips, an anime with a long 3-minute recap plus OP and ED (300s total skip) could drop to 79%, failing a flat 80% check. Calculating effective narrative duration prevents false stops regardless of skip length.

### Decision 2: 80% Baseline for Unknown Skip Metadata
- **Choice**: When `skip_seconds == 0` (e.g. native `ani-cli` fallback or streams lacking skip metadata), use `threshold = duration * 0.80`.
- **Alternatives considered**:
  - *Retain 90%*: Fails whenever user skips OP/ED manually or when provider metadata is incomplete.
  - *Lower to 70%*: Too permissive; would mistake quitting halfway through the climax for finishing the episode.

### Decision 3: Update Fallback from 1400.0s to 1150.0s
- **Choice**: When HLS media playlist duration cannot be probed (`duration is None`), use `_FALLBACK_COMPLETE_SECONDS = 1150.0` (~19.2 minutes), minus any known `skip_seconds`.
- **Alternatives considered**:
  - *Keep 1400.0s*: 1400s is 23m 20s. A 24-minute episode with OP/ED skipped plays for ~21 minutes (1260s–1308s) and would always fail the fallback check.

### Decision 4: Pure Timeline Evaluation Over MPV IPC Sockets
- **Choice**: Evaluate returncode and elapsed wall-clock time vs effective duration in Python.
- **Alternatives considered**:
  - *MPV IPC socket querying (`/tmp/mpv-socket`)*: Rejected because `input-ipc-server` is not universal across fleet hosts, causes socket collisions across concurrent processes, is not available on native `ani-cli` fallback, and suffers from race conditions during process termination.

## Risks / Trade-offs

- **[Risk]** User stops watching at 81% (around minute 19.5 of a 24-minute episode) and it marks as watched.
  - *Mitigation*: In episodic anime, minute 19.5 is already past the narrative climax and into the ending credits or preview. This matches the behavior of PlexTraktSync, Trakt, Netflix, and Crunchyroll.
- **[Risk]** `skip_seconds` exceeds total duration.
  - *Mitigation*: Guarded by `max(0.0, duration - skip_seconds)` and fallback floor.
