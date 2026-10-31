# Netflix viewing history import

`ani-cli-sync import-netflix` reconciles a Netflix viewing-history export with
your AniList list. It reads the export, works out which rows refer to which
anime episode, shows you what it would change, and only then changes anything -
and only if you ask it to.

This guide is the end-user reference: how to get the right file, what the tool
sends over the network, what it is allowed to conclude from your rows, what it
changes, what it refuses to change, and how to read its exit status.

---

## Availability: which importer you have

The preview-and-apply behavior described in this guide is the accepted contract
for `ani-cli-sync import-netflix`. It ships with the behavioral change tracked as
[issue #90](https://github.com/niStee/ani-cli-sync/issues/90), together with the
minimum command help and the minimum README section.

An earlier importer existed before that change. It resolved a small curated list
of anime titles, counted matching rows, and wrote to AniList immediately - no
preview, no `--apply`, no per-row dispositions. If you are running a build from
before #90, none of the safety behavior below applies to it.

Always check what your installed build actually offers before relying on any
flag or behavior in this guide:

```bash
ani-cli-sync import-netflix --help
```

If that output does not list `--apply`, your build predates the change and the
preview/apply flow is not available to you yet. The shipped `--help` output is
authoritative for flag spelling and for the exact report format; this guide
describes the accepted contract and the reasons behind it.

---

## What this imports

**In scope:** the per-profile **Viewing activity** CSV that Netflix offers for
download on the Account page. Netflix documents it as a CSV that opens in
spreadsheet software; it does not document the column header, the title
grammar, the date format, or any episode-completion semantics. The importer
therefore supports one specific shape of that file - see
[The supported input contract](#the-supported-input-contract).

**Out of scope:**

- A spreadsheet you re-saved or converted through another program. The importer
  requires the original CSV structure; it does not read `.xlsx`, `.tsv`, or a
  CSV whose header was edited.
- The wider **personal-information archive** you can request from Netflix. That
  is a different product and a different flow. See
  [Export the official CSV](#export-the-official-csv).
- Movies, specials, and named-episode titles. See
  [How titles are matched](#how-titles-are-matched).

### The supported input contract

The importer accepts a UTF-8 CSV with:

- the two header fields `Title` and `Date`, in that order, matched
  case-sensitively;
- an optional UTF-8 byte order mark (BOM);
- either CRLF or LF line endings;
- RFC 4180 quoting, so a title containing a comma, a double quote, or a colon
  survives as one field;
- exactly two fields in every data row;
- a non-blank title and a non-blank date in every data row.

Anything else is rejected before a single API call is made. See
[exit status 2](#read-the-result-and-exit-status).

`Title,Date` is **this project's supported input contract**. Netflix's own help
page documents that the downloaded file is a CSV that opens in spreadsheet
software; it does not document the column header, the title grammar, the date
format, or any episode-completion semantics. Nothing in this guide should be
read as a claim about what Netflix guarantees its export to contain.

### Dates are opaque

The `Date` column is carried as source text and nothing more. The importer does
not parse it, does not interpret it as a locale-specific calendar date, does not
sort by it, and does not build a viewing timeline or a completion narrative from
it. Two rows for the same episode on two different dates are one piece of
evidence, not two.

The only date rule is that a blank or whitespace-only date is invalid input.

---

## Export the official CSV

Netflix documents this flow in
[How to see viewing history and device activity](https://help.netflix.com/en/node/101917).
In a browser:

1. Open your [Netflix Account page](https://www.netflix.com/account).
2. Select **Profiles**, then choose the profile whose history you want to
   import.
3. Open **Viewing activity**.
4. If you see a limited list, use **Show More** until the full list is shown.
5. At the bottom of the page, select **Download all**.
6. Keep the downloaded file somewhere you control.

Step 4 matters. `Download all` is at the bottom of the full list, so if you skip
**Show More** the export may be shorter than you expect.

The command below uses `~/Downloads/NetflixViewingHistory.csv` as an
illustrative path. Netflix does not guarantee a particular filename, and the
importer does not care what the file is called - you pass the path you actually
have:

```bash
ani-cli-sync import-netflix ~/Downloads/NetflixViewingHistory.csv
```

### This is not the personal-information archive

Netflix has a second, broader flow: go to
[account/getmyinfo](https://www.netflix.com/account/getmyinfo) and follow the
instructions to request a copy of the personal information Netflix holds about
you. Netflix states that this can take **up to 30 days** from the date the
request is verified, and that the copy spans far more than viewing history -
account details, payment and billing information, device and access information,
and interaction history.

That archive is **not** supported importer input. It is a different file, in a
different format, covering a different scope. Netflix also points at this flow
for accounts that are no longer active, where viewing activity is no longer
listed directly.

Use the per-profile **Viewing activity** download from step 5 above.

---

## Privacy and network expectations

Your viewing history is personal data. Treat the exported file the way you would
treat any other personal record.

**What is not uploaded**

- The **complete CSV file is not uploaded**. Neither this guide nor the importer
  sends your export as a file to Netflix, to a conversion service, or to any
  third-party tool: the file is read locally and parsed into individual fields.
- The importer parses and validates the whole file before it contacts AniList.
  An invalid file produces no API traffic at all.
- Your AniList credentials are never read from the CSV, never written into it,
  and never printed. Note that the credential itself is not confined to your
  machine: the access token is transmitted to AniList with each authenticated
  request, over HTTPS, so AniList can authenticate you. That is the same
  transport the rest of `ani-cli-sync` uses.

**What leaves your machine**

Parts of the file do travel, in pieces, once the file has been parsed:

- **Title and release text is sent to AniList.** The importer sends the parsed
  title and release context of each row as search queries, plus the
  authenticated current-state reads it needs for the entries it resolved. So
  while the file itself never leaves your machine, the titles inside it do.
- **Preview is not offline mode.** A preview performs those same lookups and
  current-state reads. What it does *not* do is send any mutation. No AniList
  list entry is created, changed, or removed during a preview.
- **Apply recomputes the plan, it does not replay a saved one.** See
  [Preview and apply](#preview-and-apply) for what that means for the changes
  it sends.
- **The printed report contains titles too.** Even a run that changes nothing
  sends the title queries needed to resolve the rows.

**What not to paste**

- Do not commit the export to a repository, including a private one.
- Do not paste a real export, an account identifier, a token, or a full
  command output containing your private titles into an issue, a chat, or a
  screenshot.
- Use synthetic titles in examples and in bug reports. The examples in this
  guide use invented titles for exactly this reason.

**Your local copy**

Keep the export or remove it according to your own privacy needs. This guide
deliberately does not prescribe a deletion command for your files.

---

## Preview and apply

The importer previews by default. A plain invocation resolves everything, shows
every row's disposition, and writes nothing:

```bash
ani-cli-sync import-netflix ~/Downloads/NetflixViewingHistory.csv
```

To actually change AniList, ask for it explicitly:

```bash
ani-cli-sync import-netflix ~/Downloads/NetflixViewingHistory.csv --apply
```

An `--apply` run is a fresh run, not a replay of an earlier preview:

- **It recomputes the plan from the file you give it.** The previous preview is
  not stored and not bound to this invocation. The plan it builds may differ
  from the preview you saw earlier, because the file may have changed and
  because AniList's state may have changed.
- **It reports the changes it now plans**, and it re-checks each target
  immediately before touching it. A target whose fresh state makes the planned
  change unsafe is skipped and reported, not forced through.
- **It performs the same lookups and current-state reads** a preview performs.
  The difference is that it also sends the mutations it settled on.

Two things to keep in mind about `--apply`:

- **It is not a force flag.** It authorizes the plan this run computes. It does
  not override the guards.
- **It is consent to inference.** The progress and completion numbers the
  importer proposes are inferences from recorded viewing events. Authorizing
  them does not upgrade the evidence into verified playback.

A header-only file (a valid CSV with no data rows) is a normal, complete run:
zero events, no mutations, exit 0.

---

## How titles are matched

### The episode marker

A row title only becomes an episode event when the **whole** title, after
trimming surrounding whitespace, matches this shape:

```text
<release context>: Episode <number>
```

The `:` delimiter and the word `Episode` are matched case-sensitively. The
number is a positive decimal integer with no leading zero. Nothing may follow
the number.

Everything before the delimiter is the **release context**, and it is kept
whole. A colon-rich franchise is never split at its first colon.

| Row title | Release context | Episode evidence |
|---|---|---|
| `Chrono Academy: Eclipse: Episode 1` | `Chrono Academy: Eclipse` | Episode 1 |
| `Chrono Academy: Eclipse: Season 2: Episode 3` | `Chrono Academy: Eclipse: Season 2` | Episode 2 season, episode 3 |
| `Chrono Academy: Part 2: Episode 4` | `Chrono Academy: Part 2` | Part 2, episode 4 |

A `Season N` or `Part N` marker that is explicitly present in the context is
preserved as evidence. Its **absence stays absence** - the importer does not
invent `Season 1` or `Part 1`.

Titles that do not fit the shape stay unresolved, and the importer says so
rather than guessing:

| Row title | Why it is unresolved |
|---|---|
| `Chrono Academy: Episode 3: The Name` | Text follows the episode number |
| `Chrono Academy` | No episode marker |
| A movie title | Not an episode form |
| A special | Not an episode form |

Named-episode mapping is not supported. A row whose title carries an episode
*name* instead of a number contributes no positional progress.

### Choosing the AniList entry

Matching the release context against AniList is deliberately strict:

- **Exactly one candidate must fit.** The importer looks at the plausible
  AniList candidates for the release context and accepts only a single
  context-consistent match. No match, several plausible matches (a remake, a
  film, two seasons), or a candidate whose qualifiers contradict the row all
  produce a visible unresolved or ambiguous disposition.
- **No first-result picking.** The importer never takes the top search hit and
  never falls back on generic substring popularity.
- **Missing season text is not season-one evidence.** If the row says
  `Chrono Academy: Eclipse` with no season, the importer does not conclude
  "Season 1", and it does not strip a candidate's `Season 2` qualifier to make
  a match.
- **An unqualified row may match an unqualified candidate.** That is allowed
  without the importer assigning a season number to it.

### Deduplication

Two rows that resolve to the same anime **and** the same episode number are one
piece of evidence, however many dates they carry. Every source row is still
reported, so nothing disappears from the reconciliation - the duplicate rows are
accounted for, they just do not count twice.

### Lookup failure is not "no match"

These are different outcomes and the report keeps them apart:

- A lookup that **completed** and found nothing is an **unmatched** row. That is
  a normal result, not an error.
- A lookup that **failed** (transport error, an API error returned with a
  success status, an unreadable response, or missing data) is an **operational
  failure**. It is never reported as "no match", and a failed read never
  authorizes a write.

---

## What counts as progress evidence

This is the part worth reading carefully, because it is where a wrong number
would be most annoying.

**Progress is proposed only from exact contiguous coverage.** If the distinct
episode numbers resolved for a release are exactly `1, 2, ..., N`, then progress
`N` may be proposed.

| Episodes seen for one release | Result |
|---|---|
| 1, 2, 3 | Progress 3 may be proposed |
| 8 only | Blocked. No progress proposal for this release |
| 1, 2, 4 | Blocked. The gap at 3 blocks the whole release |

The blocked cases are blocked **as a whole**. The importer does not quietly
propose `1` for the `{1, 2, 4}` case, and it does not propose `8` for the
late-only case. If the evidence for a release is not a clean run from episode 1,
that release gets no positional progress at all.

**Counts, highest numbers, and dates never establish progress.** "I watched 12
rows", "the highest episode I saw was 12", and "the dates are in order" are all
rejected as substitutes for coverage. The highest episode in a set is not the
progress you are at.

**This is inference, not verification.** The importer is reading a record of
viewing events. It cannot tell you whether an episode was watched to the end,
whether it was skipped, or whether the row reflects a play, a resume, or a
removal from the list. Every proposed number is labelled as an inference from
recorded events.

### Completion

Completion needs **two** things:

1. Exact coverage `1..T` for the release, and
2. A **known positive total** `T` for that release.

If the total is unknown, zero, or negative, the importer will still propose
progress from a clean `1..N` run, but it will not propose completion. Neither a
row count nor the highest episode number can complete an entry on its own.

A completion proposal is still labelled as an inference, and it still requires
`--apply` to be carried out.

---

## Which entries may change

The status policy is intentionally narrow. Here is the whole of it.

**Absent entry** (nothing on your AniList list for that anime)

- May be created, and only as `CURRENT`, at the inferred progress.
- Even when the inferred progress equals the known total, the new entry is
  created as `CURRENT`. A new entry is never created directly as `COMPLETED`.

**Existing `CURRENT` entry**

- May have its progress increased.
- May be proposed for `COMPLETED` only with exact `1..T` coverage of a known
  positive total `T`. The proposal is labelled as an inference and needs
  `--apply`.
- A status-only completion is allowed when the freshly read progress already
  equals `T`.
- Progress above `T` blocks the planned change. The importer will not lower
  progress to fit.

**Every other existing status** - `PLANNING`, `PAUSED`, `DROPPED`, `REPEATING`,
and `COMPLETED`

- Is left exactly as it is. The importer reports a status-policy skip or an
  unchanged disposition and touches neither progress nor status, even with full
  coverage.

**Never, in any case**

- Reopening a `COMPLETED` entry.
- Regressing progress.
- Converting a status you set deliberately into a different one.

---

## Read the result and exit status

### What the report covers

Every input data row appears in the result with a stated reason. The summary
reconciles against the number of input rows, so the counts add up.

Each row's report carries the information needed to judge it:

| Field | What it tells you |
|---|---|
| Source row number and title | Which row of your CSV this is |
| Date metadata | The date text as it appeared in the file, kept as text |
| Deduplication target | Which anime and episode the row resolved to, and whether it merged with another row |
| Mapping evidence | Which release context, season or part, and episode number were preserved, and what the candidate match was based on |
| Planned, current, and target progress and status | What is on AniList now and what the plan would do |
| Inference label, skip reason, or failure reason | Why a proposal was made, why it was skipped, or why it failed |

The exact labels and layout are set by the implementation's report format. The
table above describes the fields, not the printed strings. An approximate shape
of a single row's entry, illustrative only:

```text
    row 7  | Chrono Academy: Eclipse: Season 2: Episode 3
           | date metadata: (kept as text, not interpreted)
           | resolved: <single AniList candidate>  episode 3
           | evidence: explicit Season 2; explicit Episode 3
           | current:  CURRENT, progress 2
           | proposal: inferred progress 3  (inference from recorded events)
```

Two things the report will not do:

- It will not print an "all imported" success line when rows were unresolved or
  failed. Skipped rows are skipped, not imported.
- It will not describe an inferred number as verified playback.

### Exit status

| Exit | Meaning | What to do |
|---|---|---|
| 0 | Processing completed. This includes runs with unresolved, ambiguous, duplicate, unchanged, or insufficient-evidence skips | Read the dispositions. Zero does **not** mean every row was imported |
| 1 | Operational, partial, or unverified apply failure | Read verified and failed targets separately. Correct the cause before rerunning |
| 2 | Usage or input validation failure | Fix the path, encoding, header, row shape, title, or date. No API operation should have occurred for invalid input |

Precedence is fixed: input problems are detected before anything else, so
**2 wins**. Then, if any operational failure or unverified/partial apply
occurred, the run exits **1**. Otherwise it exits **0**.

Exit 2 covers, among others: a missing or unreadable path, a file that is not
UTF-8, a header that is not exactly `Title,Date`, a row with the wrong number
of fields, malformed quoting, a blank title, and a blank or whitespace-only
date.

---

## Repeats, partial runs, and idempotence

### Fresh state is re-read, but the write is not atomic

Immediately before each planned mutation, the importer reads the current AniList
state again. If that fresh read shows the change is no longer safe - the
progress has already moved up, or the status is one the policy does not allow
changing - the mutation is skipped and the target is reported as unchanged or
stale. A fresh read that *fails* blocks that target's update entirely; the
importer does not treat an unknown state as permission to write.

The final check and the write are **not atomic**. AniList's mutation interface
offers no expected-current-state or version condition for this operation, so a
remote change landing between the read and the write can still race the update.
The importer reduces that risk; it does not eliminate it, and it does not claim
to.

### Reruns are safe

- A plan that was applied in full and is rerun against fresh state reports
  every target as unchanged, sends no mutation, and exits 0.
- Repeated view dates do not inflate progress. The same episode on five dates
  is one episode.
- After a partial apply, the updates that were verified stay applied. There is
  no cross-entry rollback, and no attempt to undo the ones that succeeded.
- Rerunning reconciles against current state again, so it is the right way to
  finish a run that stopped partway.
- Rows that stayed unresolved or ambiguous stay that way on a rerun until the
  underlying cause is fixed. A rerun does not resolve them for you.

### A preview proves nothing about a later write

A preview shows a plan. It does not verify that a later `--apply` succeeded, and
an `--apply` run does not verify that a preview was correct - it computes its
own plan. The apply run's own report and exit status are what tell you what
actually happened.

---

## Limitations

- **One export source.** The per-profile Viewing activity CSV, and only that
  shape. The wider personal-information archive is not supported.
- **No manual mapping.** There is no mapping file, mapping UI, or override
  table. Unmatched and ambiguous rows are reported, not patched.
- **No movies or specials.** Only the episode form above produces progress.
- **No named episodes.** A title carrying an episode name instead of a number
  is unresolved.
- **No scraper offsets.** Imported progress is AniList episode numbering.
- **Not atomic.** Fresh reads reduce, but do not remove, the race described
  above.

---

## Related

- [Issue #90](https://github.com/niStee/ani-cli-sync/issues/90) - the behavioral
  change that defines preview, apply, evidence, status policy, and exit codes.
- [Issue #88](https://github.com/niStee/ani-cli-sync/issues/88) - this guide.
- [Netflix: how to see viewing history and device activity](https://help.netflix.com/en/node/101917)
- [Netflix: what personal information Netflix holds about you and how to request a copy](https://help.netflix.com/en/node/100624)
