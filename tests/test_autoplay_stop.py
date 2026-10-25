from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from ani_cli_sync.cli import _calculate_skip_seconds, _should_advance


class TestAutoplayStopSemantics(unittest.TestCase):
    """Closing the player must stop the chain.

    Two paths previously advanced to the next episode when the user had explicitly
    stopped:

    1. A non-zero mpv exit skipped the early-stop branch entirely, because that branch
       lived inside ``if ret.returncode == 0``. Closing the player window can exit
       non-zero, so the episode looked "played successfully".
    2. A zero exit after 600s or more counted as "watched", so closing the window 11
       minutes into a 24-minute episode started the next one.

    Only positive evidence that an episode played through may advance the chain.
    """

    DURATION = 1440.0

    def test_nonzero_exit_never_advances(self):
        advance, reason = _should_advance(1, 60.0, self.DURATION)
        self.assertFalse(advance)
        self.assertIn("exit", reason)

    def test_nonzero_exit_after_full_duration_does_not_advance(self):
        # The spec's known-duration scenario: the whole episode was watched, then the
        # player ended abnormally. Elapsed time alone would have cleared every
        # threshold, so only the exit status can stop the chain here.
        advance, reason = _should_advance(1, 1440.0, self.DURATION)
        self.assertFalse(advance)
        self.assertIn("exit", reason)

    def test_nonzero_exit_after_skips_does_not_advance(self):
        # The spec's skip scenario: 1463s total, 176s skipped, 1308s elapsed. Under
        # the skip-aware ratio this is comfortably past the threshold, so the exit
        # status is the only thing that can stop the chain.
        advance, reason = _should_advance(1, 1308.0, 1463.0, skip_seconds=176.0)
        self.assertFalse(advance)
        self.assertIn("exit", reason)

    def test_abnormal_exit_reason_names_the_exit_not_the_duration(self):
        # The stop reason is user-visible ("Playback stopped (..., {why})"), so the
        # abnormal exit must be the reported cause rather than a duration shortfall.
        # A duration-based reason would tell the user the episode was too short when
        # the player had actually failed.
        _, reason = _should_advance(1, 60.0, self.DURATION)
        self.assertIn("exit", reason)
        self.assertNotIn("stopped after", reason)

        # The positive half of the pair: a normal early quit still reports the
        # duration, so the two causes remain distinguishable.
        _, reason = _should_advance(0, 60.0, self.DURATION)
        self.assertIn("stopped after", reason)
        self.assertNotIn("exit", reason)

    def test_closing_after_ten_minutes_does_not_advance(self):
        # 660s into a 1440s episode: the user closed the window.
        advance, reason = _should_advance(0, 660.0, self.DURATION)
        self.assertFalse(advance)
        self.assertIn("660", reason)

    def test_quitting_immediately_does_not_advance(self):
        advance, _ = _should_advance(0, 3.0, self.DURATION)
        self.assertFalse(advance)

    def test_full_length_playback_advances(self):
        advance, reason = _should_advance(0, 1440.0, self.DURATION)
        self.assertTrue(advance, reason)

    def test_near_end_playback_advances(self):
        # A skipped intro means elapsed sits a little under duration.
        advance, _ = _should_advance(0, 1440.0 * 0.90, self.DURATION)
        self.assertTrue(advance)

    def test_eighty_percent_playback_without_skip_metadata_advances(self):
        # Manual OP/ED skip: 1260s of a 1440s episode (87.5%) or 80% baseline advances.
        advance, _ = _should_advance(0, 1440.0 * 0.80, self.DURATION)
        self.assertTrue(advance)

    def test_just_under_threshold_does_not_advance(self):
        # Stopping early at 70% (16.8 minutes into 24m) must halt autoplay.
        advance, _ = _should_advance(0, 1440.0 * 0.70, self.DURATION)
        self.assertFalse(advance)

    def test_skip_aware_playback_advances_when_intro_and_outro_skipped(self):
        # AoT S1 ep18 real scenario: 1463.5s total, 176s skipped via ani-skip, 1308s elapsed.
        # Under the old static 90% threshold (1317s), this falsely stopped.
        # With effective duration (1463.5 - 176 = 1287.5s), 1308s safely advances.
        advance, reason = _should_advance(0, 1308.0, 1463.5, skip_seconds=176.0)
        self.assertTrue(advance, reason)

    def test_playback_with_skips_and_recap_advances(self):
        # Attack on Titan Ep 15 case: 1463s duration, 176s skipped (OP+ED), 1028s elapsed.
        # Effective duration is 1287s; at the skip-aware ratio this is a played-through
        # episode, so the chain must continue.
        advance, reason = _should_advance(0, 1028.0, 1463.0, skip_seconds=176.0)
        self.assertTrue(advance, reason)

    def test_playback_with_skips_stops_when_closed_early(self):
        # Even with 177s skipped, quitting at 600s into a 1463s episode must not advance.
        advance, _ = _should_advance(0, 600.0, 1463.0, skip_seconds=177.0)
        self.assertFalse(advance)

    def test_no_skip_baseline_is_unchanged_below_80_percent(self):
        # The ratio relaxation must not leak into the no-skip regime: 1008s of 1440s
        # is 70% of the total duration, which is still below the 80% baseline.
        advance, _ = _should_advance(0, 1440.0 * 0.70, self.DURATION)
        self.assertFalse(advance)

    def test_no_skip_baseline_is_unchanged_above_80_percent(self):
        # The positive half of the pair: 1152s of 1440s is exactly 80% and advances.
        advance, reason = _should_advance(0, 1440.0 * 0.80, self.DURATION)
        self.assertTrue(advance, reason)

    def test_unknown_duration_falls_back_to_conservative_threshold(self):
        # Duration unavailable: require a full episode minus skipped OP/ED (1150s),
        # rejecting early quit at 10 minutes (660s).
        advance, _ = _should_advance(0, 660.0, None)
        self.assertFalse(advance)
        advance, _ = _should_advance(0, 1150.0, None)
        self.assertTrue(advance)

    def test_unknown_duration_nonzero_exit_still_stops(self):
        advance, _ = _should_advance(2, 1500.0, None)
        self.assertFalse(advance)

    def test_calculate_skip_seconds_sums_intro_and_outro(self):
        class MockStreamInfo:
            intro_skip = (128.0, 215.0)  # 87s
            outro_skip = (1359.0, 1448.0)  # 89s

        self.assertEqual(_calculate_skip_seconds(MockStreamInfo()), 176.0)
        self.assertEqual(_calculate_skip_seconds(None), 0.0)


if __name__ == "__main__":
    unittest.main()