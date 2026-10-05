from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from ani_cli_sync.cli import _should_advance  # noqa: E402


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
        # A skipped intro means elapsed sits a little under duration; 90% is the floor.
        advance, _ = _should_advance(0, 1440.0 * 0.90, self.DURATION)
        self.assertTrue(advance)

    def test_just_under_threshold_does_not_advance(self):
        advance, _ = _should_advance(0, 1440.0 * 0.80, self.DURATION)
        self.assertFalse(advance)

    def test_unknown_duration_falls_back_to_conservative_threshold(self):
        # Duration unavailable: require a full-length episode's worth of playback
        # rather than the old flat 600s, which a 24-minute episode passes mid-watch.
        advance, _ = _should_advance(0, 660.0, None)
        self.assertFalse(advance)
        advance, _ = _should_advance(0, 1400.0, None)
        self.assertTrue(advance)

    def test_unknown_duration_nonzero_exit_still_stops(self):
        advance, _ = _should_advance(2, 1500.0, None)
        self.assertFalse(advance)


if __name__ == "__main__":
    unittest.main()