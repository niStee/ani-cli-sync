# Proposal: Specify the Non-Zero Exit Stop Rule

Serves: niStee/ani-cli-sync#104

## Why

The `autoplay-completion-threshold` capability spec describes **when** a
playback session counts as watched: by duration ratio, with a skip-aware
regime, a no-skip regime, and a fallback for unknown duration.

It says nothing about **whether the player ended normally**. All six of its
scenarios state "with return code 0" or a duration shortfall, and none of
its three requirements mentions a non-zero exit.

The implementation checks the exit code **first**, before any duration
reasoning (`if returncode != 0: return False, ...` in `_should_advance()`).
That check is what makes closing the player window stop the chain. Without it
in the spec, a reader would conclude that a long playback with a non-zero exit
advances, and a future change could remove or reorder the check without a spec
conflict -- unlike the ratio thresholds, which would break the spec.

This is a **specification gap, not a code defect**: the code is correct and
the behaviour is already covered by tests.

## What Changes

- One requirement is **added** to the `autoplay-completion-threshold`
  capability: a non-zero player exit stops the chain regardless of elapsed
  time or duration knowledge.
- Two scenarios are added to it: one with a known duration, one with an
  unknown duration.

No behavioural change. The code already implements this rule and the tests
already assert it.

## Why this is a proposal and not just a spec edit

`openspec/config.yaml` requires a proposal for behaviour changes and a
regression test for a bug fix that restores already-specified behaviour. This
is neither: it specifies behaviour that exists, was shipped in PR #100, and
was never written down. The proposal records that intent, so the archived
change explains why the requirement exists rather than leaving a bare
requirement with no history.

## Out of Scope

- **Any change to the exit-code check itself.** It stays first, it keeps its
  current message, and its position relative to the duration logic is
  unchanged.
- **The duration thresholds.** The 70% skip-aware ratio, the 80% no-skip
  baseline and the 1150s unknown-duration fallback are specified already and
  are unchanged.
- **A new test.** The behaviour is already covered:
  `test_nonzero_exit_never_advances` and
  `test_unknown_duration_nonzero_exit_still_stops` in
  `tests/test_autoplay_stop.py`. Writing a third test for behaviour that
  already has two asserting tests would be noise, and `openspec/config.yaml`
  says "A spec never replaces tests" -- not the reverse.
- **The four capability specs that were never shipped** (`anilist-sync`,
  `cli`, `matching`, `sub-sync`). Those are tracked separately in #104 and
  describe behaviour the code does not implement.

## Related

- `openspec/specs/autoplay-completion-threshold/` - the capability this
  change extends.
- niStee/ani-cli-sync#99 - the original autoplay change (PR #100), which
  shipped the 70% ratio and left this requirement unwritten.
- niStee/ani-cli-sync#104 - the tracking issue for the remaining capability
  specs.
