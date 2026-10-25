# Proposal: Attack on Titan Final Season Offset Mapping

Serves: niStee/ani-cli-sync#97

## Why

`resolve_episode_offset()` resolves an AniList season-relative episode number into the
provider's episode number. When a series is absent from the static `_EPISODE_OFFSETS`
table, it falls back to `compute_prequel_offset()`, which walks AniList's prequel
relation graph and sums the episode counts of every preceding season.

That fallback is wrong for *Attack on Titan: The Final Season*. The provider numbers
Part 1 and Part 2 as separate releases, and AniList's relation graph does not link them
as prequel/sequel pairs the way the walker expects. The walker computed a large, wrong
offset:

```
[00/16] Attack on Titan Final Season        -> ep 60   (expected 1)
[00/12] Attack on Titan Final Season Part 2 -> ep 76   (expected 1)
```

Observed during real playback on 2026-10-20: the resolved episode number was outside the
season, so the provider returned no stream and playback fell back to a season-relative
query. The episode still played, but only via the scraper fallback path, not because the
offset resolved correctly.

This is a table-entry gap, not a walker bug. The static table exists for exactly this
case and already carries hand-maintained entries for Overlord III/IV and Slime.

## Existing behaviour to preserve

The table is scanned in order and the first fragment match wins. Part 2 must be matched
**before** Part 1, because the Part 1 fragment (`Attack on Titan Final Season`) is a
substring of the Part 2 display title. An entry order of Part 1 first would swallow
every Part 2 episode and send it to the wrong release.

The `max_ep` bound is also load-bearing: an entry must not apply past the end of its
season, or an out-of-range episode would be mapped into a neighbouring season.

## What Changes

- Add five entries to the static offset table: Part 2 (AniList 1-12 -> provider
  `Attack on Titan: Final Season, Part 2`) on three AniList title variants, Part 1
  (AniList 1-16 -> provider `Attack on Titan: Final Season, Part 1`) on two.
- Part 2 entries precede Part 1 entries, so the longer fragment matches first.
- Every entry carries a search override, because the provider's title differs from
  AniList's.
- Every entry carries `max_ep`, so the mapping cannot leak past the season boundary.

No behaviour changes for any other series. No new dependency, no new config surface, no
change to the prequel walker.

## Out of Scope

- Changing the prequel walker itself. It is correct for the franchises it was written
  for; Attack on Titan is a table-entry gap.
- The ruff baseline change that accompanied the original local commit. That commit
  flipped a library module executable to silence ruff's `EXE001` as a side effect; the
  finding was instead fixed on its own terms in the lint-debt change (PR #96), which
  took the baseline from 16 to 0. This change carries no baseline change.
- Any other series' offset entries.

## Related

- `openspec/specs/offset-resolution/` - the offset resolution capability. (Not yet ported
  into this repo's capability-scoped spec layout; tracked as a separate follow-up issue.)
- Local branch `fix/aot-final-season-scraper-mapping` (commit `4dffb2b`), its origin.