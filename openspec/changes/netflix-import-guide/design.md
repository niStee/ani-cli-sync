# Design

## Context and dependency

This package expands documentation only after the `netflix-history-import` (#90) behavior is accepted. It does not make the proposed importer current behavior. #90 supplies minimum CLI help and a corrected README command section in its behavioral PR; #88 adds the detailed guide and a link without changing the command contract.

The #90 proposal currently recommends preview by default, explicit `--apply`, conservative candidate matching, strict `Title,Date` input, full row dispositions, fresh monotonic state checks, verified writes, and exits 0/1/2. Its unresolved semantic decisions are isolated below. No real export or live AniList operation was used.

## Goals / Non-Goals

**Goals:**
- Let a user obtain the correct file, understand what leaves their machine, preview safely, interpret results, and rerun without surprises.
- Make uncertainty visible instead of presenting title matching or episode inference as exact.
- Keep examples traceable to one accepted behavior contract.

**Non-Goals:**
- A second importer specification, new CLI flags, universal title parsing, archive ingestion, live verification, or real-user fixtures.

## Planned document structure

Create `docs/netflix-viewing-history-import.md` with the following sections.

### 1. What this imports

Explain that the command consumes the official per-profile Viewing activity CSV, not a spreadsheet converted through another program and not every file in a personal-data archive. The supported #90 input is UTF-8 `Title,Date`, including the documented BOM/CRLF/quoting cases. Viewing rows are evidence to reconcile, not proof that every row becomes AniList progress.

### 2. Export the official CSV

Numbered browser steps, citing the official help page inline:

1. Open the Netflix Account page in a browser.
2. Select Profiles and the profile whose history should be imported.
3. Open Viewing activity.
4. If only a limited list is visible, select Show More.
5. At the bottom, select Download all and keep the resulting CSV locally.

Use `~/Downloads/NetflixViewingHistory.csv` as an illustrative path, not a guaranteed filename. Distinguish this flow from Account -> Get My Info / `account/getmyinfo`: the latter requests a broader personal-information copy, can take up to 30 days after verification, and is not the supported importer input. Do not claim the official pages define the detailed episode-title grammar.

### 3. Privacy and network expectations

- Viewing history is personal data. Use synthetic titles in examples and issue reports; never commit or paste a real export, account identifier, token, or full command output containing private titles.
- Keep the downloaded file under the user's control and inspect its header before use. The guide does not upload the CSV to Netflix or a third-party conversion service.
- Local parsing and validation happen before AniList operations under the #90 design. Preview is read-only with respect to AniList mutations, but it still sends necessary title/current-state queries to AniList; it is not an offline mode.
- Apply sends only the displayed safe mutations, but output and API queries still contain viewing titles. AniList credentials remain in the existing authentication flow; they are not placed in the CSV, examples, or documentation.
- Do not prescribe destructive deletion. Tell users to retain or remove their local export according to their own privacy needs.

### 4. Preview and apply examples

All examples are conditional on #90's accepted CLI and must be checked against actual `--help` before publication.

Base preview example, valid under both evidence policies:

```bash
ani-cli-sync import-netflix ~/Downloads/NetflixViewingHistory.csv
```

Explain that preview validates the entire input, resolves candidates and current state, and displays per-row/per-target dispositions without sending mutations. Header-only input reports zero events and writes nothing.

If #90 selects P1 (contiguous evidence may propose progress), include the explicit apply example:

```bash
ani-cli-sync import-netflix ~/Downloads/NetflixViewingHistory.csv --apply
```

If argument order in the accepted parser/help differs, reproduce the accepted form exactly rather than preserving this draft. Explain that `--apply` is not force: fresh reads still block regression/reopening, and failed verification is reported.

If #90 selects P2 (preview-only), omit `--apply` entirely. Show the existing explicit command only as a user-reviewed follow-up:

```bash
ani-cli-sync set "Example Anime" 3
```

The P2 text must say the importer does not infer or apply progress; the user chooses the exact AniList episode number after reviewing mappings. Do not mix P1 and P2 examples.

### 5. Mapping and progress evidence

Document accepted behavior, not aspirations:

- Full quoted titles, colons, Unicode, seasons/parts, and explicit episode markers are preserved; one franchise is not split blindly at its first colon.
- A single context-consistent AniList candidate is required. No match, multiple plausible matches, films/specials outside the supported contract, and missing episode evidence are visible unresolved/ambiguous dispositions, never silent first-result choices.
- Repeat rows for the same resolved episode deduplicate to one unit of evidence while every source row remains accounted for.
- Lookup/read failure differs from absence or no match. A failed current-state read never authorizes creation.

Conditional P1 wording: positional progress may be proposed only for explicit contiguous coverage `1..N`. Highest observed episode, unique count, raw row count, and dates do not prove watched-through progress. Sparse evidence such as episode 8 alone or episodes 1,2,4 is blocked. Completion additionally requires full coverage of a known positive episode total.

Conditional P2 wording: no positional progress or completion is inferred from viewing rows; use explicit `set` after review.

Status wording follows #90's selected S1/S2 policy. S1 documents absent-entry creation as CURRENT, safe CURRENT increases, and fully covered CURRENT-to-COMPLETED proposals, with PLANNING/PAUSED/DROPPED/REPEATING/COMPLETED unchanged. S2 additionally documents the exact previewed PLANNING-to-CURRENT transition. Neither branch permits reopening COMPLETED or regressing current progress. Delete the unselected branch before publication.

### 6. Read the result and exit status

Include a table:

| Exit | Meaning | User action |
|---|---|---|
| 0 | Processing completed, including explicit unresolved, ambiguous, duplicate, unchanged, or insufficient-evidence skips | Review dispositions; zero does not mean every row was imported |
| 1 | Operational, partial, or unverified apply failure | Read verified versus failed targets separately; correct the cause before rerunning |
| 2 | Usage or input validation failure | Fix the path, encoding, header, row shape, title, or date; no API operation should have occurred for invalid input |

Do not replace these meanings with generic success/failure prose. Show invented, abbreviated output only if it matches the accepted implementation's actual labels; otherwise use field descriptions rather than fake exact output.

### 7. Repeats, partial completion, and idempotence

A fully applied plan rerun against fresh current state reports targets unchanged, sends no mutation, and exits 0. Repeated view dates do not inflate progress. After a partial apply, already verified updates remain applied; there is no cross-entry rollback claim. Rerunning reconciles current state, but unresolved or ambiguous rows still need their stated issue resolved. Preview itself never proves that a later mutation succeeded.

### 8. README integration

Replace no detailed #90 safety text. Add one sentence after its accepted Netflix section: `For export steps, privacy, mapping evidence, exit codes, and reruns, see the [Netflix viewing-history import guide](../docs/netflix-viewing-history-import.md).` Ensure the link is relative and resolves from README.

## Dependency decision table

| #90 decision | #88 publication consequence |
|---|---|
| P1 | Include preview/apply and contiguous `1..N` examples; prohibit highest/count/date inference |
| P2 | Remove apply/progress inference; show preview plus explicit reviewed `set` |
| S1 | Keep non-CURRENT entries unchanged; document only absent/CURRENT/fully-covered completion behavior |
| S2 | Add only the exact previewed PLANNING-to-CURRENT transition |
| Any unresolved decision or changed exit/help text | Stop documentation implementation; do not guess |

## Delegated documentation brief and gates

Under the 2026-10-30 pilot override, no intermediate human approval is required. GPT orchestrator first verifies #90's final accepted semantics and actual help, selects/removes the conditional branches, and approves this documentation plan. MiniMax-M3.1-Flash may then make only the bounded guide/README edit; no GLM behavioral test stage is needed. GPT reviews the rendered guide against #90's accepted spec/tests/help, and final human acceptance remains mandatory. This planning session performs no edit to the guide, README, code, or tests.

## Acceptance checks

- Official export path and archive distinction match the two read sources; links work and no unsupported title-format claim is attributed to Netflix.
- Every example and safety statement matches accepted #90 behavior; no unselected P1/P2/S1/S2 branch remains.
- Privacy says preview has AniList reads but no mutations; no real viewing data, token, or credential appears.
- Mapping, evidence, statuses, dispositions, exit precedence, partial results, and idempotence agree with #90.
- README's minimum #90 documentation remains intact and the new relative guide link resolves.
- `git diff --check` passes; the diff contains only the new guide and README link; no full-suite or live run is used for this docs-only change.

## Practice review (sources read 2026-10-30)

- [Netflix viewing activity, help node 101917](https://help.netflix.com/en/node/101917), live page without a shown publication date: **confirmed** the Account/Profiles/Viewing activity/Show More/Download all CSV flow; no detailed row grammar is documented there.
- [Netflix personal information copy, help node 100624](https://help.netflix.com/en/node/100624), live page without a shown publication date: **confirmed** the separate broader request at `account/getmyinfo` and its possible 30-day production time.
- #90 design/spec at pinned planning state, read 2026-10-30: **needs-precision** until GPT selects D1/D2 and final behavior is accepted; conditional branches isolate that dependency rather than hiding it.

**Reuse check: adopt.** Reuse Netflix's official flow and #90's minimum docs and accepted examples; add only the requested detailed guide. No importer wrapper, conversion tool, sample real export, or documentation framework is needed.

## Traceability and risks

- Proposal export/privacy rows map to sections 1-3 and official sources.
- Preview/apply, mapping/status, exit, and idempotence rows map to sections 4-7 and #90's corresponding requirements.
- Minimum-doc dependency maps to section 8 and #90 task 3.1.
- **Risk:** documentation ships before behavior. **Mitigation:** hard dependency and actual-help review.
- **Risk:** guide becomes a second spec. **Mitigation:** no delta, no invented output, and #90 remains authoritative.
