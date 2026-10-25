# Proposal: Skip-Aware Autoplay Completion Ratio

Serves: niStee/ani-cli-sync#99

## Why

`_should_advance()` decides whether autoplay may continue to the next episode.
It applies two different completion ratios:

- With automated skip metadata (ani-skip jumping the OP and ED): 85% of the
  effective duration, where effective duration is `duration - skip_seconds`.
- Without skip metadata: 80% of the total duration.

The 85% skip-aware ratio is too high for releases where the skip metadata does
not cover the whole non-narrative runtime. Real case, Attack on Titan S1
episode 15: 1463s duration, 176s skipped, 1028s elapsed.

```
effective duration = 1463 - 176 = 1287s
threshold at 85%   = 1094s
elapsed             = 1028s  ->  below the threshold, autoplay stopped
```

The episode had played through its narrative content. Autoplay stopped anyway,
so the chain did not continue to the next episode and watch progress did not
advance. The 15% gap between 70% and 85% of the effective duration is exactly
the band where recaps, credits and post-ED segments live on affected
releases.

## What Changes

- The skip-aware completion ratio drops from 85% to 70% of the effective
  duration.
- The no-skip baseline stays at 80% of the total duration. It is a different
  regime (the user may have skipped manually, so a stricter floor applies) and
  the reported failure is not in it.

Lowering the skip-aware ratio only relaxes the threshold in the case where the
tracker already knows that non-narrative content was skipped. The early-quit
protection that matters - the user closing the window - still holds: the
existing test at 600s of a 1463s episode with 177s skipped must continue to
stop, and it does.

## Out of Scope

- The no-skip 80% baseline. Unchanged deliberately.
- The unknown-duration fallback (1150s minus skips). Unchanged: it does not
  use a ratio at all.
- The 300-second absolute floor on the threshold. It does not exist in the
  current implementation and is not introduced here.
- The early-quit stop semantics. Unchanged.

## Related

- `openspec/specs/autoplay-completion-threshold/` - the autoplay completion
  threshold capability.
- Local commit `22f2ebc`, the origin of this change.
