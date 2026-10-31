# Proposal

## Why

[Issue #88](https://github.com/niStee/ani-cli-sync/issues/88) calls for user-facing Netflix import documentation. The current README gives only one command and does not explain the official export, privacy, mapping evidence, preview/apply safety, failure exits, or repeat runs. Issue #90 is defining that behavior and will supply the minimum CLI help and README text in its behavioral change.

## What Changes

- Plan an expanded `docs/netflix-viewing-history-import.md` guide plus one relative README link after #90's behavior is accepted.
- Explain the official per-profile Viewing activity CSV export and distinguish it from the wider personal-information archive.
- Document local-history privacy, preview versus explicit apply, conservative mapping evidence and unresolved results, status safety, exit codes 0/1/2, partial results, and idempotent reruns.
- Include only examples generated from the selected #90 semantics; retain clearly marked P1/P2 and S1/S2 branches in this plan until that dependency is resolved.
- Keep #90 responsible for minimum command help and README documentation, avoiding a second competing behavioral contract.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is documentation-only and sets `skip_specs: true`.

## Impact

The later documentation change touches only the new guide and a minimal README link. No importer code, tests, canonical specs, real exports, credentials, or live service actions are part of this package.

## Out of scope

Changing import semantics, supporting the wider Netflix archive, adding mapping overrides, publishing sample real history, and duplicating #90's minimum documentation. GPT orchestrator reviews the guide against the approved #90 behavior; final human acceptance remains required. No separate GLM test stage is needed.
