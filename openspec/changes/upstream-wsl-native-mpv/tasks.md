# Tasks

This is a local tracking-only package. No task below authorizes current implementation, an upstream fork/issue/PR, or live WSL playback. The future evidence and contribution stages require explicit operator approval. GPT orchestrator owns quality gates; GLM-5.3 writes any later tests; MiniMax-M3.1-Flash implements only after GPT test review; final human acceptance remains mandatory.

## 1. Freeze the upstream evidence baseline

- [x] 1.1 (tier: frontier) Read pinned upstream `ani-cli`, `README.md`, `ani-cli.1`, `CONTRIBUTING.md`, PR template, CODEOWNERS, and `ani-cli.yml`, `markdown.yml`, and `version.yml`; verify version 5.1.6, intentional WSL `mpv.exe`, `ANI_CLI_PLAYER` override, existing WSL docs, and applicable CI gates are recorded.
- [x] 1.2 (tier: frontier) Read upstream PRs 1389 and 1478, their patches, and closure comments; verify both proposed Linux-mpv defaults were closed unmerged because the environment override was considered sufficient.

## 2. Reproduce before prescribing (future, operator-approved WSL environment)

- [ ] 2.1 (tier: frontier) Record exact Windows/WSL distribution, ani-cli commit, mpv build and install method, interop settings, PATH, and player configuration; run E01-E08 read-only/player-discovery checks and save expected-versus-actual results without modifying the system or exposing usernames/personal paths in public text.
- [ ] 2.2 (tier: frontier) Run E09-E12 bounded playback/config checks on a controlled local fixture or approved stream, with positive/negative pairs and restoration of temporary configuration; verify full-path invocation, PATH-directory discovery, optional hardware decoding, and actual vo failure semantics instead of generalizing one machine.
- [ ] 2.3 (tier: frontier) Investigate native-Windows ani-skip separately through upstream ani-skip source and a bounded reproduction; verify whether the limitation is the helper, generated Lua path, Windows path translation, or unsupported script loading. Do not bundle a skip implementation with the documentation patch.

## 3. Documentation-first upstream contribution (after evidence and maintainer agreement)

- [ ] 3.1 (tier: frontier) Search current upstream issues/PRs and re-read current master/contribution policy immediately before editing; verify the pinned findings still apply, identify an existing issue or obtain operator approval to open the required upstream issue, and do not reopen the rejected default switch.
- [ ] 3.2 (tier: frontier) Prepare the smallest upstream `README.md` WSL correction/expansion from the accepted evidence: intentional `mpv.exe` default, `ANI_CLI_PLAYER=mpv`, correct executable-directory PATH example, full-path discovery checks, optional `hwdec=auto`, and existing ani-skip Windows warning. Verify no forced `d3d11va`, X11 blacklist, unverified package path, or absolute claim about official-build decoding is introduced.
- [ ] 3.3 (tier: frontier) Review docs against E01-E12 and upstream templates; verify links/whitespace and README/man-page consistency. Do not bump `version_number` for a docs-only patch and do not claim `ani-cli.yml` runs when only Markdown changed.
- [ ] 3.4 (tier: frontier) Have the operator write the human PR sentence and perform final review, disclose the AI model as coauthor as upstream requires, and add no AI-generated code comments or generated PR prose. Any fork/branch/PR is a separately approved external action, not part of this planning package.

## 4. Optional shell follow-up (only if reproduction proves a defect and maintainers request code)

- [ ] 4.1 (tier: frontier) Convert the reproduced defect into a new bounded behavior proposal with GLM positive/negative regression cases, sensitivity probes, and expected POSIX behavior; verify `ANI_CLI_PLAYER` precedence, full-path semantics, error output, non-WSL platforms, and no default-player regression before MiniMax implementation.
- [ ] 4.2 (tier: mid) After GPT test review and maintainer agreement, make the smallest POSIX-shell fix, update version/README/man page as applicable, and run upstream `shfmt`, `shellcheck`, executable-bit/no-awk/no-wget/version checks plus the required human playback checklist. Native ani-skip remains a separate change.

## Workflow follow-up

- Do not apply this change to ani-cli-sync runtime, create upstream state, or run WSL playback during planning.
- If maintainers decline even the documentation patch, retain the local evidence and stop rather than recreating PRs 1389/1478 or expanding into an unsolicited shell feature.
