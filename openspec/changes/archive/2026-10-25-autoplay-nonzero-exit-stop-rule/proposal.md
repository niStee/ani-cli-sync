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

The requirement is written in terms of what the user observes: the chain
stops, progress is preserved, and the reported cause is the abnormal exit.
It does not prescribe the order in which thresholds are computed, because that
order is not observable. The stop reason is, though -- it is printed as
"Playback stopped (..., {why})" -- and it distinguishes an abnormal session
from one the user ended early.

This is a **specification gap, not a code defect**: the code is correct and
the behaviour is already covered by tests.

## What Changes

- One requirement is **added** to the `autoplay-completion-threshold`
  capability: a non-zero player exit stops the chain regardless of elapsed
  time or duration knowledge, and the abnormal exit is reported as the cause
  of the stop.
- Three scenarios are added to it: one with a known duration, one with an
  unknown duration, and one after automated intro/outro skips.

No behavioural change. The code already implements this rule.

## Why this is a proposal and not just a spec edit

`openspec/config.yaml` requires a proposal for behaviour changes. This is
neither a behaviour change nor a bug fix: it specifies behaviour that exists,
was shipped in PR #100, and was never written down. The proposal records that
intent, so the archived change explains why the requirement exists rather than
leaving a bare requirement with no history.

## Out of Scope

- **Any change to the exit-code check itself.** It stays first, it keeps its
  current message, and its position relative to the duration logic is
  unchanged. The requirement is stated in terms of the observable outcome
  (the stop reason), not the order in which thresholds are computed.
- **The duration thresholds.** The 70% skip-aware ratio, the 80% no-skip
  baseline and the 1150s unknown-duration fallback are specified already and
  are unchanged.
- **The four capability specs that were never shipped** (`anilist-sync`,
  `cli`, `matching`, `sub-sync`), tracked separately in #104.

## Related

- `openspec/specs/autoplay-completion-threshold/` - the capability extended here.
- niStee/ani-cli-sync#99 - the original autoplay change (PR #100).
- niStee/ani-cli-sync#104 - the tracking issue for the remaining specs.
