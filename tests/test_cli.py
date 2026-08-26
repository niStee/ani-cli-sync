from __future__ import annotations

import unittest
import unittest.mock
from ani_cli_sync.cli import find_in_watching_list, resolve_episode_offset


class TestAniCliSync(unittest.TestCase):
    def setUp(self):
        self.sample_entries = [
            {
                "id": 1,
                "mediaId": 182255,
                "progress": 4,
                "media": {
                    "id": 182255,
                    "title": {
                        "english": "Frieren: Beyond Journey's End Season 2",
                        "romaji": "Sousou no Frieren 2nd Season",
                    },
                    "episodes": 10,
                },
            },
            {
                "id": 2,
                "mediaId": 120377,
                "progress": 3,
                "media": {
                    "id": 120377,
                    "title": {
                        "english": "Cyberpunk: Edgerunners",
                        "romaji": "Cyberpunk: Edgerunners",
                    },
                    "episodes": 10,
                },
            },
        ]

        self.multi_season_entries = [
            {
                "id": 1,
                "mediaId": 154587,
                "progress": 28,
                "media": {
                    "id": 154587,
                    "title": {
                        "english": "Frieren: Beyond Journey's End",
                        "romaji": "Sousou no Frieren",
                    },
                    "episodes": 28,
                },
            },
            {
                "id": 2,
                "mediaId": 182255,
                "progress": 4,
                "media": {
                    "id": 182255,
                    "title": {
                        "english": "Frieren: Beyond Journey's End Season 2",
                        "romaji": "Sousou no Frieren 2nd Season",
                    },
                    "episodes": 10,
                },
            },
        ]

    def test_find_by_substring(self):
        res = find_in_watching_list(self.sample_entries, "frieren")
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 182255)

    def test_find_by_romaji(self):
        res = find_in_watching_list(self.sample_entries, "sousou")
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 182255)

    def test_find_exact_season1(self):
        res = find_in_watching_list(self.multi_season_entries, "Sousou no Frieren")
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 154587)

    def test_find_exact_season2(self):
        res = find_in_watching_list(self.multi_season_entries, "Sousou no Frieren 2nd Season")
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 182255)

    def test_find_substring_season2(self):
        res = find_in_watching_list(self.multi_season_entries, "Season 2")
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 182255)

    def test_nonexistent(self):
        res = find_in_watching_list(self.sample_entries, "NonexistentAnime")
        self.assertIsNone(res)

    def test_empty_query(self):
        res = find_in_watching_list(self.sample_entries, "")
        self.assertIsNone(res)


class TestResolveEpisodeOffset(unittest.TestCase):
    """Unit tests for the episode-offset translation table."""

    # ── Frieren S2 ────────────────────────────────────────────────────────────
    def test_frieren_s2_ep1_maps_to_29(self):
        search, ep = resolve_episode_offset(
            "[01/10] Frieren: Beyond Journey's End Season 2 | Sousou no Frieren 2nd Season",
            "Sousou no Frieren 2nd Season",
            1,
        )
        self.assertEqual(ep, 29)

    def test_frieren_s2_ep10_maps_to_38(self):
        _, ep = resolve_episode_offset(
            "[10/10] Frieren: Beyond Journey's End Season 2 | Sousou no Frieren 2nd Season",
            "Sousou no Frieren 2nd Season",
            10,
        )
        self.assertEqual(ep, 38)

    def test_frieren_s2_preserves_search_title(self):
        search, _ = resolve_episode_offset(
            "[01/10] Frieren: Beyond Journey's End Season 2 | Sousou no Frieren 2nd Season",
            "Sousou no Frieren 2nd Season",
            1,
        )
        # No search override for Frieren — uses the romaji title as-is
        self.assertEqual(search, "Sousou no Frieren 2nd Season")

    # ── Slime S2 ──────────────────────────────────────────────────────────────
    def test_slime_s2_ep1_maps_to_25(self):
        search, ep = resolve_episode_offset(
            "[01/12] That Time I Got Reincarnated as a Slime Season 2 | Tensei Shitara Slime",
            "Tensei Shitara Slime",
            1,
        )
        self.assertEqual(ep, 25)
        self.assertEqual(search, "That Time I Got Reincarnated as a Slime Season 2")

    def test_slime_s2_part2_ep1_maps_to_37(self):
        search, ep = resolve_episode_offset(
            "[01/12] Slime Season 2 Part 2 | ...",
            "Tensei Shitara Slime",
            1,
        )
        self.assertEqual(ep, 37)
        self.assertEqual(search, "That Time I Got Reincarnated as a Slime Season 2 Part 2")

    # ── Identity (no offset) ──────────────────────────────────────────────────
    def test_no_offset_for_season1(self):
        search, ep = resolve_episode_offset(
            "[05/28] Frieren: Beyond Journey's End | Sousou no Frieren",
            "Sousou no Frieren",
            5,
        )
        self.assertEqual(ep, 5)
        self.assertEqual(search, "Sousou no Frieren")

    def test_no_offset_beyond_max_ep(self):
        """Episode > max_anilist_ep: offset must NOT be applied (avoid double-offset)."""
        _, ep = resolve_episode_offset(
            "[11/10] Frieren: Beyond Journey's End Season 2 | Sousou no Frieren 2nd Season",
            "Sousou no Frieren 2nd Season",
            11,
        )
        self.assertEqual(ep, 11)


class TestCmdSetGuard(unittest.TestCase):
    """Regression test: cmd_set must refuse episodes exceeding the season total."""

    def _make_media(self, episodes: int) -> dict:
        return {
            "id": 182255,
            "title": {"english": "Frieren: Beyond Journey's End Season 2", "romaji": "Sousou no Frieren 2nd Season"},
            "episodes": episodes,
        }

    def test_set_episode_exceeding_total_exits_with_error(self):
        """Passing an absolute scraper episode (e.g. 29) for a 10-ep S2 must not mark COMPLETED."""
        import ani_cli_sync.cli as cli_module

        media = self._make_media(10)

        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 1, "name": "u"}),
            unittest.mock.patch.object(cli_module, "get_watching_list", return_value=[]),
            unittest.mock.patch.object(cli_module, "search_anime", return_value=media),
            unittest.mock.patch.object(cli_module, "update_progress") as mock_update,
        ):
            with self.assertRaises(SystemExit) as ctx:
                cli_module.cmd_set("Frieren Season 2", 29)

        self.assertEqual(ctx.exception.code, 1)
        mock_update.assert_not_called()

    def test_set_episode_at_total_marks_completed(self):
        """Setting episode == total must mark COMPLETED (existing behaviour preserved)."""
        import ani_cli_sync.cli as cli_module

        media = self._make_media(10)

        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 1, "name": "u"}),
            unittest.mock.patch.object(cli_module, "get_watching_list", return_value=[]),
            unittest.mock.patch.object(cli_module, "search_anime", return_value=media),
            unittest.mock.patch.object(cli_module, "update_progress") as mock_update,
        ):
            cli_module.cmd_set("Frieren Season 2", 10)

        mock_update.assert_called_once_with("tok", 182255, 10, status="COMPLETED")


if __name__ == "__main__":
    unittest.main()
