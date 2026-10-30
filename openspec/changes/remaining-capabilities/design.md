# Design

## Context

See proposal.md - Why. This is a planning and characterization baseline at commit
`87314dc`, not a claim that all current behavior is desirable. The four delta
specs record bounded, source-supported behavior. Unsafe or unresolved branches
stay visible here rather than becoming normative requirements by omission.

The existing canonical specs for completion, episode offsets, subtitle tracks,
translation, and glossaries remain authoritative. In particular, this change
must not duplicate or weaken `autoplay-completion-threshold` or `subtitles`.

## Goals / Non-Goals

**Goals:**

- Map every proposed requirement to source and existing tests at the base commit.
- Identify missing characterization coverage and documentation conflicts.
- Preserve a review gate before any test, implementation, or promotion work.
- State which behavior is deliberately excluded rather than endorsed.

**Non-Goals:**

- No production code, tests, canonical spec changes, workflow edits, or live calls.
- No safety guarantee broader than the source proves.
- No fix for the discrepancies below and no new error-handling policy.
- No Netflix import specification beyond its command registration; #90 is separate.

## Decisions

### 1. Source is primary; tests are coverage evidence, not proof of intent

Each requirement is grounded in the base source. Existing tests are named where
they cover the same observable behavior; otherwise the gap is explicit. This
avoids deriving the baseline from the abandoned `fce6b4b` artifacts.

### 2. Bounded requirements exclude unsafe branches explicitly

The baseline specifies the supported post-playback update path, unambiguous
matching, and successfully read sequel state. It does not bless pre-play writes,
heuristic ambiguity resolution, failed-read assumptions, nonpositive episodes,
or blanket error semantics. These exclusions require separate reviewed changes,
not implementation tasks hidden inside this documentation change.

### 3. Preserve actual parser and timing behavior

The optional watch query is registered, and command-less rewriting supplies the
`watch` command before parsing. A bare non-command title therefore works; the
prior claim that it is broken is rejected. A parser-only mocked fixture confirmed
`Attack on Titan` reaches the watch query at this base.

For automatic timing, only nonzero manual delay suppresses measurement. Explicit
zero permits it. Measurement uses the first subtitle cue, not dialogue detection
or lyric exclusion. The nonzero precedence statement and episode-local scope
resolve the current flag-help wording and ADR conflict in favor of source behavior.

### 4. Adopt existing OpenSpec and unittest conventions

**Reuse check: adopt.** Reuse the repository's spec-driven schema, delta layout,
Python unittest style, and existing verification commands. No new framework,
schema, dependency, or test runner is needed.

**Practice review (sources read 2026-10-30):**

| Claim | Evidence | Verdict |
|---|---|---|
| Four artifact types and delta layout fit this change | OpenSpec spec-driven docs, undated current page, https://openspec.dev/docs/schemas/spec-driven; local `openspec/config.yaml` read 2026-10-30 | confirmed |
| Characterization records current behavior but does not prove correctness | Stack Overflow Blog, 2026-10-22, https://stackoverflow.blog/2026/10/22/the-regression-tests-nobody-writes-capturing-how-software-actually-behaves | confirmed |
| Current parser accepts a bare title | `src/ani_cli_sync/cli.py:1204-1211`; read-only mocked parser check run 2026-10-30 | confirmed |
| First-cue measurement is not dialogue alignment | `src/ani_cli_sync/subsync.py:270-333`; ADR-001 dated 2026-10-15 conflicts | confirmed discrepancy |
| External documentation establishes that excluded branches are safe | no such evidence; inspected source contradicts a broad guarantee | wrong; exclusions retained |

## Source and test traceability

| Requirement area | Source at base | Existing coverage and limit |
|---|---|---|
| Login, list, manual progress | `cli.py:38-50, 282-372` | `test_cli.py:363-407` covers above-total refusal and final completion; missing token, empty list, login, lower-progress, unknown-total, and nonpositive boundaries are uncharacterized |
| Post-playback update | `cli.py:641-683, 1032-1047` | `test_autoplay_stop.py` and `test_cli.py:673-1031` cover completion decisions and selected update flows; staleness and mutation failures are not covered |
| Sequel rollover | `cli.py:147-219, 1049-1109` | `test_cli.py:673-1128` covers accept, decline, autoplay, ambiguity, unreleased, progress preservation, and completed state; read failure is not distinguished from absence |
| CLI surface and defaults | `cli.py:1124-1236`; `pyproject.toml:44-46` | `test_subdelay_auto.py:111-147` covers sync parsing; aliases, bare invocation/title, argument errors, cancellation, and default subtitle set need characterization |
| Native playback fallback | `cli.py:788-816, 986-1005` | `test_cli.py:1188-1224` covers managed-fallback opt-out; no-token and empty-list delegation need coverage |
| Manual title resolution | `cli.py:243-279, 334-372` | `test_cli.py:17-108` covers exact, romaji, and substring cases; multiple-substring selection is unsafe and excluded |
| Watch query selection | `cli.py:818-880` | Sequel tests incidentally select a unique query; exact-among-many, narrowing, cancellation, and ambiguous autoplay fallback need focused coverage |
| Provider cut selection | `menu.py:10-89, 92-153` | `test_menu.py` covers normalization, tag preferences, fallbacks, and empty results; the duplicate embedded selector must remain equivalent |
| Automatic timing | `cli.py:720-771, 916-967`; `subsync.py:40-347` | `test_subsync.py` and `test_subdelay_auto.py` cover sign, primary track, failures, nonzero precedence, explicit zero, and episode locality; exact 60 and 0.05 boundaries and early-onset rejection need additions |

## Explicit discrepancies and exclusions

| ID | Current evidence | Baseline disposition |
|---|---|---|
| D1 | Autoplay global-search fallback writes progress 1 before playing (`cli.py:846-856`); existing `test_cli.py:431-458` pins that write | Excluded unsafe behavior. The post-playback requirement does not describe or authorize this path; do not add a characterization test that endorses it |
| D2 | `get_media_list_entry` maps every read exception to `None` (`cli.py:147-161`), which rollover treats as absent and may enroll at zero (`cli.py:1065-1096`) | Excluded unsafe behavior. Only successfully read sequel state is specified; no absence guarantee for failed reads |
| D3 | Playback progress is loaded once at selection and advanced from an in-memory counter (`cli.py:803-889, 1043-1047, 1111-1121`); the comment claiming AniList reconciliation is inaccurate (`cli.py:798-799`) | Excluded stale-write risk. Requirements cover only the selected season-relative episode after accepted playback, not monotonicity against concurrent remote changes |
| D4 | Multiple manual substring matches are sorted by shortest title (`cli.py:263-277`) | Excluded ambiguity heuristic. The matching baseline covers exact and unique matches only and does not imply a safe arbitrary choice |
| D5 | Set checks only `episode > total`; zero and negative integers reach the mutation (`cli.py:361-371`) | Excluded invalid-input behavior. A read-only mocked fixture observed both submitted as CURRENT; no positive-only guarantee is claimed |
| D6 | Broad catches flatten lookup failures into no match, while many API and mutation exceptions propagate (`cli.py:53-81, 236-240, 342-354`) | Excluded broad CLI error semantics. Only explicitly enumerated usage errors and missing-token status are specified |
| D7 | `--sub-sync` help says any explicit delay wins (`cli.py:1200-1201`), but explicit zero measures (`cli.py:720-726`); `test_subdelay_auto.py:94-108` confirms source behavior | Spec resolves in favor of nonzero-only precedence; help correction needs a later reviewed docs change |
| D8 | ADR-001 section 4 calls for intro-aware or post-intro dialogue onset, while source measures the first cue and first qualifying VAD speech (`subsync.py:182-229, 270-333`) | Spec documents the limited first-cue algorithm, not the ADR aspiration. First cue is not dialogue detection; lyric/OP handling remains excluded |
| D9 | Speech onsets before 0.5 seconds are ignored (`subsync.py:44-45, 225-229`), but the draft omitted this boundary | Coverage omission recorded for the test tier; the baseline's "usable speech onset" wording deliberately includes this implemented bound |

Additional coverage omissions relative to #104: token storage permissions and URL-fragment
extraction, non-command option forwarding, no-global-match exit, sequel eligibility
formats other than TV/ONA, provider substring/sibling fallbacks, and the exact
plausibility/negligibility boundaries. These are test or follow-up review items,
not permission to expand runtime scope. Netflix behavior remains excluded with #90.

## Risks / Trade-offs

- [A baseline can be mistaken for approval of defects] -> Name each unsafe branch,
  limit requirements to supported paths, and require user review before tests.
- [Existing tests can preserve a defect] -> Treat tests as evidence of current
  behavior, never as proof of correctness; D1 is the concrete example.
- [Specs can duplicate canonical rules and drift] -> Reference completion and
  subtitle-track contracts instead of restating their thresholds or track policy.
- [Source line references can rot] -> Treat them as base-commit traceability only;
  behavioral requirements remain independent of internal names.

## Migration Plan

No deployment or runtime migration. Planning is complete only after strict
OpenSpec validation and user review. A later separately authorized promotion can
add missing hermetic characterization tests, run positive/negative sensitivity
probes, and sync the four deltas without changing production behavior. Rollback
is removal of this unmerged planning directory.
