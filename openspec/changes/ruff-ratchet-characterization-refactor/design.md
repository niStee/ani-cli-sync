# Design

## Context and evidence boundary

At pinned main `87314dc54de181b928a49c2711f3783efca5c532`, `scripts/ruff_count_ratchet.py` has 268 lines and `main()` spans lines 165-262. It already implements exact-count equality, monotonic `--update`, optional `--base-ref`, tracked-files-only scope, 200-file batches, E902 exclusion, and distinct exits 0/1/2/3. `tests/test_ruff_ratchet.py` covers the main ratchet paths but not all parsing, batching, output, or external-failure contracts. The committed baseline is `0`.

This package is planning only. No characterization test, mutant, implementation, scanner run, or full suite was executed here. Source inspection and public read-only APIs are evidence; they are not fresh CI or Codacy closure.

## Goals / Non-Goals

**Goals:**
- Pin supported black-box behavior before reducing decision density.
- Make fail-open mutations visible through positive/negative characterization and sensitivity probes.
- Separate historical findings from proof that a future refactor resolves them.

**Non-Goals:**
- New behavior, a canonical spec delta, tool upgrades, a different security policy, blanket suppressions, arbitrary complexity targets, or unrelated test/CI rewrites.

## Historical Codacy evidence, exactly scoped

Read-only PR 53 endpoints, both fetched 2026-10-30:

- Issues: `https://app.codacy.com/api/v3/analysis/organizations/gh/niStee/repositories/ani-cli-sync/pull-requests/53/issues?status=all&limit=100`
- Files: `https://app.codacy.com/api/v3/analysis/organizations/gh/niStee/repositories/ani-cli-sync/pull-requests/53/files?limit=100`

The issues response contains ten rows, all `deltaType: Added`: five Bandit rows in the script, four Bandit rows plus one Opengrep row in its tests. They are subprocess/security-audit patterns, **not ten complexity findings**.

| File:line | Tool / pattern | Severity | Historical observation |
|---|---|---|---|
| `scripts/ruff_count_ratchet.py:30` | Bandit `B404` | Info | `import subprocess` in the PR 53 snapshot |
| `scripts/ruff_count_ratchet.py:70` | Bandit `B603` | Warning | `subprocess.run` for Ruff |
| `scripts/ruff_count_ratchet.py:70` | Bandit `B607` | Warning | partial executable path `ruff` |
| `scripts/ruff_count_ratchet.py:100` | Bandit `B603` | Warning | `subprocess.run` for Git |
| `scripts/ruff_count_ratchet.py:100` | Bandit `B607` | Warning | partial executable path `git` |
| `tests/test_ruff_ratchet.py:4` | Bandit `B404` | Info | `import subprocess` |
| `tests/test_ruff_ratchet.py:24` | Bandit `B603` | Warning | `_git` subprocess call |
| `tests/test_ruff_ratchet.py:24` | Bandit `B607` | Warning | partial executable path `git` |
| `tests/test_ruff_ratchet.py:112` | Bandit `B603` | Warning | `subprocess.run` in the CLI test |
| `tests/test_ruff_ratchet.py:112` | Opengrep `python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit` | Error | test subprocess invocation |

If the raw issue response is used to generate a review appendix, preserve each returned `issueId`, `commitSha`, file, line, tool, pattern, severity, and delta verbatim rather than reconstructing rows by hand. The table is a compact finding census, not a substitute for that raw evidence.

The files response reports eight changed files and these historical deltas:

| File | deltaNewIssues | complexity |
|---|---:|---:|
| `scripts/ruff_count_ratchet.py` | 5 | 51 |
| `tests/test_ruff_ratchet.py` | 5 | 17 |
| `tests/test_ci_config.py` | 0 | 4 |

The script contributes one B404 import, two B603 calls, and two B607 partial-path findings; the tests contribute one B404 import, three B603 calls, one B607 partial-path finding, and one Opengrep audit finding. Do not collapse them into a guessed number of unique conceptual risks. The complexity values are file deltas from that snapshot, not current cyclomatic-complexity measurements and not ten additional findings.

Current local executable evidence is Ruff 0.17.2; `.github/workflows/ci.yml` pins 0.16.10. Therefore local ratchet green alone cannot close CI/scanner findings. Fresh evidence must come from the eventual PR and both versions.

## What the Codacy complexity number actually measures (implementation finding)

The complexity figures above (`51` for the script) are **file-level sums of per-function cyclomatic complexity**, not a single per-file number. The exact metric was decoded from the Codacy PR-files API and validated against seven independent data points (PR 53's three new-file absolute values `51`/`17`/`4`, PR 102's modified-file deltas `5`/`7`/`0`, and PR 105's delta `3`), reproducing all seven exactly.

Per function the score is `1 + count(if, for, async-for, while, except-handler, ifexp) + sum(len(boolop.values) - 1) + count(comprehensions) + count(if carrying an else/elif branch)`, summed over every function in the file. `else` and `elif` branches each cost `+1`; a comprehension costs `+1`; each extra operand of a `and`/`or` costs `+1`.

Two consequences reshape this refactor:

1. **Splitting one function into N functions raises the file total**, because every new function contributes at least `+1`. A decomposition that only relocates decisions cannot lower the number.
2. **Only removing decision points lowers it.** Consolidating a *repeated* check (one branch executed at seven sites) into one shared helper removes six branches and adds one function, so it nets `-5`; relocating a unique branch into a helper nets `0`.

Measured consequence for this file: the `main()` body of the original had complexity `14`; the refactored `main()` has `5`, and the file total moves from `51` to `50`. The local proxy used for these measurements is a fitted reimplementation of the decoded formula, not Codacy's own implementation, so it is directional evidence only. Fresh Codacy evidence remains required by task 3.2 and is the only thing that can close issue #54.

## Supported behavior versus observed defects

Characterization covers documented/intended existing behavior and source-observable failure boundaries. It must not invent a friendlier contract.

| Area | Supported behavior to preserve | Out-of-scope defect, not a new requirement |
|---|---|---|
| Ruff JSON lines | Blank lines ignored; malformed text counted; object diagnostics counted except code `E902`; counts summed | A valid JSON scalar/list/null reaches `record.get` and raises `AttributeError`. Do not silently treat it as malformed or zero in this refactor. A future policy needs its own regression pair. |
| Baseline write | `--update` on a lower count writes decimal count plus one LF and returns 0 | `OSError` from `write_text` propagates rather than becoming exit 2/3. Do not claim graceful handling or add a broad exception swallow here. |
| Process failures | Git/Ruff `OSError` becomes external failure; unexpected Ruff exit forwards stderr and returns 3 | No timeout, executable pinning, or new PATH trust model is added by decomposition. |
| Baseline parsing | Existing integer parsing and malformed/missing handling remain | Do not introduce nonnegative/range validation as incidental refactor behavior. |

Defect reproductions may be recorded in a later issue/change with expected-versus-actual evidence, but are not frozen as desirable behavior and are not fixed under the characterization umbrella.

## Refactor design

Keep public constants and existing helpers importable: tests and local tooling may import `count_diagnostics`, `tracked_files`, `current_count`, `read_baseline`, `write_baseline`, `baseline_at_ref`, `baseline_absent_at_ref`, and exit constants. Preserve their parameters, return types, output streams, and subprocess argv/cwd/capture/check choices.

Use the smallest extraction that separates decisions from effects, for example:

1. A base-ref comparison helper returning an optional terminal result, with no baseline write.
2. A count/baseline evaluation helper returning `(exit_code, should_write)` or a tiny result object only if it simplifies call sites.
3. A thin `main()` that parses arguments, resolves paths, sequences helpers, prints existing messages, and writes only after the evaluation authorizes it.

Names are implementation suggestions, not new public contracts. Do not build a framework, command class, plugin registry, or generalized runner. Keep `_git` and the Ruff invocation byte-for-byte in argv semantics; moving a subprocess call into a generic wrapper can hide findings without reducing risk and is explicitly rejected.

### Implemented shape

The shipped decomposition in `scripts/ruff_count_ratchet.py` is:

- `_git` is **untouched**: same argv, same `capture_output`/`text`/`check=False`, same `except (OSError, subprocess.SubprocessError)` -> `None`.
- `_git_ok(repo_root, *args)` is **new and private**. It calls `_git` and returns the process only when git exited `0`, otherwise `None`. It holds no `subprocess` call of its own, so the Bandit B404/B603/B607 sites stay exactly where they were and no finding is hidden behind a generic wrapper. The seven former call sites each carried `if proc is None or proc.returncode != 0`, which is now stated once. All seven treated a non-zero exit as failure, so the consolidation is behavior-preserving.
- `_base_ref_outcome(repo_root, baseline_path, base_ref) -> int | None` holds the base-ref decision tree. `None` means "the bootstrap case, continue with the normal ratchet"; an `int` is a terminal exit code. It never writes the baseline.
- `_ratchet_outcome(repo_root, baseline_path, update) -> int` holds the count-versus-baseline decision tree and performs the authorized baseline write itself. The write happens **before** the "improved" print, so a failing write leaves stdout empty rather than claiming a lowering that did not happen.
- `main()` parses arguments, resolves paths, sequences the two helpers, and returns. It no longer prints or writes.

Both helpers return plain `int`/`int | None`. No result object or `NamedTuple` was introduced: the write decision is internal to `_ratchet_outcome`, so a `should_write` field would have had no consumer, and a `NamedTuple` would have added a name to the module's public surface for no benefit.

`count_diagnostics` was deliberately **not** rewritten. Its `record.get(...)` call is the pinned uncaught-`AttributeError` defect for non-object JSON, and any "tidier" rewrite of that loop would change that observable.

`current_count` was deliberately **not** rewritten either. Its `if not files: return 0` early return is redundant with the batch generator, but it is the explicit statement that an empty tracked set means zero violations *and* no Ruff invocation, which C04 pins. Removing it would be an unrelated cleanup, not part of this decomposition.

No numeric complexity target is fabricated. The acceptance criterion is preserved behavior plus simpler independently testable decisions; fresh Codacy complexity evidence determines whether the historical issue is actually addressed.

## Black-box characterization matrix

Tests may call existing helpers and `main()` with temporary repositories and stub executables. Assertions target output, exit, files written, argv, and observable return values, not the future helper decomposition. All supported-behavior tests are green before refactor. Red evidence comes from temporary mutants, never from deliberately adding failing behavior tests to unchanged code.

| ID | Positive pair | Negative pair / observable guard |
|---|---|---|
| C01 | Object diagnostics with ordinary codes count | `E902` object does not count; blank lines do not count |
| C02 | Two valid non-E902 objects sum to two | Malformed non-JSON text still counts as one, matching current policy |
| C03 | `git ls-files -z` yields tracked `.py` paths in order | Git failure/OSError returns no usable list, never a directory walk |
| C04 | Empty tracked set returns count 0 without invoking Ruff | A stub that would fail if invoked proves no hidden Ruff call |
| C05 | More than 200 files invokes ordered batches and sums counts | Batch size/argument/cwd mutation is observed; no untracked file enters argv |
| C06 | Ruff exits 0 and 1 both produce parsed counts | Unexpected exit returns external failure and forwards exact stderr once |
| C07 | Ruff `OSError` maps to external failure | It must not be reported as zero violations |
| C08 | Valid integer baseline reads | Missing/malformed baseline produces config failure, not zero |
| C09 | Update on lower count writes exact `N\n` | Equal/higher counts never write |
| C10 | Existing base ref yields integer; absent baseline is distinguished from malformed | Git failure/missing path fails closed, never bootstraps an allowance silently |
| C11 | Explicit `baseline_absent_at_ref` true permits the documented bootstrap path | False, unresolved ref, or present baseline cannot take that path |
| C12 | Equal current/base counts pass comparison | Current greater than base exits 1 before Ruff execution |
| C13 | Current count equal to local baseline exits 0 | Count above baseline exits 1 |
| C14 | Lower count without `--update` exits 1 and preserves file | `--update` lowers baseline and exits 0 |
| C15 | Higher count with `--update` exits 1 and preserves file | Update cannot widen allowance |
| C16 | Ruff external failure exits 3 | It cannot fall through to equality success or update |
| C17 | Baseline config failure exits 2 | Missing/malformed data cannot be treated as zero |
| C18 | Successful comparison emits existing success text on stdout | Regression/config/external messages retain their existing stream and meaning |
| C19 | Custom repo/baseline paths resolve against repo as today | A different resolution rule cannot redirect reads/writes |
| C20 | Main sequences base-ref check before local Ruff count | A base regression prevents an update/write and unnecessary Ruff call |
| C21 | Zero tracked files with zero baseline succeeds | No-files cannot conceal a baseline read or external failure |
| C22 | `--base-ref` bootstrap only applies when explicitly absent at ref | Existing base baseline still enforces monotonicity |
| C23 | Exact output for regression names measured and baseline counts | Refactor cannot replace actionable values with generic prose |
| C24 | Exit constants remain 0/1/2/3 and argparse usage remains usage error | No collapsed nonzero status or fail-open parser fallback |
| C25 | Baseline-at-ref non-integer produces config failure | Malformed base cannot be interpreted as absent |
| C26 | Stderr forwarding leaves stdout unpolluted on external Ruff failure | Error text is not swallowed or duplicated |
| C27 | No baseline write occurs on every non-success path except authorized lower update | File content/hash before/after each failing case proves it |

C01-C27 may be grouped into focused test methods to avoid 54 near-duplicate functions; each row still needs both sides asserted. Existing tests can be retained and extended rather than rewritten for style.

## Sensitivity probes

Apply one temporary source mutation, run the named focused test, observe red, restore exactly, and observe green. Repeat against the refactored version. Never commit a mutant.

| ID | Mutation | Required detector |
|---|---|---|
| S01 | Stop excluding `E902` | C01 negative case fails |
| S02 | Treat tracked-file/Ruff external failure as empty/zero | C03/C07 negative case fails |
| S03 | Change batch size or drop a batch | C05 invocation/count assertion fails |
| S04 | Accept `count < baseline` without update | C14 negative case fails |
| S05 | Allow `--update` to raise/widen baseline | C15 file and exit assertions fail |
| S06 | Collapse config/external exits to success | C16/C17 exit assertions fail |
| S07 | Skip base-ref regression check | C12/C20 call-order, exit, and no-write assertions fail |
| S08 | Swallow or duplicate Ruff stderr | C06/C26 exact stream assertions fail |

A passing test that was never observed red under its mutant is not accepted as a guard. The suite's own detection remains pinned by these explicit mutants; no broad mock-only assertions substitute for behavior.

S09 was added during implementation: `_git_ok` is a guard introduced by the refactor, so it needs its own mutation. It drops the return-code check from `_git_ok` so a non-zero git exit is treated as success, and is detected by `test_c10_unresolved_ref_fails_closed_in_both_helpers`.

## GLM-5.3 characterization brief - after GPT plan approval

Implement only the characterization tests and hermetic fixtures/stubs for C01-C27, using current unittest patterns and temporary repositories. Run them against original code and require green. Perform S01-S08 and record the mutation, focused red result, restoration, and green result. Do not edit production code, canonical specs, baselines, workflows, or scanner configuration. Do not add non-object-JSON/write-error fixes. Freeze tests and evidence for GPT review.

## MiniMax-M3.1-Flash refactor brief - after GPT test review

Refactor only `scripts/ruff_count_ratchet.py` within the agreed extraction boundaries. Keep frozen characterization unchanged; if a test exposes an incorrect test assumption, stop for GPT review rather than editing it to fit. Run focused tests after each step, repeat sensitivity probes, then run the full unit suite and both Ruff-version checks in the later implementation environment. Do not add blanket suppressions, change executable resolution, or hide a finding behind a generic subprocess wrapper.

## Practice review (sources read 2026-10-30)

- Codacy PR 53 issues/files APIs listed above, live historical API responses: **confirmed** ten Added subprocess/security findings and file complexity deltas 51/17/4; **not-officially-verifiable** as current closure because they describe PR 53, not a future head.
- [Python subprocess security considerations](https://docs.python.org/3/library/subprocess.html#security-considerations), current Python 3 documentation without a page publication date: **confirmed** list argv avoids shell semantics while untrusted executable/argument risks remain; decomposition is not a security fix.
- [Bandit B603](https://bandit.readthedocs.io/en/latest/plugins/b603_subprocess_without_shell_equals_true.html), [B607](https://bandit.readthedocs.io/en/latest/plugins/b607_start_process_with_partial_path.html), and [B404](https://bandit.readthedocs.io/en/latest/blacklists/blacklist_imports.html#b404-import-subprocess), current docs without page publication dates: **confirmed** these are audit warnings for process spawn, partial executable paths, and subprocess imports, not proof of ten vulnerabilities.
- [Ruff `output-format` setting](https://docs.astral.sh/ruff/settings/#output-format), current documentation without a page publication date: **confirmed** JSON is a supported machine-readable format; it does not specify this script's malformed-line/E902 policy.
- Repository `ci.yml`, source, tests, and baseline at pinned SHA, read 2026-10-30: **confirmed** CI Ruff 0.16.10 and baseline 0; local `ruff --version` reports 0.17.2, so fresh two-version verification is required.

**Reuse check: adopt.** Reuse `unittest`, existing temporary-repository/stub patterns, subprocess argv, and current ratchet helpers. No characterization framework, mutation package, process abstraction, lint suppression package, or new dependency is needed.

## Risks / Trade-offs

- **Risk:** Tests bless an accidental defect. **Mitigation:** explicit supported/defect table; no new policy for scalar JSON or write errors.
- **Risk:** Characterization is vacuous. **Mitigation:** named temporary mutants with observed red and restored green.
- **Risk:** Refactor changes fail-closed exits. **Mitigation:** black-box exit/output/write/call-order assertions before and after.
- **Risk:** Scanner count is gamed. **Mitigation:** no generic wrapper or blanket suppressions; fresh per-finding evidence required.
- **Risk:** Local Ruff differs from CI. **Mitigation:** run both 0.17.2 and 0.16.10 checks later; do not claim parity now.

## Migration Plan

No user migration, baseline change, config change, or workflow change. Existing command invocations and helper imports remain valid. Any follow-up behavior or hardening change is independently reviewed.

## Traceability

- Parsing/process/base-ref/ratchet behavior: C01-C27, S01-S08, tasks 1.1-1.3.
- Pure decomposition: refactor design and task 2.1; frozen tests/probes in task 2.2.
- Historical Codacy 10 rows and complexity 51/17/4: evidence tables and task 3.2.
- Non-object-JSON/write-error exclusion: supported/defect table and task 3.3.
- Ruff version skew: evidence boundary and task 3.1.
