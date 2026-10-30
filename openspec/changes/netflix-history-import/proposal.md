# Proposal

## Why

[Issue #90](https://github.com/niStee/ani-cli-sync/issues/90) reports unreliable Netflix CSV discovery. At pinned main `87314dc`, the importer mutates immediately, counts raw rows as episodes, splits titles at every colon, searches only a twelve-name whitelist, and can regress or complete entries without reading current state.

## What Changes

- Make `import-netflix CSV` a read-only preview by default; require explicit `--apply` for mutations.
- Accept the first-slice English `Title,Date` CSV header, UTF-8 BOM, CRLF, quoted Unicode, and embedded delimiters. Require nonblank title and date metadata without imposing a date syntax or chronology. Report every data row's disposition.
- Deduplicate repeat views by resolved episode identity, not title/date row count; retain series, season, and part context through a bounded explicit `Episode N` grammar.
- Resolve all relevant AniList candidates conservatively. Ambiguous or failed lookups remain explicit skips, never absence or guessed matches; missing season text never becomes season evidence.
- Infer progress only from an exact contiguous episode set `1..N`. Label progress and completion as inference from recorded events, never verified playback completion. Full known-total coverage may propose `COMPLETED` only with `--apply` consent, never from a count or highest number alone.
- Permit updates only for absent entries and `CURRENT` entries; leave every other existing status unchanged. Separate read-only planning from freshly revalidated apply, and disclose that the final read/write guard is not atomic.
- Treat HTTP transport failures, HTTP 200 GraphQL errors, malformed responses, and failed current-state reads as failures. Verify each mutation response and report partial results truthfully.
- Use exit 0 for completed processing, including explicitly reported unresolved skips; exit 1 for operational or partial failure; exit 2 for usage or input errors.
- Ship minimal README and command-help documentation with the behavioral change. Issue #88 will expand the guide later.

## Capabilities

### New Capabilities
- `netflix-history-import`: Safe, auditable conversion of Netflix viewing events into conservative, explicitly labelled AniList update proposals.

### Modified Capabilities

None.

## Impact

The existing importer, its CLI contract, bounded AniList helpers, synthetic tests, and README are affected. Runtime remains standard-library-only. No real export or credential is committed.

## Out of scope and review gates

No general mapping interface, universal or named-episode title grammar, watch/scraper offset reuse, unrelated helper cleanup, live test, or broad Netflix archive support. Under the authorized pilot, the GPT orchestrator selected P1 explicit contiguous-prefix inference and S1 conservative status handling on 2026-10-30; GLM-5.3 may write tests from this contract, and MiniMax-M3.1-Flash implements only after GPT test review. No intermediate human approval is required, but final human acceptance remains mandatory. Issue #88 depends on the approved semantics and must not ship conflicting examples.
