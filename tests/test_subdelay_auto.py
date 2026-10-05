from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from ani_cli_sync.cli import _auto_sub_delay, _should_auto_measure
from ani_cli_sync.subsync import OffsetResult
from ani_cli_sync.subtitles import StreamInfo, SubtitlePlan

INFO = StreamInfo(video_link="https://hls.example/1080/index.m3u8", referrer="https://zokoanime.video/")
PLAN = SubtitlePlan(sub_files=["/cache/de.vtt"], sid=1, secondary_sid=0)
NO_PLAN = SubtitlePlan(sub_files=[], sid=1, secondary_sid=0)


def _result(offset: float, confident: bool = True, reason: str = "") -> OffsetResult:
    return OffsetResult(
        offset=offset,
        onset=38.5,
        first_cue=41.87,
        confident=confident,
        reason=reason,
    )


class TestAutoSubDelay(unittest.TestCase):
    """_auto_sub_delay decides the shift. It must never raise: playback outranks measurement."""

    def _run(self, plan=PLAN, vad=True, measure=None):
        with (
            patch("ani_cli_sync.subsync.vad_available", return_value=vad),
            patch("ani_cli_sync.subsync.measure_offset", return_value=measure),
        ):
            return _auto_sub_delay(INFO, plan)

    def test_applies_confident_negative_offset(self):
        self.assertAlmostEqual(self._run(measure=_result(-3.37)), -3.37, places=3)

    def test_applies_confident_positive_offset(self):
        self.assertAlmostEqual(self._run(measure=_result(0.25)), 0.25, places=3)

    def test_unconfident_result_does_not_shift(self):
        self.assertEqual(self._run(measure=_result(-9.0, confident=False, reason="no dialogue")), 0.0)

    def test_none_result_does_not_shift(self):
        self.assertEqual(self._run(measure=None), 0.0)

    def test_missing_vad_does_not_shift(self):
        self.assertEqual(self._run(vad=False, measure=_result(-3.37)), 0.0)

    def test_negligible_offset_not_applied(self):
        # Sub-0.05s is imperceptible; emitting a flag for it is noise.
        self.assertEqual(self._run(measure=_result(0.01)), 0.0)

    def test_no_subtitle_track_does_not_shift(self):
        self.assertEqual(self._run(plan=NO_PLAN, measure=_result(-3.37)), 0.0)

    def test_measurement_exception_does_not_propagate(self):
        with (
            patch("ani_cli_sync.subsync.vad_available", return_value=True),
            patch("ani_cli_sync.subsync.measure_offset", side_effect=RuntimeError("boom")),
        ):
            self.assertEqual(_auto_sub_delay(INFO, PLAN), 0.0)

    def test_measures_against_the_primary_track(self):
        """The offset must be measured against the file that becomes --sid=1."""
        plan = SubtitlePlan(sub_files=["/cache/de.vtt", "/cache/en.vtt"], sid=1, secondary_sid=2)
        with (
            patch("ani_cli_sync.subsync.vad_available", return_value=True),
            patch("ani_cli_sync.subsync.measure_offset", return_value=_result(-1.0)) as mock_measure,
        ):
            _auto_sub_delay(INFO, plan)
        self.assertEqual(mock_measure.call_args[0][1], "/cache/de.vtt")


class TestManualOverridePrecedence(unittest.TestCase):
    """An explicit non-zero --sub-delay must never be overridden by a measurement."""

    def test_non_zero_manual_value_suppresses_measurement(self):
        self.assertFalse(_should_auto_measure("auto", -1.5))
        self.assertFalse(_should_auto_measure("auto", 0.5))

    def test_zero_means_unset_so_measurement_proceeds(self):
        # 0 is the default and means "no shift"; measuring is exactly what is wanted,
        # otherwise the flag could never discover an offset from a clean invocation.
        self.assertTrue(_should_auto_measure("auto", 0.0))

    def test_sub_sync_off_never_measures(self):
        self.assertFalse(_should_auto_measure("off", 0.0))
        self.assertFalse(_should_auto_measure("off", -3.0))


class TestSubSyncCliSurface(unittest.TestCase):
    """Drive the real parser through main(); it is constructed inline, not exposed."""

    def _parsed(self, argv: list[str]) -> dict:
        import ani_cli_sync.cli as cli_module

        captured: dict = {}

        def fake_watch(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(sys, "argv", argv),
            patch.object(cli_module, "cmd_watch", side_effect=fake_watch),
        ):
            cli_module.main()
        return captured

    def test_defaults_to_off(self):
        self.assertEqual(self._parsed(["ani-cli-sync", "watch"])["sub_sync"], "off")

    def test_parses_auto(self):
        self.assertEqual(self._parsed(["ani-cli-sync", "watch", "--sub-sync", "auto"])["sub_sync"], "auto")

    def test_parses_auto_equals_form(self):
        self.assertEqual(self._parsed(["ani-cli-sync", "--sub-sync=auto"])["sub_sync"], "auto")

    def test_rejects_unknown_value(self):
        with patch.object(sys, "argv", ["ani-cli-sync", "watch", "--sub-sync", "bogus"]), self.assertRaises(SystemExit):
            import ani_cli_sync.cli as cli_module

            cli_module.main()

    def test_manual_delay_still_parsed_alongside(self):
        captured = self._parsed(["ani-cli-sync", "watch", "--sub-delay", "-1.5", "--sub-sync", "auto"])
        self.assertEqual(captured["sub_delay"], -1.5)
        self.assertEqual(captured["sub_sync"], "auto")


if __name__ == "__main__":
    unittest.main()