# Design

## Context and evidence boundary

Issue #91 describes ani-cli 5.1.6 on WSL2 with a native Windows mpv CI/MSVC build. This planning session did not reproduce that environment, run WSL, launch mpv, install packages, or exercise ani-skip. All runtime observations in the issue are reporter evidence, not independently confirmed behavior.

The upstream evidence baseline is commit `0301d67d5768d332b049821a30082ad43d9a215a` of `pystardust/ani-cli`, also version 5.1.6. Raw pinned files and public GitHub API responses were read on 2026-10-30. A future contribution must rebase its evidence onto then-current upstream master; the pin makes this plan reviewable, not permanently current.

## What pinned upstream already does

| Surface | Confirmed behavior/content | Consequence |
|---|---|---|
| Platform selection | `*MINGW* \| *WSL2*) player_function="${ANI_CLI_PLAYER:-mpv.exe}"` | Native `mpv.exe` is intentional; `ANI_CLI_PLAYER` already takes precedence. Do not propose Linux `mpv` as the new default. |
| Player dependency | `dep_ch "$player_function"` uses `command -v "$1"` and exits when discovery fails | Full-path behavior needs actual POSIX-shell/WSL evidence; no premature `-e`/`-x` fallback. |
| Player flags | `player_extra_flags="${ANI_CLI_PLAYER_FLAGS:-""}"`; mpv branch also passes referrer, title, and skip flags | User flags are already supported; hardware and vo guidance belongs in docs unless a separate defect is proven. |
| WSL README | Existing section explains Windows mpv, ensures `mpv.exe` is on PATH, shows `export ANI_CLI_PLAYER=mpv`, and warns that ani-skip does not work on Windows | Expand/correct this section rather than claiming WSL documentation is absent. |
| Man page | Says the default is mpv everywhere except named special platforms and does not document the WSL exception | A docs patch should consider this existing imprecision; no broad option rewrite is needed. |
| Upstream PR 1389 | 2024-08-02 proposal changed WSL to Linux `mpv`; closed unmerged 2024-08-08 after maintainers called it unnecessary and cited the override | Recreating it is not a credible contribution path. |
| Upstream PR 1478 | 2025-01-23 proposal again changed WSL to Linux `mpv`; closed unmerged 2025-02-26 with the same override guidance | Preserve the default and document selection instead. |

## Corrections to issue #91's proposed workaround

1. **PATH must contain the directory, not the executable filename.** If `MPV_WIN=/mnt/c/.../mpv.exe`, then `PATH="$MPV_WIN:$PATH"` is wrong. Use an independently verified install-directory variable, for example `MPV_WIN_DIR=/mnt/c/path/to/mpv-directory`, then `PATH="$MPV_WIN_DIR:$PATH"`. Keep the full executable path separately as `ANI_CLI_PLAYER="$MPV_WIN"` only if discovery and invocation are verified.
2. **The README already has WSL instructions and a Windows ani-skip warning.** The contribution is a focused correction/expansion, not a new claim of total documentation absence.
3. **Hardware decoding is optional configuration, not a universal ani-cli default.** mpv documents `hwdec=auto` as enabling any available hardware decoding and recommends `auto`/`auto-safe`/`auto-copy` over a fixed method unless a specific method is required. Offer `hwdec=auto` as the portable first example; keep `d3d11va` as a verified Windows-specific alternative, never forced by ani-cli.
4. **No X11/Wayland blacklist.** A particular native build may omit those backends, but ani-cli should not parse and reject arbitrary user flags. Document checking the selected build's supported outputs and remove incompatible user configuration; do not generalize a build-specific crash into shell policy.
5. **ani-skip is separate.** The pinned README already warns it does not work on Windows. Do not mix a helper/Lua/path-translation fix into WSL player-discovery documentation.

The issue's exact winget package ID, install path, default software decoding, X11 crash, full-path behavior, and end-to-end GPU log remain unverified here. Public examples must use placeholders and verified discovery commands, never a machine-specific package path presented as stable.

## Documentation contribution shape

The preferred future patch edits only upstream `README.md` and possibly makes the existing man-page default-player sentence precise if maintainers request it. It should be short enough to satisfy upstream's "keep it brief" guidance.

Proposed content contract, not final upstream prose:

- State that WSL intentionally defaults to native Windows `mpv.exe`; Linux mpv is opt-in through `export ANI_CLI_PLAYER=mpv`.
- Explain that WSL interop and Windows PATH appending are configurable; use `command -v mpv.exe` as a discovery check rather than assuming every installation is visible.
- Show a correct PATH-directory example and a separate full-path `ANI_CLI_PLAYER` example only after E01-E08 confirm them on supported WSL/shell combinations.
- Explain that `ANI_CLI_PLAYER_FLAGS` is passed to the selected player. If hardware decoding is wanted, try `hwdec=auto` in the native Windows mpv configuration or as an optional player flag; do not require a specific GPU backend.
- Retain the existing Windows ani-skip warning and point to a separate investigation/change rather than implying the documentation makes skip work.
- Avoid prescribing X11/Wayland flags for a native Windows build. Refer to the selected mpv build's own supported-output diagnostics, verified in the reproduction stage.

No runtime code or version bump belongs in a docs-only PR. Upstream's version workflow is path-filtered to `ani-cli`; the contribution guide's "bump the version" applies when the script changes, not as a reason to create a fake version delta for Markdown.

## Evidence matrix for future reproduction

Run these only in an operator-approved WSL environment. E01-E08 are discovery/read-only checks; E09-E12 are bounded player/config tests with saved and restored configuration. Public evidence uses `$USER`, `/mnt/c/Users/<user>/...`, and counts/exit codes, never personal paths.

| ID | Check / positive path | Negative or comparison path | Required evidence before docs/code |
|---|---|---|---|
| E01 | Record `uname -a`, WSL version/distribution, ani-cli SHA/version | Compare against pinned `*WSL2*` match; no silent assumption all WSL is WSL2 | Exact platform tuple and matched branch |
| E02 | `command -v mpv.exe` with interop and Windows PATH enabled | Same check with a controlled PATH lacking the install directory | PATH directory list, exit status, resolved path shape |
| E03 | `command -v "$ANI_CLI_PLAYER"` for a verified executable full path | Missing file, non-executable, directory-only, and path-with-spaces cases | Shell/WSL behavior; whether a real `dep_ch` defect exists |
| E04 | `ANI_CLI_PLAYER=mpv` selects Linux mpv when installed | No Linux mpv installed produces the existing actionable dependency error | Override precedence and no fallback confusion |
| E05 | Add the executable's **directory** to PATH and resolve bare `mpv.exe` | Add the full filename to PATH and show it does not provide equivalent discovery | Correct docs example and negative control |
| E06 | Bare/default selection uses native `mpv.exe` | Explicit Linux/full-path selection takes precedence | No default change is needed for the workaround |
| E07 | Record selected mpv version/build features and supported vo/hwdec lists | Compare another install method/build if available | Build-specific versus universal claim boundary |
| E08 | Capture baseline `ANI_CLI_PLAYER_FLAGS` and native mpv config locations actually used | Unset/empty flags and absent config comparison | Avoid attributing user config to ani-cli defaults |
| E09 | Controlled playback with default decode configuration | Same fixture with `hwdec=auto`; optional `d3d11va` only if supported | Actual decoder selected, logs, exit status, no "required" claim without comparison |
| E10 | Controlled playback with a supported video output | Unsupported `--vo=x11` only as a contained negative check if the build omits it | Actual error semantics; no new ani-cli blacklist inferred |
| E11 | Basic next/previous/replay/continue behavior under selected player | Early close/nonzero player result distinguished from normal exit | Required human PR checklist evidence if code changes |
| E12 | Existing `--skip` behavior with native Windows player | Linux-player comparison and no-skip control | Isolate ani-skip/Lua/path failure; separate follow-up decision |

A discovery check must not be represented as playback verification. If the operator cannot provide WSL evidence, the package remains planning-only and no external contribution is made on the strength of issue #91 alone.

## Decision gates

1. **GPT plan gate:** accept the docs-first scope and reject a repeat default-switch PR.
2. **Evidence gate:** E01-E08 support any discovery/path prose; E09-E12 support decoder/vo/ani-skip statements. Unsupported claims are removed, not labelled as verified.
3. **Maintainer gate:** current upstream search plus issue/discussion agreement on the proposed docs. Code requires a reproduced defect and explicit maintainer request.
4. **Test gate:** any later shell behavior change gets GLM-written positive/negative POSIX regression tests and sensitivity probes before MiniMax implementation, with GPT test review. Documentation-only work does not invent a fake red test.
5. **Human contribution gate:** operator approves external writes, writes the PR description in human prose, reviews all AI-assisted edits, and ensures model coauthorship as required upstream.
6. **Final acceptance:** upstream maintainers and the operator decide acceptance; local plan completion is not upstream adoption.

## Upstream workflow constraints actually read

Pinned `CONTRIBUTING.md` requires:

- `shfmt -i 4 -ci -d -w ani-cli` and `shellcheck -s sh -o all -e 2250 ani-cli` for shell changes;
- version bump, applicable README update, no unnecessary dependencies, POSIX/cross-platform portability, and an issue for a fix;
- no AI-written code comments and no AI-generated PR descriptions; a human sentence or blank description is required;
- AI model coauthorship, careful steering/review, and no low-effort fully generated PR.

Pinned CI adds:

- `ani-cli.yml`: Shellcheck/Shfmt, executable bit, no awk, and no wget for changes to `ani-cli`;
- `version.yml`: a version delta for changes to `ani-cli`;
- `markdown.yml`: dead-link and trailing-whitespace checks for Markdown changes;
- PR template: core playback/history/download/episode/quality/syncplay/vlc/dub checks plus docs updates, with ani-skip/no-detach/exit-after-play as additional cases;
- CODEOWNERS: upstream owners review `ani-cli` and `README.md`.

These requirements are not optional local CI commands to run now; they are gates for the future upstream patch. Do not claim upstream checks ran against this local planning package.

## Delegation briefs for a future approved contribution

### GLM-5.3 - evidence/tests only

Given reproduced WSL evidence and an approved shell behavior proposal, write black-box positive/negative cases for player selection, full-path discovery, PATH-directory resolution, override precedence, error text, and non-WSL regression. Include sensitivity mutants for any new guard. For docs-only work, instead audit each statement against E01-E12 and the pinned/current docs; do not manufacture runtime tests.

### MiniMax-M3.1-Flash - implementation only after review

For a docs-only accepted scope, apply the smallest human-reviewed README/man-page wording change and run applicable Markdown checks. For an approved shell follow-up, implement only the reviewed POSIX diff, preserve the intentional default and override, bump version, run upstream shell/version checks, and leave playback acceptance to the operator. Never create upstream issues/forks/PRs autonomously and never add AI-written comments or generated PR prose.

## Practice review (sources read 2026-10-30)

- Pinned upstream [`ani-cli`](https://raw.githubusercontent.com/pystardust/ani-cli/0301d67d5768d332b049821a30082ad43d9a215a/ani-cli), [`README.md`](https://raw.githubusercontent.com/pystardust/ani-cli/0301d67d5768d332b049821a30082ad43d9a215a/README.md), [`ani-cli.1`](https://raw.githubusercontent.com/pystardust/ani-cli/0301d67d5768d332b049821a30082ad43d9a215a/ani-cli.1), [`CONTRIBUTING.md`](https://raw.githubusercontent.com/pystardust/ani-cli/0301d67d5768d332b049821a30082ad43d9a215a/CONTRIBUTING.md), [PR template](https://raw.githubusercontent.com/pystardust/ani-cli/0301d67d5768d332b049821a30082ad43d9a215a/.github/PULL_REQUEST_TEMPLATE.md), and workflows [`ani-cli.yml`](https://raw.githubusercontent.com/pystardust/ani-cli/0301d67d5768d332b049821a30082ad43d9a215a/.github/workflows/ani-cli.yml), [`markdown.yml`](https://raw.githubusercontent.com/pystardust/ani-cli/0301d67d5768d332b049821a30082ad43d9a215a/.github/workflows/markdown.yml), [`version.yml`](https://raw.githubusercontent.com/pystardust/ani-cli/0301d67d5768d332b049821a30082ad43d9a215a/.github/workflows/version.yml): **confirmed** current-at-pin selection, docs, override, skip warning, and contribution/CI constraints.
- Upstream [PR 1389](https://github.com/pystardust/ani-cli/pull/1389), created 2024-08-02/closed 2024-08-08, and [PR 1478](https://github.com/pystardust/ani-cli/pull/1478), created 2025-01-23/closed 2025-02-26, including API patches and closure comments: **confirmed** both Linux-default changes were unmerged and maintainers recommended `ANI_CLI_PLAYER`; **wrong** to present either as support for changing the default again.
- [mpv stable manual, `hwdec`](https://mpv.io/manual/stable/#options-hwdec), live manual without a page publication date: **confirmed** `auto` enables any available hwdec and the manual recommends auto modes over fixed methods absent a specific need; **needs-precision** for the issue's claim that every official native build defaults to CPU decoding on every machine.
- [Microsoft WSL advanced settings](https://learn.microsoft.com/en-us/windows/wsl/wsl-config), dated 2026-10-16: **confirmed** `interop.enabled` and `appendWindowsPath` both default to true and control Windows-process launching/PATH appending; local shell startup files can still alter PATH, so discovery must be checked.
- [Microsoft WSL filesystem/interop guidance](https://learn.microsoft.com/en-us/windows/wsl/filesystems), source metadata dated 2021-09-27 and live page updated 2026-06-02: **confirmed** WSL can run Windows `.exe` tools from Linux and arguments are passed to the binary; it does not prove every mpv installation/path works unchanged.
- [Issue #91](https://github.com/niStee/ani-cli-sync/issues/91), created 2026-10-23: **needs-precision** as a single-machine report; **not-officially-verifiable** here for its playback, package, decoder, X11, full-path, and ani-skip claims because no WSL reproduction was performed.

**Reuse check: contribute.** Reuse upstream's existing WSL section, `ANI_CLI_PLAYER`, `ANI_CLI_PLAYER_FLAGS`, `command -v` discovery, and mpv's own `hwdec=auto` support. Contribute a small upstream documentation correction after evidence and maintainer agreement. Do not fork behavior into ani-cli-sync, wrap upstream player selection, or build a parallel WSL compatibility layer.

## Risks / Trade-offs

- **Risk:** Repeating rejected PRs. **Mitigation:** preserve `mpv.exe`; docs first; maintainer gate.
- **Risk:** Publishing an incorrect PATH workaround. **Mitigation:** directory-versus-file correction and E02/E05 negative control.
- **Risk:** Overgeneralizing one GPU/build. **Mitigation:** optional `hwdec=auto`, build-specific evidence, no forced d3d11va or X11 blacklist.
- **Risk:** An unnecessary dependency-check patch. **Mitigation:** prove full-path failure across the actual shell/WSL environment before proposing code.
- **Risk:** Violating upstream AI policy. **Mitigation:** human PR prose, model coauthor, no AI comments, careful human review, minimal diff.
- **Risk:** Scope growth into skip support. **Mitigation:** retain the existing warning and track ani-skip separately.

## Migration / rollout

No ani-cli-sync migration or rollout. Any upstream contribution starts from a fresh current-master read after approval. A docs-only PR has no runtime migration; a later shell patch has its own tests, version bump, docs, and human playback acceptance. If evidence or maintainer feedback rejects the proposal, stop with no external changes.

## Traceability

- Intentional default and existing override: upstream evidence table, decision gate 1, tasks 1.1-1.2 and 3.2.
- Correct PATH/full-path guidance: corrections 1, E02-E06, tasks 2.1 and 3.2.
- Optional `hwdec=auto`, no forced d3d11va/X11 blacklist: corrections 3-4, E07-E10, task 3.2.
- Separate native ani-skip investigation: correction 5, E12, tasks 2.3 and 4 boundary.
- Upstream contribution/CI/AI rules: workflow section, tasks 3.1-3.4 and 4.2.
- No current runtime/external action: proposal impact/out-of-scope and tasks preamble.
