from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from ruff_count_ratchet import (
    EXIT_CONFIG,
    EXIT_EXTERNAL,
    EXIT_OK,
    EXIT_REGRESSION,
    baseline_absent_at_ref,
    baseline_at_ref,
    count_diagnostics,
    current_count,
    read_baseline,
    tracked_files,
    write_baseline,
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo(tmp: Path, tracked_py: bool = True) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "agent.tests@example.com")
    _git(repo, "config", "user.name", "Synthetic Agent Tests")
    if tracked_py:
        (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--allow-empty", "-qm", "init")
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


def _recording_ruff(
    tmp: Path,
    *,
    exit_code: int = 1,
    fixed_lines: int = 0,
    per_file_line: bool = False,
    stderr_text: str = "",
) -> tuple[Path, Path]:
    """A `ruff` stub that logs cwd and argv of every invocation to a file.

    Fixed-count and per-file variants keep the emitted json-lines deterministic;
    the log observable proves whether, how often, and with what arguments the
    gate actually ran the linter, and which cwd it ran in.
    """
    bindir = tmp / "bin"
    bindir.mkdir(exist_ok=True)
    log = tmp / "ruff_stub.log"
    body = [
        "#!/bin/sh",
        "{",
        '  printf \'cwd %s\\n\' "$(pwd)"',
        '  for a in "$@"; do printf \'arg %s\\n\' "$a"; done',
        "  printf 'end\\n'",
        "} >> '" + str(log) + "'",
    ]
    if stderr_text:
        body.append(f"printf '{stderr_text}\\n' >&2")
    if per_file_line:
        body += [
            "seen=0",
            'for a in "$@"; do',
            '  if [ "$seen" = 1 ]; then printf \'{"code":"F401"}\\n\'; fi',
            '  [ "$a" = "--" ] && seen=1',
            "done",
        ]
    else:
        body += [
            f"n=0; while [ $n -lt {fixed_lines} ]; do",
            '  printf \'{"code":"F401"}\\n\'',
            "  n=$((n+1))",
            "done",
        ]
    body.append(f"exit {exit_code}")
    stub = bindir / "ruff"
    stub.write_text("\n".join(body) + "\n", encoding="utf-8")
    stub.chmod(0o755)
    return bindir, log


def _stub_call_log(log: Path) -> list[tuple[str, list[str]]]:
    """Parse the stub log into ``(cwd, argv)`` pairs, one per invocation."""
    if not log.exists():
        return []
    calls: list[tuple[str, list[str]]] = []
    cwd, args = "", []
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.startswith("cwd "):
            cwd = line[4:]
        elif line.startswith("arg "):
            args.append(line[4:])
        elif line == "end":
            calls.append((cwd, list(args)))
            cwd, args = "", []
    return calls


def _run_gate(
    repo: Path,
    *cli_args: str,
    bindir: Path | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run the real gate script on argv with an optional stub `ruff` on PATH."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if bindir is not None:
        env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "ruff_count_ratchet.py"), *cli_args],
        cwd=str(cwd if cwd is not None else repo),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _base_ref_repo(
    tmp: Path,
    *,
    base_baseline: str | None,
    head_baseline: str | None,
) -> tuple[Path, str]:
    """A two-tip repository for --base-ref runs; ``HEAD~1`` is the base tip.

    The middle commit carries the base baseline (or nothing, for the bootstrap
    case), so the base tip always exists whether or not it records a baseline.
    """
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "agent.tests@example.com")
    _git(repo, "config", "user.name", "Synthetic Agent Tests")
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base content")
    if base_baseline is None:
        # The baseline directory exists in the base tip so --base-ref must not
        # mistake the bootstrap case for an absent repository path.
        _baseline_in_scripts(repo, "0\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "base tip without baseline")
        _git(repo, "rm", "-q", "scripts/ruff_count_baseline.txt")
    else:
        _baseline_in_scripts(repo, f"{base_baseline}\n")
        _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base baseline")
    _baseline_in_scripts(repo, f"{head_baseline}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--allow-empty", "-qm", "head baseline")
    return repo, "HEAD~1"


def _baseline_in_scripts(repo: Path, text: str) -> Path:
    (repo / "scripts").mkdir(exist_ok=True, parents=True)
    path = repo / "scripts" / "ruff_count_baseline.txt"
    path.write_text(f"{text.rstrip()}\n", encoding="utf-8")
    return path


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


class TestWriteBaselineFailure(unittest.TestCase):
    def test_write_oserror_remains_uncaught(self):
        # An authorized update currently propagates write errors. This pins the
        # boundary without defining it as a friendlier exit-code contract.
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            with self.assertRaises(OSError):
                write_baseline(directory, 0)


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
        env["PYTHONDONTWRITEBYTECODE"] = "1"
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


class TestCountDiagnosticsPolicy(unittest.TestCase):
    """C01/C02: what a batch of ruff json-lines counts, and what it does not."""

    def test_c01_blank_lines_are_not_counted(self):
        self.assertEqual(count_diagnostics("\n\n   \n"), 0)

    def test_c01_e902_io_error_is_not_counted(self):
        # S01 detector: a file-access failure is an environment problem, not lint
        # debt, so deleting a tracked file must not look like a count change.
        self.assertEqual(count_diagnostics('{"code":"E902"}\n'), 0)
        self.assertEqual(count_diagnostics('{"code":"E902"}\n{"code":"F401"}\n'), 1)

    def test_c01_record_without_code_key_counts(self):
        self.assertEqual(count_diagnostics('{"message":"no code key"}\n'), 1)

    def test_c02_two_valid_objects_sum_to_two(self):
        self.assertEqual(count_diagnostics('{"code":"F401"}\n{"code":"E501"}\n'), 2)

    def test_c02_malformed_still_counts_in_a_mixed_batch(self):
        payload = '{"code":"F401"}\nnot json\n{"code":"E902"}\n\n{"code":"E501"}\n'
        self.assertEqual(count_diagnostics(payload), 3)

    def test_non_object_json_keeps_current_uncaught_attribute_error(self):
        # Source-observable defect, not supported policy: do not silently turn
        # valid JSON scalars/lists/null into malformed or zero-count input.
        for payload in ("1\n", '"diagnostic"\n', "[]\n", "null\n"):
            with self.subTest(payload=payload), self.assertRaises(AttributeError):
                count_diagnostics(payload)


class TestTrackedFilesScope(unittest.TestCase):
    """C03: the scan is `git ls-files` over tracked python files, never a walk."""

    def test_c03_tracked_py_and_pyi_in_path_order_others_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _init_repo(Path(td))
            (repo / "b.pyi").write_text("x: int = 1\n", encoding="utf-8")
            (repo / "c.txt").write_text("not python\n", encoding="utf-8")
            (repo / "sub").mkdir()
            (repo / "sub" / "d.py").write_text("y = 2\n", encoding="utf-8")
            # Name chosen so a directory-walk mutant would list it first.
            (repo / "aaa_untracked.py").write_text("z = 3\n", encoding="utf-8")
            _git(repo, "add", "b.pyi", "c.txt", "sub")
            self.assertEqual(tracked_files(repo), ["a.py", "b.pyi", "sub/d.py"])

    def test_c03_git_failure_returns_none_never_empty_list(self):
        # S02 detector: a failed listing must be unusable, not silently empty.
        with tempfile.TemporaryDirectory() as td:
            not_a_repo = Path(td) / "not-a-repo"
            not_a_repo.mkdir()
            self.assertIsNone(tracked_files(not_a_repo))

    def test_c03_git_oserror_returns_none_never_a_walk(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _init_repo(Path(td))
            empty_bin = Path(td) / "emptybin"
            empty_bin.mkdir()
            with mock.patch.dict(os.environ, {"PATH": str(empty_bin)}):
                self.assertIsNone(tracked_files(repo))


class TestCurrentCountExecution(unittest.TestCase):
    """C04-C07: the subprocess behaviour of the scan itself."""

    def _path_with_stub(self, bindir: Path) -> dict:
        return {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}

    def test_c04_empty_tracked_set_is_zero_without_a_ruff_call(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp, tracked_py=False)
            bindir, log = _recording_ruff(tmp, exit_code=99)
            with mock.patch.dict(os.environ, self._path_with_stub(bindir)):
                self.assertEqual(current_count(repo), 0)
            # An exit-99 stub proves no hidden ruff call: had it run, the scan
            # would have returned None instead of 0 and the log would exist.
            self.assertFalse(log.exists())

    def test_c05_batches_of_200_in_git_order_with_all_files(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "batchrepo"
            repo.mkdir()
            _git(repo, "init", "-q", "-b", "main")
            _git(repo, "config", "user.email", "agent.tests@example.com")
            _git(repo, "config", "user.name", "Synthetic Agent Tests")
            names = [f"f{i:03d}.py" for i in range(205)]
            for name in names:
                (repo / name).write_text("x = 1\n", encoding="utf-8")
            # Directory walks usually encounter this untracked name before the
            # tracked f*.py files; argv proves that Git scope excluded it.
            (repo / "aaa_untracked.py").write_text("z = 3\n", encoding="utf-8")
            _git(repo, "add", *names)
            _git(repo, "commit", "-qm", "init")
            bindir, log = _recording_ruff(tmp, per_file_line=True)
            with mock.patch.dict(os.environ, self._path_with_stub(bindir)):
                self.assertEqual(current_count(repo), 205)
            calls = _stub_call_log(log)
            self.assertEqual(len(calls), 2)
            first, second = calls[0][1], calls[1][1]
            for cwd, _argv in calls:
                self.assertEqual(cwd, str(repo.resolve()))
            self.assertEqual(first[:4], ["check", "--output-format", "json-lines", "--"])
            self.assertEqual(first[4:], names[:200])
            self.assertEqual(second[4:], names[200:])
            self.assertNotIn("aaa_untracked.py", first + second)

    def test_c06_exit_0_and_exit_1_both_produce_counts(self):
        for exit_code in (0, 1):
            with tempfile.TemporaryDirectory() as td:
                tmp = Path(td)
                repo = _init_repo(tmp)
                bindir, _log = _recording_ruff(tmp, exit_code=exit_code, fixed_lines=2)
                with mock.patch.dict(os.environ, self._path_with_stub(bindir)):
                    self.assertEqual(current_count(repo), 2)

    def test_c06_unexpected_exit_forwards_stderr_once_and_fails(self):
        # S08 detector: swallowing or duplicating this write is observable here.
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp)
            bindir, _log = _recording_ruff(
                tmp, exit_code=2, stderr_text="stub-boom: unexpected exit"
            )
            err = io.StringIO()
            with (
                mock.patch.dict(os.environ, self._path_with_stub(bindir)),
                contextlib.redirect_stderr(err),
            ):
                result = current_count(repo)
            self.assertIsNone(result)
            self.assertEqual(err.getvalue(), "stub-boom: unexpected exit\n")

    def test_c07_ruff_oserror_is_none_not_zero(self):
        # S02 detector: an unruff-able environment must not read as "clean".
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp)
            git_bin = tmp / "gitbin"
            git_bin.mkdir()
            git = shutil.which("git")
            if git is None:
                self.skipTest("git is required by this suite")
            os.symlink(git, git_bin / "git")
            with mock.patch.dict(os.environ, {"PATH": str(git_bin)}):
                self.assertIsNone(current_count(repo))

    def test_c07_cli_ruff_oserror_is_exit_3_not_ok(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp)
            _baseline_in_scripts(repo, "0")
            git_bin = tmp / "gitbin"
            git_bin.mkdir()
            git = shutil.which("git")
            if git is None:
                self.skipTest("git is required by this suite")
            os.symlink(git, git_bin / "git")
            with mock.patch.dict(os.environ, {"PATH": str(git_bin)}):
                proc = _run_gate(repo)
            self.assertEqual(proc.returncode, EXIT_EXTERNAL)
            self.assertEqual(proc.stderr, "error: ruff failed to run\n")


class TestBaselineAtRefHelpers(unittest.TestCase):
    """C10/C11: reading a baseline from a ref, and the absent-vs-malformed split.

    ``baseline_at_ref`` answers the integer, ``baseline_absent_at_ref`` answers
    whether the ref records no baseline at all; together they fail closed: a
    git failure or a baseline outside the repository must never read as
    "nothing to compare against".
    """

    def test_c10_integer_baseline_at_ref_reads_back(self):
        with tempfile.TemporaryDirectory() as td:
            repo, ref = _base_ref_repo(Path(td), base_baseline="7", head_baseline="1")
            baseline = repo / "scripts" / "ruff_count_baseline.txt"
            self.assertEqual(baseline_at_ref(repo, ref, baseline), 7)

    def test_c10_absent_at_ref_is_none_and_flag_true(self):
        with tempfile.TemporaryDirectory() as td:
            repo, ref = _base_ref_repo(Path(td), base_baseline=None, head_baseline="1")
            baseline = repo / "scripts" / "ruff_count_baseline.txt"
            self.assertIsNone(baseline_at_ref(repo, ref, baseline))
            self.assertTrue(baseline_absent_at_ref(repo, ref, baseline))

    def test_c10_malformed_at_ref_is_none_and_flag_false(self):
        with tempfile.TemporaryDirectory() as td:
            repo, ref = _base_ref_repo(
                Path(td), base_baseline="not-a-number", head_baseline="1"
            )
            baseline = repo / "scripts" / "ruff_count_baseline.txt"
            self.assertIsNone(baseline_at_ref(repo, ref, baseline))
            self.assertFalse(baseline_absent_at_ref(repo, ref, baseline))

    def test_c10_unresolved_ref_fails_closed_in_both_helpers(self):
        with tempfile.TemporaryDirectory() as td:
            repo, _ref = _base_ref_repo(Path(td), base_baseline="1", head_baseline="1")
            baseline = repo / "scripts" / "ruff_count_baseline.txt"
            self.assertIsNone(baseline_at_ref(repo, "no-such-ref", baseline))
            self.assertFalse(baseline_absent_at_ref(repo, "no-such-ref", baseline))

    def test_c10_baseline_outside_repo_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            repo, ref = _base_ref_repo(Path(td), base_baseline="1", head_baseline="1")
            outside = repo.parent / "outside.txt"
            outside.write_text("1\n", encoding="utf-8")
            self.assertIsNone(baseline_at_ref(repo, ref, outside))
            self.assertFalse(baseline_absent_at_ref(repo, ref, outside))

    def test_c10_cli_unresolved_ref_is_error_3_no_bootstrap_no_ruff(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ref = _base_ref_repo(tmp, base_baseline="1", head_baseline="5")
            _bindir, log = _recording_ruff(tmp, exit_code=0)
            proc = _run_gate(repo, "--base-ref", "no-such-ref", bindir=_bindir)
            self.assertEqual(proc.returncode, EXIT_EXTERNAL)
            self.assertEqual(proc.stderr, "error: could not read the baseline at no-such-ref\n")
            self.assertEqual(proc.stdout, "")
            self.assertFalse(log.exists())


class TestBaseRefCli(unittest.TestCase):
    """C12/C20/C22/C25: what --base-ref enforces, in which order, on which stream."""

    def test_c12_equal_base_and_current_passes_comparison(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, ref = _base_ref_repo(tmp, base_baseline="0", head_baseline="0")
            bindir, _log = _recording_ruff(tmp, exit_code=1, fixed_lines=0)
            proc = _run_gate(repo, "--base-ref", ref, bindir=bindir)
            self.assertEqual(proc.returncode, EXIT_OK)
            self.assertEqual(proc.stdout, "OK (count == baseline 0).\n")

    def test_c12_c20_raised_baseline_exits_1_before_ruff_and_update(self):
        # S07 detector: skipping the base-ref check makes the stub run (exit 99),
        # removes the message, and lands on a different failing outcome.
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, ref = _base_ref_repo(tmp, base_baseline="0", head_baseline="5")
            baseline = repo / "scripts" / "ruff_count_baseline.txt"
            before = baseline.read_bytes()
            _bindir, log = _recording_ruff(
                tmp, exit_code=99, stderr_text="stub-boom: must not run"
            )
            proc = _run_gate(repo, "--base-ref", ref, "--update", bindir=_bindir)
            self.assertEqual(proc.returncode, EXIT_REGRESSION)
            self.assertEqual(
                proc.stderr,
                f"BASELINE RAISED: 0 -> 5 (+5) against {ref}. The baseline may only "
                "fall. Fix the findings instead of widening the allowance.\n",
            )
            self.assertEqual(proc.stdout, "")
            self.assertFalse(log.exists())
            self.assertEqual(baseline.read_bytes(), before)

    def test_c20_update_flag_cannot_bypass_raised_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            repo, ref = _base_ref_repo(Path(td), base_baseline="3", head_baseline="9")
            _bindir, log = _recording_ruff(Path(td), exit_code=99)
            proc = _run_gate(repo, "--base-ref", ref, "--update", bindir=_bindir)
            self.assertEqual(proc.returncode, EXIT_REGRESSION)
            self.assertIn("BASELINE RAISED: 3 -> 9 (+6)", proc.stderr)
            self.assertIn("Fix the findings", proc.stderr)
            self.assertEqual(proc.stdout, "")
            self.assertFalse(log.exists())

    def test_c22_bootstrap_message_when_absent_at_ref(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, ref = _base_ref_repo(tmp, base_baseline=None, head_baseline="0")
            bindir, _log = _recording_ruff(tmp, exit_code=1, fixed_lines=0)
            proc = _run_gate(repo, "--base-ref", ref, bindir=bindir)
            self.assertEqual(proc.returncode, EXIT_OK)
            self.assertEqual(
                proc.stdout,
                f"bootstrap: {ref} records no baseline yet, so there is no "
                "earlier value to raise. The one-directional check starts once "
                "this baseline lands.\nOK (count == baseline 0).\n",
            )
            self.assertEqual(proc.stderr, "")

    def test_c22_existing_base_baseline_cannot_bootstrap(self):
        with tempfile.TemporaryDirectory() as td:
            repo, ref = _base_ref_repo(Path(td), base_baseline="0", head_baseline="5")
            proc = _run_gate(repo, "--base-ref", ref)
            self.assertEqual(proc.returncode, EXIT_REGRESSION)
            self.assertNotIn("bootstrap", proc.stdout)

    def test_c25_malformed_base_ref_is_error_3_not_bootstrap(self):
        # Pins the actual exit for an unreadable base baseline: EXIT_EXTERNAL
        # (source line "could not read the baseline at"), not EXIT_CONFIG and
        # not the bootstrap path. Design matrix C25 says "config failure"; the
        # implemented contract returns 3. Recorded in tests-review.md.
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, ref = _base_ref_repo(
                tmp, base_baseline="not-a-number", head_baseline="0"
            )
            _bindir, log = _recording_ruff(tmp, exit_code=99)
            proc = _run_gate(repo, "--base-ref", ref, bindir=_bindir)
            self.assertEqual(proc.returncode, EXIT_EXTERNAL)
            self.assertEqual(proc.stderr, f"error: could not read the baseline at {ref}\n")
            self.assertNotIn("bootstrap", proc.stdout)
            self.assertFalse(log.exists())


class TestRatchetMessagesAndWrites(unittest.TestCase):
    """C09/C13-C18/C23/C26/C27: exact messages, streams, and write timing."""

    def test_c18_c23_success_message_exact_on_stdout(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp)
            _baseline_in_scripts(repo, "0")
            bindir, _log = _recording_ruff(tmp, exit_code=1, fixed_lines=0)
            proc = _run_gate(repo, bindir=bindir)
            self.assertEqual(proc.returncode, EXIT_OK)
            self.assertEqual(proc.stdout, "OK (count == baseline 0).\n")
            self.assertEqual(proc.stderr, "")

    def test_c23_regression_message_exact_on_stderr(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp)
            _baseline_in_scripts(repo, "2")
            bindir, _log = _recording_ruff(tmp, exit_code=1, fixed_lines=3)
            proc = _run_gate(repo, bindir=bindir)
            self.assertEqual(proc.returncode, EXIT_REGRESSION)
            self.assertEqual(
                proc.stderr,
                "REGRESSION: 3 violations > baseline 2 (+1). New ruff violations "
                "cannot merge; fix them, or coordinate a baseline change "
                "deliberately.\n",
            )
            self.assertEqual(proc.stdout, "")

    def test_c14_c23_stale_message_exact_and_file_preserved(self):
        # S04 detector: a mutant that accepts a lower count without --update
        # fails both the exit and the exact stderr assertion.
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp)
            baseline = _baseline_in_scripts(repo, "5")
            bindir, _log = _recording_ruff(tmp, exit_code=1, fixed_lines=3)
            proc = _run_gate(repo, bindir=bindir)
            self.assertEqual(proc.returncode, EXIT_REGRESSION)
            self.assertEqual(
                proc.stderr,
                "BASELINE STALE: 3 violations < baseline 5 (-2). Run with "
                "--update to lower the baseline and close the slack.\n",
            )
            self.assertEqual(proc.stdout, "")
            self.assertEqual(baseline.read_bytes(), b"5\n")

    def test_c09_c23_update_lowers_to_exact_bytes_with_message(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp)
            baseline = _baseline_in_scripts(repo, "5")
            bindir, _log = _recording_ruff(tmp, exit_code=1, fixed_lines=3)
            proc = _run_gate(repo, "--update", bindir=bindir)
            self.assertEqual(proc.returncode, EXIT_OK)
            self.assertEqual(proc.stdout, "improved 5 -> 3 (-2). Baseline lowered.\n")
            self.assertEqual(baseline.read_bytes(), b"3\n")

    def test_c15_higher_count_with_update_fails_and_preserves_file(self):
        # S05 detector: --update must never widen; the regression branch has
        # to fire even when the operator asks for a write.
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp)
            baseline = _baseline_in_scripts(repo, "2")
            bindir, _log = _recording_ruff(tmp, exit_code=1, fixed_lines=3)
            proc = _run_gate(repo, "--update", bindir=bindir)
            self.assertEqual(proc.returncode, EXIT_REGRESSION)
            self.assertEqual(baseline.read_bytes(), b"2\n")

    def test_c13_equal_count_never_writes_even_with_update(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp)
            baseline = _baseline_in_scripts(repo, "3")
            bindir, _log = _recording_ruff(tmp, exit_code=1, fixed_lines=3)
            proc = _run_gate(repo, "--update", bindir=bindir)
            self.assertEqual(proc.returncode, EXIT_OK)
            self.assertEqual(baseline.read_bytes(), b"3\n")

    def test_c16_c26_external_failure_exact_streams_exit_3(self):
        # S06 detector: collapsing EXIT_EXTERNAL to EXIT_OK fails here.
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp)
            _baseline_in_scripts(repo, "0")
            bindir, _log = _recording_ruff(
                tmp, exit_code=2, stderr_text="stub-boom: unexpected exit"
            )
            proc = _run_gate(repo, bindir=bindir)
            self.assertEqual(proc.returncode, EXIT_EXTERNAL)
            self.assertEqual(
                proc.stderr,
                "stub-boom: unexpected exit\nerror: ruff failed to run\n",
            )
            self.assertEqual(proc.stdout, "")

    def test_c16_external_failure_with_update_still_3_no_write(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp)
            baseline = _baseline_in_scripts(repo, "0")
            bindir, _log = _recording_ruff(
                tmp, exit_code=2, stderr_text="stub-boom: unexpected exit"
            )
            proc = _run_gate(repo, "--update", bindir=bindir)
            self.assertEqual(proc.returncode, EXIT_EXTERNAL)
            self.assertEqual(baseline.read_bytes(), b"0\n")
            self.assertEqual(proc.stdout, "")

    def test_c27_no_write_on_any_non_success_path(self):
        scenarios = [
            ("regression", "2", 3, 1, []),
            ("stale-no-update", "5", 3, 1, []),
            ("malformed-baseline", "oops", 0, 2, []),
            ("external-ruff", "0", 0, 3, []),
            ("unknown-flag", "0", 0, 2, ["--no-such-flag"]),
        ]
        for name, text, violations, expected, extra in scenarios:
            with self.subTest(name), tempfile.TemporaryDirectory() as td:
                tmp = Path(td)
                repo = _init_repo(tmp)
                baseline = _baseline_in_scripts(repo, text)
                before = baseline.read_bytes()
                bindir, _log = _recording_ruff(
                    tmp,
                    exit_code=2 if name == "external-ruff" else 1,
                    fixed_lines=violations,
                )
                proc = _run_gate(repo, *extra, bindir=bindir)
                self.assertEqual(proc.returncode, expected)
                self.assertEqual(baseline.read_bytes(), before)

    def test_c27_missing_baseline_stays_absent_on_failure(self):
        with tempfile.TemporaryDirectory() as td:
            repo = _init_repo(Path(td))
            baseline = repo / "scripts" / "ruff_count_baseline.txt"
            self.assertFalse(baseline.exists())
            proc = _run_gate(repo)
            self.assertEqual(proc.returncode, EXIT_CONFIG)
            self.assertFalse(baseline.exists())


class TestCliContract(unittest.TestCase):
    """C19/C21/C24: path resolution, empty repos, and the parser's contract."""

    def test_c24_exit_constants_are_0_1_2_3(self):
        self.assertEqual(
            (EXIT_OK, EXIT_REGRESSION, EXIT_CONFIG, EXIT_EXTERNAL), (0, 1, 2, 3)
        )

    def test_c24_unknown_flag_is_usage_error_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp)
            _baseline_in_scripts(repo, "0")
            _bindir, log = _recording_ruff(tmp, exit_code=99)
            proc = _run_gate(repo, "--no-such-flag", bindir=_bindir)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("usage:", proc.stderr)
            self.assertEqual(proc.stdout, "")
            self.assertFalse(log.exists())

    def test_c19_custom_repo_and_baseline_paths_resolve_cwd_free(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp)
            elsewhere = tmp / "neutral"
            elsewhere.mkdir()
            custom = repo / "custom" / "b.txt"
            custom.parent.mkdir()
            # Resolve cwd '.' against the process cwd: if the gate resolved the
            # custom values against cwd instead of repo this would fail.
            proc = _run_gate(
                repo,
                "--repo-root",
                str(repo),
                "--baseline",
                str(custom),
                cwd=elsewhere,
            )
            self.assertEqual(proc.returncode, EXIT_CONFIG)
            self.assertEqual(
                proc.stderr, f"error: baseline missing or malformed: {custom}\n"
            )
            self.assertFalse((repo / "scripts").exists())

    def test_c19_relative_baseline_resolves_against_neutral_cwd(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp)
            elsewhere = tmp / "neutral"
            elsewhere.mkdir()
            custom = elsewhere / "custom" / "b.txt"
            custom.parent.mkdir()
            custom.write_text("5\n", encoding="utf-8")
            bindir, _log = _recording_ruff(tmp, exit_code=1, fixed_lines=3)
            proc = _run_gate(
                repo,
                "--repo-root",
                str(repo),
                "--baseline",
                "custom/b.txt",
                "--update",
                bindir=bindir,
                cwd=elsewhere,
            )
            self.assertEqual(proc.returncode, EXIT_OK)
            self.assertEqual(custom.read_bytes(), b"3\n")
            self.assertFalse((repo / "custom").exists())

    def test_c19_default_repo_root_is_invocation_cwd(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp)
            elsewhere = tmp / "neutral"
            _baseline_in_scripts(elsewhere, "0\n")
            bindir, log = _recording_ruff(tmp, exit_code=99)
            proc = _run_gate(repo, bindir=bindir, cwd=elsewhere)
            self.assertEqual(proc.returncode, EXIT_EXTERNAL)
            self.assertEqual(proc.stderr, "error: ruff failed to run\n")
            self.assertFalse(log.exists())

    def test_c19_update_writes_only_the_named_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp)
            elsewhere = tmp / "neutral"
            elsewhere.mkdir()
            custom = repo / "custom" / "b.txt"
            custom.parent.mkdir()
            custom.write_text("5\n", encoding="utf-8")
            bindir, _log = _recording_ruff(tmp, exit_code=1, fixed_lines=3)
            proc = _run_gate(
                repo,
                "--repo-root",
                str(repo),
                "--baseline",
                str(custom),
                "--update",
                bindir=bindir,
                cwd=elsewhere,
            )
            self.assertEqual(proc.returncode, EXIT_OK)
            self.assertEqual(custom.read_bytes(), b"3\n")
            self.assertFalse((repo / "scripts" / "ruff_count_baseline.txt").exists())

    def test_c21_zero_tracked_files_zero_baseline_ok_without_ruff(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp, tracked_py=False)
            _baseline_in_scripts(repo, "0")
            bindir, log = _recording_ruff(tmp, exit_code=99)
            proc = _run_gate(repo, bindir=bindir)
            self.assertEqual(proc.returncode, EXIT_OK)
            self.assertEqual(proc.stdout, "OK (count == baseline 0).\n")
            self.assertFalse(log.exists())

    def test_c21_zero_files_does_not_conceal_bad_baseline(self):
        # S06 detector: a config error with no files still exits 2.
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_repo(tmp, tracked_py=False)
            baseline = _baseline_in_scripts(repo, "oops")
            bindir, _log = _recording_ruff(tmp, exit_code=99)
            proc = _run_gate(repo, bindir=bindir)
            self.assertEqual(proc.returncode, EXIT_CONFIG)
            self.assertEqual(
                proc.stderr,
                f"error: baseline missing or malformed: {baseline.resolve()}\n",
            )

    def test_c21_non_repo_root_is_external_failure_not_ok(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            not_repo = tmp / "not-a-repo"
            _baseline_in_scripts(not_repo, "0")
            proc = _run_gate(not_repo)
            self.assertEqual(proc.returncode, EXIT_EXTERNAL)
            self.assertEqual(proc.stderr, "error: ruff failed to run\n")


if __name__ == "__main__":
    unittest.main()
