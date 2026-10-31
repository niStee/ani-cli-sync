# Proposal

## Why

Issue [#104](https://github.com/niStee/ani-cli-sync/issues/104) identifies four
implemented capabilities without canonical requirements. A source-grounded
baseline lets later changes distinguish existing behavior from intended changes.

## What Changes

- Add baseline requirements for authentication/list state, manual progress,
  verified-playback updates, and the supported sequel rollover cases.
- Describe the implemented command surface and distinct title-selection paths.
- Describe opt-in, episode-local automatic subtitle timing and its refusals.
- Provide a source/test traceability inventory and explicitly separate defects,
  documentation conflicts, and uncovered edge cases from normative requirements.
- Preserve existing completion, subtitle selection, and offset specifications.

## Capabilities

### New Capabilities

- `anilist-sync`: authenticated watchlist state, explicit progress correction,
  post-playback status updates, and supported sequel transitions.
- `cli`: explicit commands, implicit option-only watch invocation, selection,
  authentication fallback, and supported subtitle options.
- `matching`: current-watchlist title resolution and provider-cut selection.
- `sub-sync`: primary-track offset measurement, manual precedence, confidence
  bounds, failure handling, and per-episode application.

### Modified Capabilities

None. Existing threshold and subtitle-track requirements remain authoritative.

## Impact

Planning artifacts only. No runtime, dependencies, credentials, network services,
or AniList mutations change. A later reviewed baseline-promotion pass will add
canonical specs and any missing characterization tests without changing code.

Out of scope: Netflix reliability (#90), translation documentation (#89), duration
fallback (#60), new matching heuristics, progress hardening, CLI error redesign,
and subtitle dialogue/lyric detection. No abandoned specification is copied.
Known unsafe behavior is not endorsed by omission; the design records exclusions
and follow-up gates explicitly.
