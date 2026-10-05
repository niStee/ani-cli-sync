from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from ani_cli_sync.cli import _auto_sub_delay, _should_auto_measure
from ani_cli_sync.subsync import OffsetResult
from ani_cli_sync.subtitles import StreamInfo, SubtitlePlan

INFO = StreamInfo(video_link="https://hls.example/1080/index.m3u8", referrer="https://zokoanime.video/")
PLAN = SubtitlePlan(sub_files=["/cache/de.vtt"], sid=1, secondary_sid=0)
NO_PLAN = SubtitlePlan(sub_files=[], sid=1, secondary_sid=0)

# progress 1 of 3 -> plays ep2, then autoplays ep3, which completes and ends the run.
TWO_EPISODE_ENTRY = {
    "id": 1,
    "mediaId": 100,
    "progress": 1,
    "media": {"id": 100, "title": {"english": "Show Season 1", "romaji": "Show S1"}, "episodes": 3},
}


def _result(
    offset: float,
    confident: bool = True,
    reason: str = "",
    onset: float = 38.5,
    first_cue: float = 41.87,
) -> OffsetResult:
    return OffsetResult(
        offset=offset,
        onset=onset,
        first_cue=first_cue,
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


class TestPerEpisodeMeasurement(unittest.TestCase):
    """--sub-sync=auto must measure every episode, never reuse the previous result.

    The offset is a property of one subtitle file, never of the invocation: Attack on
    Titan ep1 needs -3.37 while ep2 needs +0.25. Feeding ep1's value into ep2 mis-times
    the dialogue by seconds, which is worse than applying no shift at all.
    """

    INFO = StreamInfo(video_link="https://hls.example/1080/index.m3u8", referrer="https://zokoanime.video/")
    PLAN = SubtitlePlan(sub_files=["/cache/de.vtt"], sid=1, secondary_sid=0)

    def _drive(self, returncode: int = 0, measurements: tuple = ()):
        """Run cmd_watch over two episodes on the subtitles path. Returns the mocks."""
        import ani_cli_sync.cli as cli_module

        cli_module._PREQUEL_OFFSET_CACHE.clear()

        def mock_gql(query, variables=None, token=None, retries=3):
            if "relations" in query:
                # Empty edges: find_sequel returns nothing and the run ends after ep3.
                return {"data": {"Media": {"relations": {"edges": []}}}}
            if "MediaList" in query:
                raise RuntimeError("Not Found.")
            return {}

        build_mpv = MagicMock(return_value=["mpv"])
        measure = MagicMock(side_effect=list(measurements))
        probe = MagicMock(return_value=None)
        update = MagicMock()

        with (
            patch.object(cli_module, "get_token", return_value="tok"),
            patch.object(cli_module, "get_viewer", return_value={"id": 42, "name": "nils"}),
            patch.object(cli_module, "get_watching_list", return_value=[TWO_EPISODE_ENTRY]),
            patch.object(cli_module, "gql_query", side_effect=mock_gql),
            patch.object(cli_module, "update_progress", update),
            patch.object(
                cli_module.subprocess,
                "run",
                MagicMock(return_value=MagicMock(returncode=returncode)),
            ),
            # Two (start, end) pairs: each episode reports 1450s of playback, above the
            # unknown-duration fallback threshold.
            patch.object(cli_module.time, "time", side_effect=[0.0, 1450.0, 1450.0, 2900.0]),
            patch.object(cli_module.time, "sleep"),
            patch.object(cli_module, "_probe_duration", probe),
            patch("ani_cli_sync.subtitles.resolve_stream_info", return_value=self.INFO),
            patch("ani_cli_sync.subtitles.prepare_subtitles", return_value=self.PLAN),
            patch("ani_cli_sync.subtitles.build_mpv_command", build_mpv),
            patch("ani_cli_sync.subtitles.prefetch_next_episode"),
            patch("ani_cli_sync.subsync.vad_available", return_value=True),
            patch("ani_cli_sync.subsync.measure_offset", measure),
        ):
            cli_module.cmd_watch(query="Show", autoplay=True, sub_sync="auto")

        return build_mpv, measure, probe, update

    def test_every_episode_is_measured_again(self):
        _, measure, _, _ = self._drive(measurements=(_result(-3.37), _result(0.25, onset=21.79, first_cue=21.54)))
        self.assertEqual(measure.call_count, 2, "episode 3 reused episode 2's measurement")

    def test_each_episode_gets_its_own_offset(self):
        build_mpv, _, _, _ = self._drive(
            measurements=(_result(-3.37), _result(0.25, onset=21.79, first_cue=21.54))
        )
        self.assertEqual([c.kwargs["sub_delay"] for c in build_mpv.call_args_list], [-3.37, 0.25])

if __name__ == "__main__":
    unittest.main()