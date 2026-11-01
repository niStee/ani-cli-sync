# Design

## Context

See `proposal.md` and `specs/netflix-history-import/spec.md`. Source inspection at pinned main `87314dc54de181b928a49c2711f3783efca5c532` found `cmd_import_netflix` in `src/ani_cli_sync/cli.py` at lines 375-448. It writes before reading state, groups at the first colon, limits discovery to twelve hard-coded names, takes one `Media(search:)` result, equates `len(items)` with progress, and always prints success. There is no importer test at the pinned SHA.

The shared helpers need bounded correction for this path: `search_anime` collapses lookup failure and no match; `get_media_list_entry` returns `None` for both; `gql_query` returns a JSON object without inspecting top-level GraphQL `errors`; and `update_progress` accepts an empty or partial payload. This change may harden those contracts for importer callers, but must not silently redefine unrelated watch behavior. Reuse existing `gql_query`, AniList GraphQL, `csv`, `argparse`, and `unittest`; no dependency, new mapping file, or broad refactor.

Netflix's official help documents downloading viewing activity as CSV but does not pin a detailed title grammar, date syntax, or episode-completion semantics. The first slice therefore adopts an explicit support boundary rather than claiming a universal Netflix schema.

## Goals / Non-Goals

**Goals:**
- One previewable plan, freshly checked monotonic apply, explicit per-row accounting, and truthful failure semantics.
- Explicit episode evidence, season/part-safe identity, and conservative candidate resolution.
- Clearly labelled inference from recorded events, distinct from verified playback completion.
- Bounded API contracts that distinguish absence from failure.

**Non-Goals:**
- A universal or named-episode Netflix title grammar, manual mapping UI/file, movie/special inference, or scraper offset import.
- Live AniList or Netflix calls in tests, real viewing data, transactional multi-entry rollback, atomic concurrent-write protection, or unrelated API cleanup.

## Orchestrator decisions and pilot authorization

The operator explicitly authorized this pilot on 2026-10-30 without intermediate human spec or test approvals. GPT orchestrator quality review replaces those intermediate gates; GLM-5.3 writes tests only after GPT spec approval, MiniMax-M3.1-Flash implements only after GPT test review, and final human acceptance remains mandatory. This planning session performs neither tests nor implementation.

### Progress evidence: P1 selected

Use an exact contiguous set of explicit episode identities `1..N`, not merely a usable prefix inside a larger sparse set. If the distinct resolved episode set has maximum `N`, progress `N` is proposable only when the set contains every integer from 1 through `N`. Late-only evidence or any gap at or below the maximum blocks that group's progress proposal rather than silently ignoring higher episodes.

This is an explicitly consented inference from recorded Netflix episode events, not verified playback completion. Full known-total coverage may propose `COMPLETED` only as labelled inference and only `--apply` can consent to the mutation. A known total is necessary for completion; highest observed episode, unique event count, raw row count, and date order are rejected as substitutes for coverage.

P2 preview-only was not selected because the approved pilot permits bounded inferred updates with preview and explicit consent. The conservative evidence and labelling rules above preserve the rationale for P2 without leaving two alternative contracts in force.

### Status policy: S1 selected

- An absent entry may be created only as `CURRENT` at the inferred progress, including when that progress equals a known total; direct absent-to-`COMPLETED` creation is not allowed.
- A `CURRENT` entry may receive a progress increase. It may transition to `COMPLETED` only for exact `1..T` coverage of a known positive total `T`, with the proposal labelled as inference and authorized by `--apply`. A status-only completion is permitted when fresh progress already equals `T`; progress above `T` blocks the planned mutation rather than being lowered.
- `PLANNING`, `PAUSED`, `DROPPED`, `REPEATING`, and `COMPLETED` entries always receive explicit status-policy or unchanged dispositions. No transition, progress mutation, or reopening is permitted for them.

S2's `PLANNING -> CURRENT` widening was not selected; preserving the user's existing non-`CURRENT` intent is the conservative policy. Arbitrary reopening or status conversion remains rejected.

## Decisions

### Decision 1: Strict input, then immutable plan, then guarded apply

Use `open(..., encoding="utf-8-sig", newline="")` and `csv.DictReader` with strict parsing. Require exactly two header fields whose trimmed values are the case-sensitive English names `Title` and `Date`, and exactly two fields per data row. Titles and dates must contain non-whitespace text after trimming. Preserve date text as source metadata only: impose no syntax, locale parsing, sorting, or chronological inference. The `Title,Date` header is this slice's supported input contract, not a claim that Netflix officially documents only that schema.

Read and validate all input before any API operation. An invalid file is one exit-2 input failure, not a mixture of valid and rejected rows. Parse, group, resolve, and read current state into a deterministic plan. Preview stops there. Every progress or status proposal is labelled as inference from recorded events, never verified playback.

Apply re-reads state immediately before each planned mutation and skips the mutation unless the displayed change remains safe under the selected status policy. This reduces stale-plan regression risk but is not an atomic compare-and-set: AniList's documented mutation flow has no expected-current-state or version predicate for this operation. A remote write between the final read and mutation can still race the update, so neither documentation nor results may claim strict simultaneous remote non-regression. There is no cross-entry rollback; verified successes and failures remain separately visible.

**Alternative:** Apply row by row while parsing. Rejected because early mutations precede discovery of later input errors and prevent a complete preview.

### Decision 2: Bounded right-anchored episode grammar

After trimming surrounding whitespace from the full title, support only a whole-string match to `^(.+): Episode ([1-9][0-9]*)$`. Trim the captured release context and require it to be non-empty. The literal delimiter and `Episode` token are case-sensitive. Earlier colons remain part of release context; no text may follow the episode number. Explicit `Season N` and `Part N` markers already present in that context are preserved as release evidence; their absence remains absence.

| Synthetic title | Release context | Evidence retained |
|---|---|---|
| `Chrono Academy: Eclipse: Episode 1` | `Chrono Academy: Eclipse` | Episode 1; no season or part inferred |
| `Chrono Academy: Eclipse: Season 2: Episode 3` | `Chrono Academy: Eclipse: Season 2` | Season 2, episode 3 |
| `Chrono Academy: Part 2: Episode 4` | `Chrono Academy: Part 2` | Part 2, episode 4 |

A form such as `Chrono Academy: Episode 3: The Name`, a bare episode name, a movie, or a special is unresolved in this slice. No named-episode mapping is promised without later evidence and a new contract.

Deduplicate on `(media_id, episode_number)` after resolution. Keep source-row references and uninterpreted date metadata in dispositions, not identity. Unknown episode numbering is not guessed.

**Alternative:** Split on the last colon only as a universal rule. Rejected because named episode labels can themselves contain colons; the whole-string suffix and candidate consistency define this bounded slice instead.

### Decision 3: Multi-candidate AniList resolution

Add an importer-scoped candidate query using AniList `Page(media(search:..., type:ANIME))`, requesting stable `id`, English/romaji/native titles, synonyms, `episodes`, and `format`, with a small documented bound (for example, at most 10 candidates per distinct release query). Fetch no next page automatically; a full page is reported as potentially incomplete and ambiguous unless one exact context-consistent candidate is established.

Normalize case and surrounding whitespace for comparison, retain full release tokens, and accept only one candidate consistent with all explicit season/part evidence. An explicit source qualifier must have equivalent candidate context. Never synthesize `Season 1` or `Part 1` from a missing source qualifier, and never remove a candidate's extra season/part qualifier to force a match. An unqualified source can match an exactly unqualified candidate alias without assigning it an inferred season number.

Never take the first result or use generic substring popularity. Keep candidate IDs/titles in ambiguity diagnostics without dumping unrelated history. Cache successful candidate lists per query within the run; do not cache failures as no match.

**Alternative:** Reuse singular `search_anime` as-is. Rejected because it loses both alternatives and failure evidence.

### Decision 4: Explicit read/write API contracts

For importer operations, a valid response must be a JSON object, contain no top-level `errors`, and contain the expected `data` shape. A `null` `MediaList` under valid `data` means no existing entry; an exception, GraphQL error, missing `data`, or malformed `MediaList` means read failure. Mutation success requires `SaveMediaListEntry` with matching `mediaId`, integer `progress`, and requested `status`; otherwise it is unverified and exit 1.

Keep these checks local to importer-facing wrappers unless a shared-helper change is proven behavior-preserving for existing callers. Do not turn a caught read error into absence. Do not add retry loops beyond the existing bounded transport policy or sleeps in tests.

### Decision 5: Deterministic dispositions and exit precedence

Keep an internal disposition per input row and per target update. Render source row number and title, uninterpreted date metadata, dedupe target, mapping evidence, planned/current/target progress and status, and the inference label or a concise skip/failure reason. Never print an all-imported success message when unresolved or failed rows exist, and never describe inferred progress or completion as verified playback.

Exit precedence is 2 for usage/input (before API), then 1 if any operational failure or unverified/partial apply occurred, otherwise 0. Unmatched, ambiguous, insufficient-evidence, status-policy, duplicate, and unchanged dispositions are completed processing and can exit 0. This does not call skipped rows imported. `--apply` never means force.

## Fixture matrix (synthetic only)

All fixtures use invented titles and response data. No real Netflix CSV, names from an operator account, tokens, or live calls.

| ID | Input / response | Expected observable result |
|---|---|---|
| F01 | UTF-8 BOM, CRLF, `Title,Date` | Header accepted; nonblank dates retained only as metadata |
| F02 | Quoted Unicode, commas, doubled quotes, colon-rich franchise title, differently formatted nonblank locale dates | Full title/date text preserved; no first-colon grouping, date parser, or chronology |
| F03 | LF input and header-only input | Valid; zero rows exits 0 with no writes |
| F04 | Missing/unreadable path, non-UTF-8, wrong/missing header, short/long row, malformed quote, blank title, blank/whitespace-only date | Exit 2; no API call or mutation |
| F05 | Same media/episode on two dates plus another episode | One deduped identity; every source row reconciled; dates do not order progress |
| F06 | Same franchise, different explicit seasons/parts with episode 1 | Distinct media identities; no cross-season merge |
| F07 | `Chrono Academy: Eclipse: Season 2: Episode 3` and an unqualified colon-rich variant | Correct release and episode preserved; absent season is not inferred |
| F08 | Movie, bare episode name, `Episode 3: The Name`, unsupported special | Explicit unresolved skip; no inferred progress or named-episode claim |
| F09 | One exact candidate vs no candidates | Confident plan vs unmatched skip, both non-operational |
| F10 | Two plausible candidates, remake/film conflict, candidate with extra season qualifier | Ambiguity skip with candidates; no first-result choice or qualifier stripping |
| F11 | Transport failure vs HTTP 200 `errors` vs invalid/missing JSON data | Operational failure exit 1; never no match |
| F12 | Episodes 1,2,3 vs 8 only vs 1,2,4 | Exact set proposes inferred 3; sparse forms block the group; no count/high inference |
| F13 | Episodes 1,2 repeated, known total 2 vs known total 3 | Full coverage may propose labelled inferred completion under status policy; partial coverage cannot |
| F14 | Unknown/zero/negative episode total | No completion inference; otherwise valid exact-prefix handling only |
| F15 | Absent, CURRENT lower/equal/higher, COMPLETED, and each other status | Only selected absent/CURRENT transitions; no direct absent completion, regress, or reopen |
| F16 | Preview vs apply | Identical plan evidence and inference labels; zero mutations in preview |
| F17 | Fresh read failure / valid `MediaList:null` | Failure blocked vs true absent entry |
| F18 | Fresh progress advanced after preview | Mutation skipped against newer mocked state; no atomic concurrent-write guarantee claimed |
| F19 | Verified mutation vs empty/wrong-media/wrong-progress/wrong-status response | Success only on exact verification; other cases exit 1 |
| F20 | First update verified, second fails; later rerun already current | Truthful partial result exit 1; idempotent rerun exit 0 and no writes |
| F21 | Valid safe row plus unmatched/ambiguous/insufficient row | All dispositions visible; summary reconciles; exit 0 without false import claim |

For every guard pair, GLM must include a positive and negative case and record a sensitivity probe: mutate the implementation to remove/weaken exactly that guard, observe the focused test fail, restore, and observe it pass. At minimum probe preview-no-write, episode dedupe, no first-candidate fallback, no missing-season inference, no count/high inference, no regress/reopen, failed-read-is-not-absent, GraphQL-errors-fail, mutation verification, and exit precedence. Test the sequential fresh-state guard with mocks; do not invent an impossible strict simultaneous-write assertion.

## GLM-5.3 test brief - spec approved under pilot

Derive tests from the approved delta and F01-F21 in `tests/test_netflix_import.py` (or the smallest consistent existing test module). Use `unittest`, temporary synthetic CSVs, and mocked API boundaries. Freeze expected CLI output/exit behavior and mutation call counts, including inference labels and nonblank locale-date acceptance. Test both pure parsing/planning and command-level preview/apply seams; do not contact Netflix, AniList, a player, or credentials. Include positive/negative pairs and record every sensitivity probe with focused red and restored green commands. Do not implement production code, weaken expectations to fit current behavior, add real exports, broaden helper behavior beyond the approved contract, or claim atomic concurrent-write safety. Deliver tests and probe evidence for GPT review; implementation remains blocked until that review.

## MiniMax-M3.1-Flash implementation brief - blocked pending test review

After GPT approves the frozen tests and recorded probes, make the smallest standard-library change to the existing importer and bounded API wrappers. Preserve all frozen tests byte-for-byte unless GPT authorizes a test correction. Implement strict CSV validation with nonblank uninterpreted dates, structural episode identities, candidate resolution, exact-prefix inference, selected status transitions, plan/apply separation, fresh monotonic guards, verified responses, dispositions, and exits exactly as approved. Remove the twelve-title whitelist from the importer only; do not add a mapping interface or refactor unrelated commands. Update command help and the minimal README section in the same behavioral change, including the inference and non-atomicity disclosures. Use no real service, live write, dependency, or player. Run focused tests, then `PYTHONPATH=src python3 -m unittest discover -s tests`, `ruff check .`, and `python3 scripts/ruff_count_ratchet.py`; report actual results.

## Practice review (read 2026-10-30)

- [Netflix viewing activity, help node 101917](https://help.netflix.com/en/node/101917), live help page with no publication date shown: **confirmed** Account -> Profiles -> profile -> Viewing activity -> Download all yields CSV. **Not officially verifiable:** a fixed title grammar, date syntax, or verified episode-completion semantics; the page does not specify them.
- [Netflix personal information copy, help node 100624](https://help.netflix.com/en/node/100624), live help page with no publication date shown: **confirmed** the wider archive is a different flow and may take up to 30 days.
- [Python `csv` documentation, 3.15.2, updated 2026-10-29](https://docs.python.org/3/library/csv.html): **confirmed** `newline=''`, Unicode decoding choice, quoting, and `strict=True`; adopt the standard library. It does not supply date validation, so none is invented here.
- [AniList GraphQL errors](https://anilist.gitbook.io/anilist-apiv2-docs/docs/guide/graphql/errors.md), live documentation with no page date shown: **confirmed** callers must inspect `errors` even for HTTP 200.
- [AniList `MediaListStatus`](https://anilist.gitbook.io/anilist-apiv2-docs/docs/reference/enum/medialiststatus.md), live documentation with no page date shown: **confirmed** six statuses; no automatic transition safety is supplied by the API.
- [AniList mutations](https://anilist.gitbook.io/anilist-apiv2-docs/docs/guide/graphql/mutations.md) and [`MediaList`](https://anilist.gitbook.io/anilist-apiv2-docs/docs/reference/object/medialist.md), live documentation with no page dates shown: **confirmed** save/update and returned progress/status fields. No expected-current-progress, version, or compare-and-set predicate is documented for the mutation used here, so the fresh read/write sequence must not claim atomicity.

**Reuse check: adopt.** Adopt Python `csv` and the repository's AniList/`argparse`/`unittest` seams, wrapping only their unsafe response contracts. A new importer framework or mapping service adds no needed capability.

## Risks / Trade-offs

- **[Risk]** Exact contiguous coverage imports little from partial Netflix histories. **Mitigation:** truthful unresolved output; no silent use of a shorter prefix when higher gaps exist.
- **[Risk]** Recorded viewing events can be mistaken for verified playback. **Mitigation:** label every inferred proposal, require preview plus `--apply`, and restrict completion to full known-total coverage under the status policy.
- **[Risk]** Netflix title grammar varies by locale or release. **Mitigation:** the explicit right-anchored grammar, bounded fixtures, and ambiguity skips; no universal or named-episode claim.
- **[Risk]** Nonempty date metadata is not necessarily a real calendar date. **Mitigation:** deliberately do not parse, compare, or use it for progress; reject only blank metadata in this slice.
- **[Risk]** A later apply failure or concurrent remote write can leave state different from the preview. **Mitigation:** fresh guards, per-target verification, partial exit 1, an explicit non-atomicity warning, and no false rollback or strict non-regression claim.
- **[Risk]** Shared helper hardening changes watch behavior. **Mitigation:** importer-scoped wrappers and existing-suite regression checks.

## Migration Plan

The default becomes preview, so existing automation that expected immediate writes must add `--apply` only after reviewing output and its inference labels. There is no data migration or automatic rollback. Re-running apply is idempotent after current-state verification, subject to the disclosed concurrent-write limitation. README and CLI help must land with the behavior; #88 expands documentation afterward.

## Traceability

- Input/preview: spec requirements 1-3; F01-F08, F16; tasks 1-2.
- Identity/resolution/evidence: requirements 4-6; F05-F14, F21; tasks 1-2.
- Status/read/verification/partial results: requirements 7-10; F11, F15-F21; tasks 1-3.
- Minimum docs and final checks: proposal Impact; task 3.
