# Proposal

## Why

[Issue #91](https://github.com/niStee/ani-cli-sync/issues/91) records one user's WSL2/native-Windows mpv experience and asks for upstream ani-cli improvements. Pinned upstream source already documents basic WSL setup and selects `mpv.exe` deliberately, while two attempts to replace that default with Linux `mpv` were closed unmerged. The useful next contribution is therefore a verified correction and expansion of existing documentation, not another default-switch proposal.

The current evidence is insufficient to prescribe a universal full-path failure, mandatory hardware decoder, X11 guard, or ani-skip code change. Those claims need real WSL reproduction and maintainer agreement before becoming implementation requirements.

## What Changes

- Keep a local, bounded upstream-contribution plan grounded in upstream commit `0301d67d5768d332b049821a30082ad43d9a215a`.
- Prepare a future documentation-first patch that expands the existing WSL section with correct PATH-directory, full-path, Linux-player override, and optional `hwdec=auto` guidance.
- Define an evidence matrix for full paths, PATH discovery, player flags, and native-Windows ani-skip behavior before any shell change is considered.
- Preserve the intentional WSL `mpv.exe` default and the existing `ANI_CLI_PLAYER=mpv` escape hatch.
- Respect upstream's contribution, AI-authorship, PR-description, and human-review requirements.

## Capabilities

### New Capabilities

None in ani-cli-sync.

### Modified Capabilities

None. This package tracks a possible contribution to the separate upstream `pystardust/ani-cli` project and sets `skip_specs: true`. It does not change this repository's Python behavior or canonical specifications.

## Impact

Only this OpenSpec planning package is added now. A future, separately approved upstream patch would target upstream `README.md` first. Upstream `ani-cli`, `ani-cli.1`, contribution issues, forks, branches, or PRs are not changed by this package.

## Out of scope

Changing the WSL default to Linux `mpv`, forcing `d3d11va`, inventing an X11/Wayland blacklist, weakening dependency checks without evidence, implementing native-Windows skip support, creating an upstream fork/issue/PR, running live WSL playback, or changing ani-cli-sync Python/tests. Final human acceptance remains mandatory before any external contribution or live test.
