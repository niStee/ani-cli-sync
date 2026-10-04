#!/usr/bin/env python3
"""Whole-repo ruff violation-count ratchet.

The repository had no lint enforcement in CI at all: ruff ran only through the local
pre-commit hook, which is not a required status check and does not run in CI. Eighteen
pre-existing findings therefore meant nothing was gated, and a PR could add findings
freely.

Clearing eighteen findings is a separate campaign. This freezes the debt instead.

Design notes, each of which is a failure mode this gate has to avoid:

* The measured count must **equal** the baseline, not merely be below it. A gate that
  only fails on an increase lets an unrecorded decrease leave slack that absorbs a later
  regression.
* The baseline may only fall, and only via ``--update``. ``--base-ref`` additionally
  fails a PR that widens the allowance in the same commit that adds the findings.
* Scope is **git-tracked** Python files, never a directory walk. A walk also visits
  untracked scratch, nested worktrees and vendored caches that happen to be on disk,
  which reports phantom regressions that do not exist in CI.
* Exit codes are distinct: ``2`` is a config error and ``3`` is an external failure, and
  neither is ever reported as "no regression". A ratchet that fails open is worse than
  no ratchet.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_REGRESSION = 1
EXIT_CONFIG = 2
EXIT_EXTERNAL = 3

BASELINE_NAME = "ruff_count_baseline.txt"
SCAN_GLOBS = ("*.py", "*.pyi")
_IO_ERROR_CODE = "E902"


def count_diagnostics(stdout: str) -> int:
    """Count violations in a batch of ruff json-lines output.

    A line we cannot parse is counted rather than dropped: the count is the metric this
    gate defends, so an unparseable diagnostic must never silently lower it.
    """
    total = 0
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            total += 1
            continue
        # A file-access failure is an environment problem, not lint debt. Counting it
        # would turn a deleted-but-tracked file into a phantom count change.
        if record.get("code") == _IO_ERROR_CODE:
            continue
        total += 1
    return total


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def tracked_files(repo_root: Path) -> list[str] | None:
    """Tracked Python files, or None when the scan cannot run."""
    proc = _git(repo_root, "ls-files", "-z", "--", *SCAN_GLOBS)
    if proc is None or proc.returncode != 0:
        return None
    files = [f for f in proc.stdout.split("\0") if f]
    return files


def current_count(repo_root: Path) -> int | None:
    """Total tracked-file ruff violations, or None when the scan could not run."""
    files = tracked_files(repo_root)
    if files is None:
        return None
    if not files:
        return 0

    total = 0
    for batch in (files[i : i + 200] for i in range(0, len(files), 200)):
        try:
            proc = subprocess.run(
                ["ruff", "check", "--output-format", "json-lines", "--", *batch],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        # ruff exits 1 when violations exist and 0 when clean. Both are valid results.
        if proc.returncode not in (0, 1):
            sys.stderr.write(proc.stderr)
            return None
        total += count_diagnostics(proc.stdout)
    return total


def read_baseline(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def write_baseline(path: Path, value: int) -> None:
    path.write_text(f"{value}\n", encoding="utf-8")


def baseline_at_ref(repo_root: Path, ref: str, baseline: Path) -> int | None:
    """Baseline recorded at ``ref``, or None when it cannot be read.

    Without this the ratchet is one-sided: it fails only when the count exceeds the
    baseline, so raising the baseline in the same commit that adds the violations would
    pass as an improvement. Comparing against a ref is what makes the baseline monotonic
    rather than advisory.

    ``ls-tree`` is used deliberately. On git 2.43, ``cat-file -e`` and
    ``rev-parse --verify`` both answer 128 for a path that is merely absent and for a path
    expression git refuses outright, so an absent baseline and a bad ref are
    indistinguishable. ``ls-tree`` exits 0 with empty output for an absent path and
    non-zero for a name it will not look up.
    """
    resolve = _git(repo_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if resolve is None or resolve.returncode != 0:
        return None
    try:
        rel = baseline.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None
    proc = _git(repo_root, "ls-tree", ref, "--", rel)
    if proc is None or proc.returncode != 0:
        return None
    if not proc.stdout.strip():
        return None
    proc = _git(repo_root, "show", f"{ref}:{rel}")
    if proc is None or proc.returncode != 0:
        return None
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return None


def baseline_absent_at_ref(repo_root: Path, ref: str, baseline: Path) -> bool:
    """True when ``ref`` resolves but records no baseline file yet.

    This is the bootstrap case: the PR that introduces the ratchet is also the PR that
    adds its baseline, so the base branch has none and there is no earlier value that
    could be raised. Comparing against a ref older than the gate is not an error, it is
    the first run.

    The read is an allowlist on purpose. A gate that treats any git error as "nothing to
    compare against" would fail open on a typo'd ref or a missing git binary, which is
    the one outcome a ratchet must never produce.
    """
    resolve = _git(repo_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if resolve is None or resolve.returncode != 0:
        return False
    try:
        rel = baseline.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return False
    proc = _git(repo_root, "ls-tree", ref, "--", rel)
    if proc is None or proc.returncode != 0:
        return False
    return not proc.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repository root (default: cwd)")
    parser.add_argument("--baseline", default=None, help="Baseline count file")
    parser.add_argument("--update", action="store_true", help="Lower the baseline when the count improved")
    parser.add_argument("--base-ref", help="Git ref to compare the baseline against")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    baseline_path = (
        Path(args.baseline).resolve()
        if args.baseline
        else (repo_root / "scripts" / BASELINE_NAME)
    )

    if args.base_ref and baseline_path.is_file():
        if baseline_absent_at_ref(repo_root, args.base_ref, baseline_path):
            print(
                f"bootstrap: {args.base_ref} records no baseline yet, so there is no "
                "earlier value to raise. The one-directional check starts once this "
                "baseline lands."
            )
        else:
            base = baseline_at_ref(repo_root, args.base_ref, baseline_path)
            if base is None:
                print(f"error: could not read the baseline at {args.base_ref}", file=sys.stderr)
                return EXIT_EXTERNAL
            current = read_baseline(baseline_path)
            if current is None:
                print("error: baseline missing or malformed", file=sys.stderr)
                return EXIT_CONFIG
            if current > base:
                print(
                    f"BASELINE RAISED: {base} -> {current} (+{current - base}) against "
                    f"{args.base_ref}. The baseline may only fall. Fix the findings "
                    "instead of widening the allowance.",
                    file=sys.stderr,
                )
                return EXIT_REGRESSION

    baseline = read_baseline(baseline_path)
    if baseline is None:
        print(
            f"error: baseline missing or malformed: {baseline_path}",
            file=sys.stderr,
        )
        return EXIT_CONFIG

    count = current_count(repo_root)
    if count is None:
        print("error: ruff failed to run", file=sys.stderr)
        return EXIT_EXTERNAL

    if count > baseline:
        print(
            f"REGRESSION: {count} violations > baseline {baseline} (+{count - baseline}). "
            "New ruff violations cannot merge; fix them, or coordinate a baseline "
            "change deliberately.",
            file=sys.stderr,
        )
        return EXIT_REGRESSION

    if count < baseline:
        if args.update:
            write_baseline(baseline_path, count)
            print(f"improved {baseline} -> {count} (-{baseline - count}). Baseline lowered.")
            return EXIT_OK
        print(
            f"BASELINE STALE: {count} violations < baseline {baseline} "
            f"(-{baseline - count}). Run with --update to lower the baseline and close "
            "the slack.",
            file=sys.stderr,
        )
        return EXIT_REGRESSION

    print(f"OK (count == baseline {baseline}).")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())