from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

from ani_cli_sync.menu import (
    clean_title,
    ensure_menu_helper,
    prepare_menu_env,
    select_candidate,
)


class TestMenuSelector(unittest.TestCase):
    def test_clean_title(self):
        self.assertEqual(clean_title("High School DxD (Uncensored)"), "high school dxd")
        self.assertEqual(clean_title("High School DxD [AT-X]"), "high school dxd")
        self.assertEqual(clean_title("To LOVE-Ru (BD)"), "to love-ru")
        self.assertEqual(clean_title("Redo of Healer [Blu-ray]"), "redo of healer")
        self.assertEqual(clean_title("That Time I Got Reincarnated as a Slime Season 3"), "that time i got reincarnated as a slime season 3")

    def test_select_uncensored_preference_true(self):
        lines = [
            "1 High School DxD",
            "2 High School DxD (Uncensored)",
            "3 High School DxD New",
            "4 High School DxD New (Uncensored)",
        ]
        selected = select_candidate(lines, target_title="High School DxD", uncensored=True)
        self.assertEqual(selected, "2 High School DxD (Uncensored)")

    def test_select_uncensored_preference_false(self):
        lines = [
            "1 High School DxD",
            "2 High School DxD (Uncensored)",
            "3 High School DxD New",
            "4 High School DxD New (Uncensored)",
        ]
        selected = select_candidate(lines, target_title="High School DxD", uncensored=False)
        self.assertEqual(selected, "1 High School DxD")

    def test_select_season_specific_uncensored(self):
        lines = [
            "1 High School DxD",
            "2 High School DxD (Uncensored)",
            "3 High School DxD New",
            "4 High School DxD New (Uncensored)",
        ]
        selected = select_candidate(lines, target_title="High School DxD New", uncensored=True)
        self.assertEqual(selected, "4 High School DxD New (Uncensored)")

    def test_select_atx_and_bd_tags(self):
        lines_atx = [
            "1 High School DxD [TV]",
            "2 High School DxD [AT-X]",
        ]
        self.assertEqual(select_candidate(lines_atx, target_title="High School DxD", uncensored=True), "2 High School DxD [AT-X]")

        lines_bd = [
            "1 Shinmai Maou no Testament",
            "2 Shinmai Maou no Testament (BD)",
        ]
        self.assertEqual(select_candidate(lines_bd, target_title="Shinmai Maou no Testament", uncensored=True), "2 Shinmai Maou no Testament (BD)")

    def test_select_fallback_when_no_uncensored(self):
        lines = [
            "1 That Time I Got Reincarnated as a Slime",
            "2 That Time I Got Reincarnated as a Slime Season 2",
            "3 That Time I Got Reincarnated as a Slime Season 3",
        ]
        # Even if uncensored=True, should gracefully fall back to matching candidate without error
        selected = select_candidate(lines, target_title="That Time I Got Reincarnated as a Slime", uncensored=True)
        self.assertEqual(selected, "1 That Time I Got Reincarnated as a Slime")

    def test_select_unmatched_romaji_sibling_fallback(self):
        # When AniList romaji title does not directly match English scraper titles,
        # it should inspect the first candidate's siblings for an uncensored release.
        lines = [
            "1 The Testament of Sister New Devil",
            "2 The Testament of Sister New Devil (Uncensored)",
            "3 The Testament of Sister New Devil BURST",
            "4 The Testament of Sister New Devil BURST (Uncensored)",
        ]
        selected = select_candidate(lines, target_title="Shinmai Maou no Keiyakusha", uncensored=True)
        self.assertEqual(selected, "2 The Testament of Sister New Devil (Uncensored)")

    def test_select_empty_or_single_candidate(self):
        self.assertIsNone(select_candidate([]))
        self.assertEqual(select_candidate(["1 Solo Leveling"]), "1 Solo Leveling")


class TestMenuHelperEnvironment(unittest.TestCase):
    def test_ensure_menu_helper(self):
        with tempfile.TemporaryDirectory() as td:
            cache_dir = Path(td)
            script_path, bin_dir = ensure_menu_helper(cache_dir)
            self.assertTrue(script_path.is_file())
            self.assertTrue(os.access(script_path, os.X_OK))

            for alias in ("fzf", "rofi", "dmenu", "ani-cli-menu"):
                alias_path = bin_dir / alias
                self.assertTrue(alias_path.exists())
                self.assertTrue(os.access(alias_path, os.X_OK))

    def test_prepare_menu_env(self):
        with tempfile.TemporaryDirectory() as td:
            cache_dir = Path(td)
            env = prepare_menu_env(
                target_title="High School DxD",
                uncensored=True,
                base_env={"PATH": "/usr/bin:/bin"},
                cache_dir=cache_dir,
            )
            self.assertIn("ANI_CLI_MENU", env)
            self.assertEqual(env["ANI_CLI_SYNC_TARGET_TITLE"], "High School DxD")
            self.assertEqual(env["ANI_CLI_SYNC_UNCENSORED"], "1")
            self.assertTrue(env["PATH"].startswith(str(cache_dir)))


class TestEmbeddedSelectorEquivalence(unittest.TestCase):
    """menu.py carries the selector twice: the module function (what the unit suite
    covers) and the helper script embedded as a string (what ani-cli executes via
    ANI_CLI_MENU). If the two drift, tested behavior and shipped behavior diverge
    silently, so they are pinned to select identically."""

    FIXTURE_LINES: ClassVar[list[list[str]]] = [
        [
            "1 High School DxD",
            "2 High School DxD (Uncensored)",
            "3 High School DxD New",
            "4 High School DxD New (Uncensored)",
        ],
        ["1 High School DxD [TV]", "2 High School DxD [AT-X]"],
        # Both candidates carry an uncensored marker: with uncensored=False the
        # cut loops find no candidate and the selector must fall back to the
        # FIRST match (the final return), not the last.
        ["1 High School DxD (Uncensored)", "2 High School DxD (Uncensored)"],
        [
            "1 That Time I Got Reincarnated as a Slime",
            "2 That Time I Got Reincarnated as a Slime Season 2",
        ],
        [
            "1 The Testament of Sister New Devil",
            "2 The Testament of Sister New Devil (Uncensored)",
            "3 The Testament of Sister New Devil BURST",
        ],
        ["1 Solo Leveling"],
        [],
    ]
    TARGETS: ClassVar[list[str | None]] = [
        None,
        "High School DxD",
        "High School DxD New",
        "Shinmai Maou no Keiyakusha",
        "That Time I Got Reincarnated as a Slime",
        "No Such Title",
    ]

    def test_embedded_helper_selects_identically_to_module_selector(self):
        from ani_cli_sync.menu import _HELPER_SCRIPT_CODE, clean_title, select_candidate

        namespace: dict = {}
        exec(_HELPER_SCRIPT_CODE, namespace)  # noqa: S102 - executing the shipped helper source is the point of this parity test
        embedded_select = namespace["select_candidate"]
        embedded_clean = namespace["clean_title"]

        for title in ("High School DxD (Uncensored)", "To LOVE-Ru (BD)", "Redo of Healer [Blu-ray]", "SPY x FAMILY Part 2"):
            self.assertEqual(embedded_clean(title), clean_title(title), msg=f"clean_title drifted for {title!r}")

        for lines in self.FIXTURE_LINES:
            for target in self.TARGETS:
                for uncensored in (True, False):
                    with self.subTest(lines=lines, target=target, uncensored=uncensored):
                        self.assertEqual(
                            embedded_select(lines, target_title=target, uncensored=uncensored),
                            select_candidate(lines, target_title=target, uncensored=uncensored),
                        )


class TestSubstringGroupSelection(unittest.TestCase):
    """A target with no exact candidate still narrows to its normalized substring
    group before applying the cut preference."""

    LINES: ClassVar[list[str]] = ["1 High School DxD New", "2 High School DxD New (Uncensored)"]

    def test_substring_group_prefers_uncensored_cut(self):
        selected = select_candidate(self.LINES, target_title="High School DxD", uncensored=True)
        self.assertEqual(selected, "2 High School DxD New (Uncensored)")

    def test_substring_group_respects_censored_preference(self):
        selected = select_candidate(self.LINES, target_title="High School DxD", uncensored=False)
        self.assertEqual(selected, "1 High School DxD New")


if __name__ == "__main__":
    unittest.main()
