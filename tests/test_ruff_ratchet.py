from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from ruff_count_ratchet import (  # noqa: E402
    EXIT_CONFIG,
    EXIT_EXTERNAL,
    EXIT_OK,
    EXIT_REGRESSION,
    count_diagnostics,
    read_baseline,
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _init_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    return repo


def _stub_ruff(tmp: Path, violations: int) -> Path:
    """Put a deterministic `ruff` on PATH.

    The gate's own logic is what these tests exercise, so the linter is stubbed at the
    process boundary. A missing ruff must surface as EXIT_EXTERNAL, never as "no
    regression", so the stub has to exist and be controllable per test.
    """
    bindir = tmp / "bin"
    bindir.mkdir(exist_ok=True)
    stub = bindir / "ruff"
    stub.write_text(
        "#!/bin/sh\n"
        f'n=0\nwhile [ $n -lt {violations} ]; do\n'
        '  printf \'{"code":"F401","message":"unused import"}\\n\'\n'
        "  n=$((n+1))\n"
        "done\n"
        "exit 1\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return bindir


class TestCountDiagnostics(unittest.TestCase):
    def test_counts_one_diagnostic_per_line(self):
        payload = '{"code":"F401"}\n{"code":"F401"}\n{"code":"E501"}\n'
        self.assertEqual(count_diagnostics(payload), 3)

    def test_empty_output_is_zero(self):
        self.assertEqual(count_diagnostics(""), 0)

    def test_malformed_line_is_counted_not_dropped(self):
        # A line ruff emitted that we cannot parse must still count: dropping it would
        # silently lower the metric this gate defends.
        self.assertEqual(count_diagnostics("not json\n{\"code\":\"F401\"}\n"), 2)


class TestReadBaseline(unittest.TestCase):
    def test_reads_integer(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "b.txt"
            p.write_text("18\n", encoding="utf-8")
            self.assertEqual(read_baseline(p), 18)

    def test_missing_file_is_config_error(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(read_baseline(Path(td) / "absent.txt"))

    def test_non_integer_is_config_error(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "b.txt"
            p.write_text("eighteen\n", encoding="utf-8")
            self.assertIsNone(read_baseline(p))


class TestRatchetExitCodes(unittest.TestCase):
    """The ratchet must distinguish four outcomes. Collapsing them is how a lint gate
    silently stops gating: a config error must never read as 'no regression'."""

    def _run(self, repo: Path, baseline: str, *extra: str, violations: int = 0) -> int:
        # Exercise the script's real default contract: the baseline lives beside it
        # under scripts/, not at the repo root.
        (repo / "scripts").mkdir(exist_ok=True)
        path = repo / "scripts" / "ruff_count_baseline.txt"
        path.write_text(baseline, encoding="utf-8")
        bindir = _stub_ruff(repo.parent, violations)
        env = dict(os.environ)
        env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "ruff_count_ratchet.py"), *extra],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self._last = proc
        return proc.returncode

    def test_equal_count_passes(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _init_repo(Path(td))
            self.assertEqual(self._run(repo, "0"), EXIT_OK)

    def test_missing_baseline_is_config_error(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _init_repo(Path(td))
            self.assertEqual(self._run(repo, "0", "--baseline", "absent.txt"), EXIT_CONFIG)

    def test_unparsable_baseline_is_config_error(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _init_repo(Path(td))
            self.assertEqual(self._run(repo, "not-a-number"), EXIT_CONFIG)

    def test_count_above_baseline_is_regression(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _init_repo(Path(td))
            # Baseline 0 but the repo's own known violations are counted, so force a
            # regression by setting the baseline below the real count.
            self.assertEqual(self._run(repo, "0", "--update"), EXIT_OK)
            self.assertEqual(self._run(repo, "0", violations=3), EXIT_REGRESSION)

    def test_decrease_without_update_is_regression(self):
        """An unrecorded decrease must fail, otherwise the slack it leaves can absorb a
        later regression. The baseline is allowed to fall only via --update."""
        with tempfile.TemporaryDirectory() as td:
            repo = _init_repo(Path(td))
            self.assertEqual(self._run(repo, "0", "--update"), EXIT_OK)
            # Baseline now equals the real count. Raise it by hand, then the measured
            # count is below baseline and must fail without --update.
            (repo / "scripts" / "ruff_count_baseline.txt").write_text("999\n", encoding="utf-8")
            self.assertEqual(self._run(repo, "999"), EXIT_REGRESSION)

    def test_update_records_decrease(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _init_repo(Path(td))
            self.assertEqual(self._run(repo, "5", "--update"), EXIT_OK)
            self.assertEqual((repo / "scripts" / "ruff_count_baseline.txt").read_text().strip(), "0")

    def test_exit_code_constants_are_distinct(self):
        codes = [EXIT_OK, EXIT_REGRESSION, EXIT_CONFIG, EXIT_EXTERNAL]
        self.assertEqual(len(codes), len(set(codes)))


if __name__ == "__main__":
    unittest.main()