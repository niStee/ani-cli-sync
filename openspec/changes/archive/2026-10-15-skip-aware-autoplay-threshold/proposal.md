# Proposal: Skip-Aware Autoplay Completion Threshold

## Why

In `ani-cli-sync`, the completion guard `_should_advance()` requires wall-clock playback elapsed time to reach 90% of total stream duration (`duration * 0.90`). When automated intro/outro skipping (`ani-skip`) is active, skipping the opening (~90s) and ending (~90s) removes approximately 12.5% to 15% of a 24-minute episode's runtime. A viewer watching 100% of the narrative dialogue has an elapsed time of ~87.5%–89.4%, falling just short of the rigid 90% threshold (e.g. Attack on Titan Episode 18 missed by 9 seconds), which falsely classifies the session as an early quit and halts autoplay.

## What Changes

- Calculate total scheduled skip time (`skip_seconds`) from `stream_info.intro_skip` and `stream_info.outro_skip`.
- Base the playback completion threshold on effective narrative duration (`duration - skip_seconds`) when skip metadata is present.
- Lower the general fallback watched ratio to 80% (matching PlexTraktSync and Trakt standards) for episodes without explicit skip metadata or with manual skips.
- Lower the unknown-duration fallback from 1400.0s to 1150.0s (~19.2 minutes, 80% of a 24-minute episode) so episodes with skipped OP/ED advance cleanly even when playlist duration probing fails.

### Out of Scope

- Modifying `mpv` player binaries or configuration.
- Changing AniList authentication or GraphQL mutations.

## Capabilities

### New Capabilities
- `autoplay-completion-threshold`: Evaluates media playback completion using effective duration adjusted for skipped intros/outros and industry-standard completion ratios (80%–85%) to prevent false-negative early quit stops.

### Modified Capabilities
<!-- None: baseline specs are introduced through changes in this repository. -->

## Impact

- `src/ani_cli_sync/cli.py`: Update `_should_advance` signature and implementation; update call site in `cmd_watch`.
- `tests/test_autoplay_stop.py`: Update tests to verify skip-aware advancement, 80% baseline, and conservative early-stop rejection.
