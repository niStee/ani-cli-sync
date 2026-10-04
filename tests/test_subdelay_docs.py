from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestSubDelayIsPerEpisode(unittest.TestCase):
    """A dub offset is a property of an individual subtitle file, not of a series.

    Measured on Attack on Titan S1: ep 1 needs -3.8 (first cue 41.870, JP audio ~38s),
    ep 2 needs ~0 (first cue 21.540, JP audio ~22s). Both came from the same release and
    the same provider, so an offset measured on one episode mis-times the next.
    """

    def setUp(self):
        self.agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.cli = (REPO_ROOT / "src" / "ani_cli_sync" / "cli.py").read_text(encoding="utf-8")

    def test_agents_md_states_offset_is_per_episode(self):
        self.assertRegex(
            self.agents,
            r"(?i)offset is per-episode, not per-show",
            "AGENTS.md must state that the offset is per-episode; a reader who misses this "
            "will carry one episode's value onto the next",
        )

    def test_agents_md_does_not_advise_a_per_show_default(self):
        # A global env-var default is the specific footgun: it silently applies one
        # episode's offset to every episode of every show.
        self.assertNotRegex(
            self.agents,
            r"ANI_CLI_SYNC_SUB_DELAY=-3\.8",
            "AGENTS.md must not recommend a concrete global default; the offset is "
            "per-episode and a global value mis-times everything it touches",
        )

    def test_flag_help_warns_about_per_episode_variation(self):
        self.assertRegex(
            self.cli,
            r"(?i)per[- ]episode",
            "--sub-delay help text must warn that the value varies per episode, so the "
            "warning is visible at the point of use and not only in the docs",
        )

    def test_flag_help_states_the_direction(self):
        self.assertRegex(
            self.cli,
            r"(?i)negative pulls subs earlier",
            "--sub-delay help must keep stating that negative values pull subs earlier",
        )


if __name__ == "__main__":
    unittest.main()