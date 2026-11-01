# Spec Delta

## Purpose

Imports Netflix viewing history into AniList through an auditable preview and conservative, explicitly authorized apply, with inferred proposals distinguished from verified playback and freshly observed progress guarded against regression.

## ADDED Requirements

### Requirement: Preview Before Mutation
The import command SHALL default to a read-only preview and SHALL mutate AniList only when the user explicitly requests apply mode for the displayed proposals.

#### Scenario: Default invocation previews without writing
- **WHEN** a user supplies a valid viewing-history CSV without apply mode
- **THEN** the system reads and resolves the history, displays all row dispositions and inferred proposals, performs no mutation, and identifies preview mode

#### Scenario: Explicit apply authorizes only the reviewed plan
- **WHEN** a user requests apply mode for the same valid input
- **THEN** the system freshly validates current state before each update and applies only safe changes from the displayed plan, including only those inferred progress or completion proposals shown for consent

### Requirement: Supported CSV Validation
The importer SHALL accept a well-formed CSV with the English `Title,Date` header, optional UTF-8 BOM, CRLF or LF records, and RFC 4180 quoting, and SHALL reject unsupported or unreadable input without API operations.

#### Scenario: Quoted Unicode history and locale dates are preserved
- **WHEN** a BOM-prefixed CRLF CSV contains quoted Unicode titles, colons, commas, and nonblank date text in different locale formats
- **THEN** each data row is retained with its full title and date text and represented in the preview without date parsing or chronological inference

#### Scenario: Invalid input is a usage error
- **WHEN** the file is absent, unreadable, not UTF-8, has an unsupported header or row shape, malformed quoting, a blank title, or a blank or whitespace-only date
- **THEN** the importer reports the offending input, exits 2, and performs no API read or mutation

#### Scenario: Header-only history completes without changes
- **WHEN** a valid CSV contains its header and no data rows
- **THEN** the importer reports zero events, performs no mutation, and exits 0

### Requirement: Full Input Disposition
Every input data row SHALL appear in the result as deduplicated, mapped, proposed, unchanged, unresolved, or rejected for a stated reason; summaries SHALL reconcile with the input count.

#### Scenario: Unresolved anime remains visible
- **WHEN** one valid row has no confident anime mapping and another maps safely
- **THEN** the result names both dispositions, processes the safe candidate, reports the unresolved skip, and exits 0 when no operational failure occurred

#### Scenario: Repeated view does not create extra progress
- **WHEN** the same resolved episode occurs with different nonblank date metadata
- **THEN** the rows share one episode identity, every occurrence is reported, and only one episode of evidence contributes to the plan without ordering the dates

### Requirement: Series And Episode Identity
The supported episode form SHALL be non-empty release context followed by a right-anchored, case-sensitive `: Episode N` suffix, where N is an unsigned positive decimal integer without leading zeros. Other forms SHALL remain unresolved.

#### Scenario: Colon-rich release and explicit season remain intact
- **WHEN** a row title is `Chrono Academy: Eclipse: Season 2: Episode 3`
- **THEN** release context `Chrono Academy: Eclipse: Season 2`, explicit season 2, and episode 3 are preserved rather than grouping at the first colon

#### Scenario: Unsupported or named episode forms are not guessed
- **WHEN** a row lacks that exact suffix, including `Chrono Academy: Episode 3: The Name` or a title with no episode number
- **THEN** the row is explicitly unresolved and contributes no positional progress, without claiming named-episode support

#### Scenario: Releases retain separate episode identities
- **WHEN** two explicit seasons or parts contain the same episode number
- **THEN** the events remain associated with their respective releases and are deduplicated by resolved media identity and episode number, not date or raw title prefix

### Requirement: Conservative Media Resolution
Media resolution SHALL evaluate plausible AniList candidates against the full preserved release context and select only a single context-consistent match, without inventing missing season or part evidence.

#### Scenario: Multiple plausible candidates require review
- **WHEN** search returns more than one context-consistent series, season, part, remake, or film candidate
- **THEN** the importer skips that history group with an ambiguity reason and candidate details rather than choosing the first result

#### Scenario: Missing season text is not season-one evidence
- **WHEN** the source release context has no season or part marker
- **THEN** the importer does not infer `Season 1` or `Part 1`, and does not strip a candidate's release qualifier to force a match

#### Scenario: No match differs from lookup failure
- **WHEN** a completed lookup returns no candidates
- **THEN** the group is reported as unmatched without an operational failure, distinct from a failed lookup

### Requirement: Positional Progress Requires Coverage
For a mapped release with distinct episode set E and maximum M, progress SHALL be proposed only when E is exactly `1..M`. That proposal is inference from recorded events, never verified playback completion; counts, highest numbers, and dates SHALL NOT establish progress.

#### Scenario: Exact initial coverage supports labelled inference
- **WHEN** a confidently mapped release has explicit evidence for exactly episodes 1, 2, and 3
- **THEN** the preview labels inferred progress 3 from recorded episode events and makes no verified-playback claim

#### Scenario: Sparse evidence blocks the whole group's positional inference
- **WHEN** a group contains only episode 8, or episodes 1, 2, and 4
- **THEN** the importer blocks that group's progress update as insufficient coverage rather than proposing 8, 3, 4, or a shorter prefix that ignores the gap

#### Scenario: Full known-total coverage supports only a consented completion proposal
- **WHEN** the distinct episode set is exactly `1..T` for a known positive total T
- **THEN** the preview may label an inferred `COMPLETED` proposal subject to the status policy, and only explicit apply mode may authorize it; neither count nor highest number alone can complete an entry

#### Scenario: Unknown or invalid total cannot establish completion
- **WHEN** the candidate total is unknown, zero, or negative
- **THEN** exact initial coverage may still support inferred progress, but no completion proposal is made

### Requirement: Status Transitions Are Explicitly Bounded
Only an absent entry may be created as `CURRENT`; existing `CURRENT` entries may increase progress and may become `COMPLETED` only with full known-total coverage. Every other existing status SHALL remain unchanged.

#### Scenario: Absent entry is created only as CURRENT
- **WHEN** exact initial coverage maps to an entry that is absent, including coverage through a known total
- **THEN** the preview proposes a new `CURRENT` entry at the inferred progress, never a direct absent-to-`COMPLETED` transition, and apply requires explicit consent

#### Scenario: Current entry can receive an inferred completion proposal
- **WHEN** an existing `CURRENT` entry has full known-total coverage and progress no higher than that total
- **THEN** the preview may propose `CURRENT` to `COMPLETED` as labelled inference, and only explicit apply mode may authorize that mutation

#### Scenario: Other existing statuses receive a policy skip
- **WHEN** a planned target currently has `PLANNING`, `PAUSED`, `DROPPED`, or `REPEATING` status
- **THEN** the importer reports a status-policy skip and leaves progress and status unchanged even with full coverage

#### Scenario: Completed entry remains completed
- **WHEN** a planned target is already `COMPLETED`
- **THEN** the importer reports it unchanged and neither lowers progress nor reopens it

### Requirement: Reads And Writes Are Separated
Input, resolution, and initial state reads SHALL precede apply. Immediately before each mutation, state SHALL be read again and unsafe or stale changes skipped; failed reads are unknown. The final check and write are not atomic.

#### Scenario: Failed current-state read blocks its update
- **WHEN** current-state retrieval fails for an otherwise safe target
- **THEN** no update for that target is attempted, the failure is reported, and processing exits 1

#### Scenario: Fresh state prevents regression from the observed state
- **WHEN** a fresh read shows current progress equal to or above an inferred progress-only target, or a status that the bounded policy does not permit changing
- **THEN** the importer skips the mutation and reports the target unchanged or stale without regressing or reopening it

#### Scenario: Concurrent remote writes have no atomic guarantee
- **WHEN** a remote entry changes after the final current-state read but before the subsequent mutation
- **THEN** the importer does not claim strict simultaneous non-regression and documents that the fresh-state guard cannot prevent this race

### Requirement: GraphQL And Mutation Verification
AniList operations SHALL fail on transport errors, non-success HTTP responses, GraphQL errors at any HTTP status, invalid JSON, or missing expected data, and every mutation SHALL be verified against its requested media, progress, and status.

#### Scenario: HTTP 200 GraphQL error is not a match
- **WHEN** a search response has HTTP status 200 and a GraphQL `errors` member
- **THEN** the operation is an operational failure, not an empty result, and exit is 1

#### Scenario: Unverified update is a partial failure
- **WHEN** a mutation response is absent, malformed, or disagrees with the requested target
- **THEN** the importer reports that update as unverified, performs no claim of success, and exits 1

### Requirement: Truthful Completion And Partial Results
The importer SHALL distinguish completed processing, operational or partial failure, and usage or input failure using exits 0, 1, and 2 respectively, while retaining completed results after a partial failure.

#### Scenario: Explicit unresolved skips can complete successfully
- **WHEN** all operations finish and some rows remain unresolved for stated non-operational reasons
- **THEN** the summary reconciles all input rows and exits 0 without claiming those rows were imported

#### Scenario: One failed update preserves truthful partial results
- **WHEN** one update is verified and a later operation fails
- **THEN** output identifies the verified update and failed remainder separately and exits 1 without an all-imported message

#### Scenario: Reapplying unchanged history is idempotent
- **WHEN** a prior plan was fully applied and current state is freshly read
- **THEN** every target is unchanged, no mutation is sent, and the run exits 0
