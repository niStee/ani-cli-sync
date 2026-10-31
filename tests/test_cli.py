from __future__ import annotations

import contextlib
import io
import os
import re
import stat
import sys
import tempfile
import unittest
import unittest.mock
import urllib.error
from pathlib import Path
from typing import ClassVar

REPO_ROOT = Path(__file__).resolve().parent.parent

from ani_cli_sync.cli import (
    compute_prequel_offset,
    find_in_watching_list,
    find_sequel,
    get_media_list_entry,
    has_table_offset_match,
    resolve_episode_offset,
)


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
        _, ep = resolve_episode_offset(
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
    def test_slime_s2_ep1_maps_to_1(self):
        search, ep = resolve_episode_offset(
            "[01/12] That Time I Got Reincarnated as a Slime Season 2 | Tensei Shitara Slime",
            "Tensei Shitara Slime",
            1,
        )
        self.assertEqual(ep, 1)
        self.assertEqual(search, "That Time I Got Reincarnated as a Slime Season 2")

    def test_slime_s2_part2_ep1_maps_to_1(self):
        search, ep = resolve_episode_offset(
            "[01/12] Slime Season 2 Part 2 | ...",
            "Tensei Shitara Slime",
            1,
        )
        self.assertEqual(ep, 1)
        self.assertEqual(search, "That Time I Got Reincarnated as a Slime Season 2 Part 2")

    # ── Slime S3 ──────────────────────────────────────────────────────────────
    def test_slime_s3_season3_ep1_maps_to_1(self):
        search, ep = resolve_episode_offset(
            "[01/24] That Time I Got Reincarnated as a Slime Season 3 | Tensei Shitara Slime Datta Ken 3rd Season",
            "Tensei Shitara Slime Datta Ken 3rd Season",
            1,
        )
        self.assertEqual(ep, 1)
        self.assertEqual(search, "That Time I Got Reincarnated as a Slime Season 3")

    def test_slime_s3_season3_ep24_maps_to_24(self):
        search, ep = resolve_episode_offset(
            "[24/24] That Time I Got Reincarnated as a Slime Season 3 | Tensei Shitara Slime Datta Ken 3rd Season",
            "Tensei Shitara Slime Datta Ken 3rd Season",
            24,
        )
        self.assertEqual(ep, 24)
        self.assertEqual(search, "That Time I Got Reincarnated as a Slime Season 3")

    def test_slime_s3_season3_ep_beyond_max_falls_through_to_identity(self):
        search, ep = resolve_episode_offset(
            "[25/24] That Time I Got Reincarnated as a Slime Season 3 | Tensei Shitara Slime Datta Ken 3rd Season",
            "Tensei Shitara Slime Datta Ken 3rd Season",
            25,
        )
        self.assertEqual(ep, 25)
        self.assertEqual(search, "Tensei Shitara Slime Datta Ken 3rd Season")

    def test_slime_s3_3rd_season_ep1_maps_to_1(self):
        search, ep = resolve_episode_offset(
            "[01/24] Tensei Shitara Slime Datta Ken 3rd Season",
            "Tensei Shitara Slime Datta Ken 3rd Season",
            1,
        )
        self.assertEqual(ep, 1)
        self.assertEqual(search, "That Time I Got Reincarnated as a Slime Season 3")

    def test_slime_s3_3rd_season_ep24_maps_to_24(self):
        search, ep = resolve_episode_offset(
            "[24/24] Tensei Shitara Slime Datta Ken 3rd Season",
            "Tensei Shitara Slime Datta Ken 3rd Season",
            24,
        )
        self.assertEqual(ep, 24)
        self.assertEqual(search, "That Time I Got Reincarnated as a Slime Season 3")

    def test_slime_s3_3rd_season_ep_beyond_max_falls_through_to_identity(self):
        _, ep = resolve_episode_offset(
            "[25/24] Tensei Shitara Slime Datta Ken 3rd Season",
            "Tensei Shitara Slime Datta Ken 3rd Season",
            25,
        )
        self.assertEqual(ep, 25)
    # ── Slime S4 ──────────────────────────────────────────────────────────────
    def test_slime_s4_season4_ep1_maps_to_1_with_computed_offset(self):
        search, ep = resolve_episode_offset(
            "[00/24] That Time I Got Reincarnated as a Slime Season 4 | Tensei Shitara Slime Datta Ken 4th Season",
            "Tensei Shitara Slime Datta Ken 4th Season",
            1,
            computed_offset=48,
        )
        self.assertEqual(ep, 1)
        self.assertEqual(search, "That Time I Got Reincarnated as a Slime Season 4")

    def test_slime_s4_4th_season_ep1_maps_to_1_with_computed_offset(self):
        search, ep = resolve_episode_offset(
            "[00/24] Tensei Shitara Slime Datta Ken 4th Season",
            "Tensei Shitara Slime Datta Ken 4th Season",
            1,
            computed_offset=48,
        )
        self.assertEqual(ep, 1)
        self.assertEqual(search, "That Time I Got Reincarnated as a Slime Season 4")

    # ── Identity (no offset) ──────────────────────────────────────────────────
    def test_no_offset_for_season1(self):
        search, ep = resolve_episode_offset(
            "[05/28] Frieren: Beyond Journey's End | Sousou no Frieren",
            "Sousou no Frieren",
            5,
        )
        self.assertEqual(ep, 5)
        self.assertEqual(search, "Sousou no Frieren")

    def test_non_slime_season3_resolves_to_identity(self):
        """Non-Slime Season 3 anime must NOT match Slime S3 offsets."""
        search, ep = resolve_episode_offset(
            "[01/13] The Rising of the Shield Hero Season 3 | Tate no Yuusha no Nariagari Season 3",
            "Tate no Yuusha no Nariagari Season 3",
            1,
        )
        self.assertEqual(ep, 1)
        self.assertEqual(search, "Tate no Yuusha no Nariagari Season 3")

    def test_non_slime_part_2_resolves_to_identity(self):
        """Non-Slime 'Part 2' anime must NOT match Slime S2 Part 2 offsets."""
        search, ep = resolve_episode_offset(
            "[00/10] Attack on Titan Season 3 Part 2 | Shingeki no Kyojin Season 3 Part 2",
            "Shingeki no Kyojin Season 3 Part 2",
            1,
        )
        self.assertEqual(ep, 1)
        self.assertEqual(search, "Shingeki no Kyojin Season 3 Part 2")

        search_sxf, ep_sxf = resolve_episode_offset(
            "[00/13] SPY x FAMILY Part 2 | SPY×FAMILY Part 2",
            "SPY×FAMILY Part 2",
            1,
        )
        self.assertEqual(ep_sxf, 1)
        self.assertEqual(search_sxf, "SPY×FAMILY Part 2")

    def test_episode_offsets_table_no_bare_structural_tokens(self):
        """_EPISODE_OFFSETS fragments must be anchored to franchise titles, not bare tokens like 'Part 2'."""
        import re

        from ani_cli_sync.cli import _EPISODE_OFFSETS

        bare_token_pattern = re.compile(r"^(part|season|cour)\s*\d+$", re.IGNORECASE)
        for fragment, search_override, _, _ in _EPISODE_OFFSETS:
            self.assertFalse(
                bare_token_pattern.match(fragment.strip()),
                f"_EPISODE_OFFSETS fragment '{fragment}' is a bare structural token without franchise context",
            )
            self.assertGreaterEqual(
                len(fragment.strip()),
                6,
                f"_EPISODE_OFFSETS fragment '{fragment}' is suspiciously short",
            )

    # ── Attack on Titan: The Final Season ─────────────────────────────────────
    # The provider released Part 1 and Part 2 as separate titles, and AniList's
    # relation graph does not express that split the way the prequel walker
    # expects. Without a static table entry the walker sums unrelated seasons
    # and the episode number lands far outside the requested season.
    def test_aot_final_season_part1_ep1_resolves_to_part1(self):
        """Part 1 resolves to its own release with the season-relative episode number."""
        search, ep = resolve_episode_offset(
            "[00/16] Attack on Titan Final Season | Shingeki no Kyojin: The Final Season",
            "Shingeki no Kyojin: The Final Season",
            1,
            computed_offset=59,
        )
        self.assertEqual(ep, 1)
        self.assertEqual(search, "Attack on Titan: Final Season, Part 1")

    def test_aot_final_season_part2_ep1_resolves_to_part2(self):
        """Part 2 resolves to its own release with the season-relative episode number."""
        search, ep = resolve_episode_offset(
            "[00/12] Attack on Titan Final Season Part 2 | Shingeki no Kyojin: The Final Season Part 2",
            "Shingeki no Kyojin: The Final Season Part 2",
            1,
            computed_offset=75,
        )
        self.assertEqual(ep, 1)
        self.assertEqual(search, "Attack on Titan: Final Season, Part 2")

    def test_aot_part2_title_does_not_match_the_part1_entry(self):
        """The Part 1 fragment is a substring of the Part 2 title; Part 2 must win.

        This is the ordering constraint: with the Part 1 entry listed first,
        every Part 2 episode would be sent to the Part 1 release.
        """
        search, ep = resolve_episode_offset(
            "[00/12] Attack on Titan Final Season Part 2 | Attack on Titan: The Final Season Part 2",
            "Attack on Titan: The Final Season Part 2",
            5,
            computed_offset=75,
        )
        self.assertEqual(ep, 5)
        self.assertEqual(search, "Attack on Titan: Final Season, Part 2")

    def test_aot_episode_beyond_season_bound_is_not_remapped(self):
        """A season bound keeps an out-of-range episode out of the table entry."""
        search, ep = resolve_episode_offset(
            "[00/16] Attack on Titan Final Season | Shingeki no Kyojin: The Final Season",
            "Shingeki no Kyojin: The Final Season",
            17,
            computed_offset=59,
        )
        self.assertNotEqual(search, "Attack on Titan: Final Season, Part 1")
        self.assertNotEqual(ep, 17)

    def test_aot_table_entry_does_not_displace_the_computed_prequel_offset(self):
        """Negative half of the pair: an unlisted series still uses the computed chain."""
        search, ep = resolve_episode_offset(
            "[00/12] Some Unlisted Series Season 2 | Some Unlisted Series 2",
            "Some Unlisted Series 2",
            3,
            computed_offset=12,
        )
        self.assertEqual(ep, 15)
        self.assertEqual(search, "Some Unlisted Series 2")

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
            self.assertRaises(SystemExit) as ctx,
        ):
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


class TestWatchQueryFallback(unittest.TestCase):
    """When --autoplay is given a query that isn't in CURRENT, fall back to global
    AniList search instead of dying on a non-tty fzf spawn (regression: 'inappropriate
    ioctl for device' when launched without a controlling terminal)."""

    def setUp(self):
        import warnings
        self._warn_ctx = warnings.catch_warnings()
        self._warn_ctx.__enter__()
        warnings.simplefilter("ignore", ResourceWarning)

    def tearDown(self):
        self._warn_ctx.__exit__(None, None, None)

    def _make_media(self, mid, romaji, english, episodes):
        return {
            "id": mid,
            "title": {"romaji": romaji, "english": english},
            "episodes": episodes,
        }

    def test_autoplay_query_not_in_watching_falls_back_to_global_search(self):
        import ani_cli_sync.cli as cli_module

        aot = self._make_media(16498, "Shingeki no Kyojin", "Attack on Titan", 25)

        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 1, "name": "u"}),
            unittest.mock.patch.object(cli_module, "get_watching_list", return_value=[]),
            unittest.mock.patch.object(cli_module, "search_anime", return_value=aot) as mock_search,
            unittest.mock.patch.object(cli_module, "update_progress") as mock_update,
            unittest.mock.patch.object(cli_module, "subprocess") as mock_sub,
            unittest.mock.patch("sys.stdout"),
            # resolve_stream_info runs the real `ani-cli debug`, so this test reaches the
            # subtitle pipeline and used to depend on the CDN rejecting the fetch. With the
            # Referer fix the fetch succeeds and the run continued into real LLM
            # translation, hanging the suite. Emulate the old outcome without a network.
            unittest.mock.patch(
                "ani_cli_sync.subtitles.fetch_vtt_text",
                side_effect=urllib.error.URLError("network disabled in unit test"),
            ),
            unittest.mock.patch("ani_cli_sync.subtitles.translate_cues_llm", return_value=None),
            # The watch loop's lookahead daemon thread (target
            # prefetch_next_episode) starts once a stream resolves. Stub it at
            # the ani_cli_sync.subtitles boundary (the function-local import
            # site in the watch loop) so no real resolve/prepare work outlives
            # this mock context and races into later tests.
            unittest.mock.patch("ani_cli_sync.subtitles.prefetch_next_episode"),
        ):
            cli_module.cmd_watch(query="Attack on Titan", autoplay=True, quality=None, dub=False)

        mock_search.assert_called_once_with("Attack on Titan")
        mock_update.assert_called_once_with("tok", 16498, 1, status="CURRENT")
        self.assertTrue(mock_sub.Popen.called or mock_sub.run.called)

    def test_autoplay_query_no_global_match_exits_cleanly_without_fzf(self):
        import ani_cli_sync.cli as cli_module

        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 1, "name": "u"}),
            unittest.mock.patch.object(cli_module, "get_watching_list", return_value=[]),
            unittest.mock.patch.object(cli_module, "search_anime", return_value=None),
            unittest.mock.patch.object(cli_module, "update_progress") as mock_update,
            unittest.mock.patch.object(cli_module, "subprocess") as mock_sub,
            unittest.mock.patch("sys.stdout"),
        ):
            cli_module.cmd_watch(query="Nonexistent Anime XYZ", autoplay=True, quality=None, dub=False)

        mock_update.assert_not_called()
        mock_sub.Popen.assert_not_called()
        mock_sub.run.assert_not_called()


class TestComputePrequelOffset(unittest.TestCase):
    """Unit tests for compute_prequel_offset PREQUEL chain traversal."""

    def test_slime_prequel_chain_computes_48(self):
        # S3 (300) -> S2 P2 (202, 12 eps) -> S2 P1 (201, 12 eps) -> S1 (100, 24 eps) -> None
        responses = {
            300: {
                "data": {
                    "Media": {
                        "relations": {
                            "edges": [{"relationType": "PREQUEL", "node": {"id": 202, "episodes": 12, "format": "TV"}}]
                        }
                    }
                }
            },
            202: {
                "data": {
                    "Media": {
                        "relations": {
                            "edges": [{"relationType": "PREQUEL", "node": {"id": 201, "episodes": 12, "format": "TV"}}]
                        }
                    }
                }
            },
            201: {
                "data": {
                    "Media": {
                        "relations": {
                            "edges": [{"relationType": "PREQUEL", "node": {"id": 100, "episodes": 24, "format": "TV"}}]
                        }
                    }
                }
            },
            100: {"data": {"Media": {"relations": {"edges": []}}}},
        }

        def mock_gql(_query, variables):
            return responses.get(variables["id"], {"data": {"Media": {"relations": {"edges": []}}}})

        offset = compute_prequel_offset(300, mock_gql)
        self.assertEqual(offset, 48)

    def test_excludes_ova_and_special_nodes(self):
        # S2 (200) -> PREQUEL OVA (150, 2 eps), PREQUEL TV (100, 12 eps) -> TV chosen
        responses = {
            200: {
                "data": {
                    "Media": {
                        "relations": {
                            "edges": [
                                {"relationType": "PREQUEL", "node": {"id": 150, "episodes": 2, "format": "OVA"}},
                                {"relationType": "PREQUEL", "node": {"id": 100, "episodes": 12, "format": "TV"}},
                            ]
                        }
                    }
                }
            },
            100: {"data": {"Media": {"relations": {"edges": []}}}},
        }

        def mock_gql(_query, variables):
            return responses.get(variables["id"], {"data": {"Media": {"relations": {"edges": []}}}})

        offset = compute_prequel_offset(200, mock_gql)
        self.assertEqual(offset, 12)

    def test_null_episodes_returns_none(self):
        responses = {
            200: {
                "data": {
                    "Media": {
                        "relations": {
                            "edges": [{"relationType": "PREQUEL", "node": {"id": 100, "episodes": None, "format": "TV"}}]
                        }
                    }
                }
            },
        }

        def mock_gql(_query, variables):
            return responses.get(variables["id"], {"data": {"Media": {"relations": {"edges": []}}}})

        self.assertIsNone(compute_prequel_offset(200, mock_gql))

    def test_cycle_detection_returns_none(self):
        responses = {
            1: {
                "data": {
                    "Media": {
                        "relations": {
                            "edges": [{"relationType": "PREQUEL", "node": {"id": 2, "episodes": 12, "format": "TV"}}]
                        }
                    }
                }
            },
            2: {
                "data": {
                    "Media": {
                        "relations": {
                            "edges": [{"relationType": "PREQUEL", "node": {"id": 1, "episodes": 12, "format": "TV"}}]
                        }
                    }
                }
            },
        }

        def mock_gql(_query, variables):
            return responses.get(variables["id"], {"data": {"Media": {"relations": {"edges": []}}}})

        self.assertIsNone(compute_prequel_offset(1, mock_gql))

    def test_ambiguous_multiple_tv_prequels_returns_none(self):
        responses = {
            200: {
                "data": {
                    "Media": {
                        "relations": {
                            "edges": [
                                {"relationType": "PREQUEL", "node": {"id": 101, "episodes": 12, "format": "TV"}},
                                {"relationType": "PREQUEL", "node": {"id": 102, "episodes": 12, "format": "TV"}},
                            ]
                        }
                    }
                }
            },
        }

        def mock_gql(_query, variables):
            return responses.get(variables["id"], {"data": {"Media": {"relations": {"edges": []}}}})

        self.assertIsNone(compute_prequel_offset(200, mock_gql))

    def test_no_prequels_returns_zero(self):
        responses = {
            100: {"data": {"Media": {"relations": {"edges": []}}}},
        }

        def mock_gql(_query, variables):
            return responses.get(variables["id"], {"data": {"Media": {"relations": {"edges": []}}}})

        self.assertEqual(compute_prequel_offset(100, mock_gql), 0)

    def test_api_exception_returns_none(self):
        def mock_gql(_query, _variables):
            raise RuntimeError("API error")

        self.assertIsNone(compute_prequel_offset(100, mock_gql))


class TestOffsetPrecedence(unittest.TestCase):
    """Unit tests for the strict precedence: table > computed > identity."""

    def test_table_entry_beats_computed_value(self):
        # Slime Season 3 is in table (+0 with search override)
        search, ep = resolve_episode_offset(
            "[01/24] That Time I Got Reincarnated as a Slime Season 3",
            "Tensei Shitara Slime Datta Ken 3rd Season",
            1,
            computed_offset=999,
        )
        self.assertEqual(ep, 1)  # 1 + 0 (table), not 1 + 999
        self.assertEqual(search, "That Time I Got Reincarnated as a Slime Season 3")

    def test_overlord_iii_independent_numbering(self):
        search, ep = resolve_episode_offset(
            "[00/13] Overlord III | Overlord III",
            "Overlord III",
            1,
            computed_offset=26,
        )
        self.assertEqual(ep, 1)
        self.assertEqual(search, "Overlord III")

    def test_computed_used_when_table_misses(self):
        search, ep = resolve_episode_offset(
            "[01/12] Unlisted Anime Season 2",
            "Unlisted Anime Season 2",
            1,
            computed_offset=24,
        )
        self.assertEqual(ep, 25)
        self.assertEqual(search, "Unlisted Anime Season 2")

    def test_identity_when_both_miss(self):
        search, ep = resolve_episode_offset(
            "[01/12] Unlisted Anime Season 2",
            "Unlisted Anime Season 2",
            1,
            computed_offset=None,
        )
        self.assertEqual(ep, 1)
        self.assertEqual(search, "Unlisted Anime Season 2")


class TestSequelRollover(unittest.TestCase):
    """Unit tests for sequel rollover in cmd_watch."""

    def setUp(self):
        self.s1_entry = {
            "id": 1,
            "mediaId": 100,
            "progress": 11,
            "media": {
                "id": 100,
                "title": {"english": "Show Season 1", "romaji": "Show S1"},
                "episodes": 12,
            },
        }

    def _run_cmd_watch(
        self,
        watching_entries: list[dict],
        relations_resp: dict | None,
        medialist_resp: dict | None,
        input_responses: list[str],
        autoplay: bool = False,
    ) -> tuple[unittest.mock.MagicMock, unittest.mock.MagicMock]:
        import ani_cli_sync.cli as cli_module

        cli_module._PREQUEL_OFFSET_CACHE.clear()

        def mock_gql(query, variables=None, token=None, retries=3):
            if "relations" in query:
                if relations_resp is not None:
                    return relations_resp
                return {"data": {"Media": {"relations": {"edges": []}}}}
            if "MediaList" in query:
                if medialist_resp is not None:
                    return medialist_resp
                raise RuntimeError("Not Found.")
            return {}

        mock_update = unittest.mock.MagicMock()
        mock_subproc = unittest.mock.MagicMock(return_value=unittest.mock.MagicMock(returncode=0))
        input_iter = iter(input_responses)

        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 42, "name": "nils"}),
            unittest.mock.patch.object(cli_module, "get_watching_list", return_value=watching_entries),
            unittest.mock.patch.object(cli_module, "gql_query", side_effect=mock_gql),
            unittest.mock.patch.object(cli_module, "update_progress", mock_update),
            unittest.mock.patch.object(cli_module.subprocess, "run", mock_subproc),
            unittest.mock.patch("builtins.input", side_effect=lambda *_: next(input_iter)),
            unittest.mock.patch.object(
                cli_module.time, "time", side_effect=[0.0, 1450.0, 1450.0, 2900.0, 2900.0, 4400.0]
            ),
            unittest.mock.patch.object(cli_module.time, "sleep"),
        ):
            cli_module.cmd_watch(query="Show", autoplay=autoplay, no_sub_fallback=True)

        return mock_update, mock_subproc

    def test_sequel_interactive_accept(self):
        """Sequel found + interactive accept -> enrolled at 0/CURRENT, loop continues at ep 1."""
        relations_resp = {
            "data": {
                "Media": {
                    "relations": {
                        "edges": [
                            {
                                "relationType": "SEQUEL",
                                "node": {
                                    "id": 200,
                                    "title": {"english": "Show Season 2", "romaji": "Show S2"},
                                    "episodes": 12,
                                    "format": "TV",
                                    "status": "FINISHED",
                                },
                            }
                        ]
                    }
                }
            }
        }
        mock_update, mock_subproc = self._run_cmd_watch(
            watching_entries=[self.s1_entry],
            relations_resp=relations_resp,
            medialist_resp=None,  # No existing entry in MediaList
            input_responses=["y", "q"],
            autoplay=False,
        )

        # Expected updates: S1 completed at ep 12, S2 enrolled at ep 0 [CURRENT], S2 ep 1 finished [CURRENT]
        self.assertIn(unittest.mock.call("tok", 100, 12, status="COMPLETED"), mock_update.call_args_list)
        self.assertIn(unittest.mock.call("tok", 200, 0, status="CURRENT"), mock_update.call_args_list)
        self.assertIn(unittest.mock.call("tok", 200, 1, status="CURRENT"), mock_update.call_args_list)

        # Expected subprocess runs: S1 ep 12, then S2 ep 1
        self.assertEqual(mock_subproc.call_count, 2)
        cmd_s1 = mock_subproc.call_args_list[0][0][0]
        cmd_s2 = mock_subproc.call_args_list[1][0][0]
        self.assertEqual(cmd_s1[-3:], ["-e", "12", "Show S1"])
        self.assertEqual(cmd_s2[-3:], ["-e", "1", "Show S2"])

    def test_sequel_interactive_decline(self):
        """Interactive decline (empty input) -> no sequel mutation, loop breaks."""
        relations_resp = {
            "data": {
                "Media": {
                    "relations": {
                        "edges": [
                            {
                                "relationType": "SEQUEL",
                                "node": {
                                    "id": 200,
                                    "title": {"english": "Show Season 2", "romaji": "Show S2"},
                                    "episodes": 12,
                                    "format": "TV",
                                    "status": "FINISHED",
                                },
                            }
                        ]
                    }
                }
            }
        }
        mock_update, mock_subproc = self._run_cmd_watch(
            watching_entries=[self.s1_entry],
            relations_resp=relations_resp,
            medialist_resp=None,
            input_responses=[""],  # Decline
            autoplay=False,
        )

        # Only S1 completed, no S2 mutation
        mock_update.assert_called_once_with("tok", 100, 12, status="COMPLETED")
        self.assertEqual(mock_subproc.call_count, 1)

    def test_sequel_autoplay(self):
        """Autoplay -> enroll + continue without prompt."""
        relations_resp = {
            "data": {
                "Media": {
                    "relations": {
                        "edges": [
                            {
                                "relationType": "SEQUEL",
                                "node": {
                                    "id": 200,
                                    "title": {"english": "Show Season 2", "romaji": "Show S2"},
                                    "episodes": 12,
                                    "format": "TV",
                                    "status": "FINISHED",
                                },
                            }
                        ]
                    }
                }
            }
        }
        import ani_cli_sync.cli as cli_module

        cli_module._PREQUEL_OFFSET_CACHE.clear()

        def mock_gql(query, variables=None, token=None, retries=3):
            if "relations" in query:
                return relations_resp
            if "MediaList" in query:
                raise RuntimeError("Not Found.")
            return {}

        mock_update = unittest.mock.MagicMock()
        mock_subproc = unittest.mock.MagicMock(
            side_effect=[
                unittest.mock.MagicMock(returncode=0),
                unittest.mock.MagicMock(returncode=0),
                unittest.mock.MagicMock(returncode=1),
            ]
        )

        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 42, "name": "nils"}),
            unittest.mock.patch.object(cli_module, "get_watching_list", return_value=[self.s1_entry]),
            unittest.mock.patch.object(cli_module, "gql_query", side_effect=mock_gql),
            unittest.mock.patch.object(cli_module, "update_progress", mock_update),
            unittest.mock.patch.object(cli_module.subprocess, "run", mock_subproc),
            unittest.mock.patch.object(
                cli_module.time, "time", side_effect=[0.0, 1450.0, 1450.0, 2900.0, 2900.0, 4400.0]
            ),
            unittest.mock.patch.object(cli_module.time, "sleep"),
        ):
            cli_module.cmd_watch(query="Show", autoplay=True, no_sub_fallback=True)

        self.assertIn(unittest.mock.call("tok", 100, 12, status="COMPLETED"), mock_update.call_args_list)
        self.assertIn(unittest.mock.call("tok", 200, 0, status="CURRENT"), mock_update.call_args_list)
        self.assertIn(unittest.mock.call("tok", 200, 1, status="CURRENT"), mock_update.call_args_list)

    def test_sequel_not_yet_released_no_mutation(self):
        """NOT_YET_RELEASED sequel -> no mutation."""
        relations_resp = {
            "data": {
                "Media": {
                    "relations": {
                        "edges": [
                            {
                                "relationType": "SEQUEL",
                                "node": {
                                    "id": 200,
                                    "title": {"english": "Show Season 2", "romaji": "Show S2"},
                                    "episodes": 12,
                                    "format": "TV",
                                    "status": "NOT_YET_RELEASED",
                                },
                            }
                        ]
                    }
                }
            }
        }
        mock_update, mock_subproc = self._run_cmd_watch(
            watching_entries=[self.s1_entry],
            relations_resp=relations_resp,
            medialist_resp=None,
            input_responses=[],
            autoplay=False,
        )

        mock_update.assert_called_once_with("tok", 100, 12, status="COMPLETED")
        self.assertEqual(mock_subproc.call_count, 1)

    def test_sequel_clobber_guard_existing_progress(self):
        """Existing sequel entry at progress 5 -> NO reset, resumes at ep 6."""
        relations_resp = {
            "data": {
                "Media": {
                    "relations": {
                        "edges": [
                            {
                                "relationType": "SEQUEL",
                                "node": {
                                    "id": 200,
                                    "title": {"english": "Show Season 2", "romaji": "Show S2"},
                                    "episodes": 12,
                                    "format": "TV",
                                    "status": "FINISHED",
                                },
                            }
                        ]
                    }
                }
            }
        }
        medialist_resp = {
            "data": {
                "MediaList": {
                    "status": "PAUSED",
                    "progress": 5,
                }
            }
        }
        mock_update, mock_subproc = self._run_cmd_watch(
            watching_entries=[self.s1_entry],
            relations_resp=relations_resp,
            medialist_resp=medialist_resp,
            input_responses=["y", "q"],
            autoplay=False,
        )

        # S1 completed; S2 status set to CURRENT with progress 5 (NOT 0); then ep 6 finished [CURRENT]
        self.assertIn(unittest.mock.call("tok", 100, 12, status="COMPLETED"), mock_update.call_args_list)
        self.assertIn(unittest.mock.call("tok", 200, 5, status="CURRENT"), mock_update.call_args_list)
        self.assertNotIn(unittest.mock.call("tok", 200, 0, status="CURRENT"), mock_update.call_args_list)
        self.assertIn(unittest.mock.call("tok", 200, 6, status="CURRENT"), mock_update.call_args_list)

        # 2nd subprocess run should be for ep 6
        cmd_s2 = mock_subproc.call_args_list[1][0][0]
        self.assertEqual(cmd_s2[-3:], ["-e", "6", "Show S2"])

    def test_sequel_ambiguous_multiple_tv_no_mutation(self):
        """Ambiguous (two TV sequels) -> no mutation."""
        relations_resp = {
            "data": {
                "Media": {
                    "relations": {
                        "edges": [
                            {
                                "relationType": "SEQUEL",
                                "node": {
                                    "id": 201,
                                    "title": {"english": "Show S2 Route A", "romaji": "Show S2 A"},
                                    "episodes": 12,
                                    "format": "TV",
                                    "status": "FINISHED",
                                },
                            },
                            {
                                "relationType": "SEQUEL",
                                "node": {
                                    "id": 202,
                                    "title": {"english": "Show S2 Route B", "romaji": "Show S2 B"},
                                    "episodes": 12,
                                    "format": "TV",
                                    "status": "FINISHED",
                                },
                            },
                        ]
                    }
                }
            }
        }
        mock_update, mock_subproc = self._run_cmd_watch(
            watching_entries=[self.s1_entry],
            relations_resp=relations_resp,
            medialist_resp=None,
            input_responses=[],
            autoplay=False,
        )

        mock_update.assert_called_once_with("tok", 100, 12, status="COMPLETED")
        self.assertEqual(mock_subproc.call_count, 1)

    def test_sequel_already_completed_no_mutation(self):
        """Sequel already marked COMPLETED -> no rollover, no mutation, loop breaks."""
        relations_resp = {
            "data": {
                "Media": {
                    "relations": {
                        "edges": [
                            {
                                "relationType": "SEQUEL",
                                "node": {
                                    "id": 200,
                                    "title": {"english": "Show Season 2", "romaji": "Show S2"},
                                    "episodes": 12,
                                    "format": "TV",
                                    "status": "FINISHED",
                                },
                            }
                        ]
                    }
                }
            }
        }
        medialist_resp = {
            "data": {
                "MediaList": {
                    "status": "COMPLETED",
                    "progress": 12,
                }
            }
        }
        mock_update, mock_subproc = self._run_cmd_watch(
            watching_entries=[self.s1_entry],
            relations_resp=relations_resp,
            medialist_resp=medialist_resp,
            input_responses=[],
            autoplay=False,
        )

        mock_update.assert_called_once_with("tok", 100, 12, status="COMPLETED")
        self.assertEqual(mock_subproc.call_count, 1)


class TestSequelHelpers(unittest.TestCase):
    """Unit tests for find_sequel, get_media_list_entry, and has_table_offset_match."""

    def setUp(self):
        # _probe_duration fetches the HLS media playlist over the network. Keep the
        # unit suite hermetic: an unknown duration falls back to the conservative
        # full-episode threshold, which is what these tests assert against.
        import ani_cli_sync.cli as cli_module

        patcher = unittest.mock.patch.object(cli_module, "_probe_duration", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)


    def test_find_sequel_returns_node_on_valid_sequel(self):
        resp = {
            "data": {
                "Media": {
                    "relations": {
                        "edges": [
                            {
                                "relationType": "SEQUEL",
                                "node": {
                                    "id": 200,
                                    "title": {"english": "Sequel", "romaji": "Sequel"},
                                    "episodes": 12,
                                    "format": "TV",
                                    "status": "FINISHED",
                                },
                            }
                        ]
                    }
                }
            }
        }
        with unittest.mock.patch("ani_cli_sync.cli.gql_query", return_value=resp):
            node, reason = find_sequel(100)
            self.assertIsNotNone(node)
            self.assertIsNone(reason)
            self.assertEqual(node["id"], 200)

    def test_find_sequel_not_yet_released(self):
        resp = {
            "data": {
                "Media": {
                    "relations": {
                        "edges": [
                            {
                                "relationType": "SEQUEL",
                                "node": {
                                    "id": 200,
                                    "title": {"english": "Sequel", "romaji": "Sequel"},
                                    "episodes": 12,
                                    "format": "TV",
                                    "status": "NOT_YET_RELEASED",
                                },
                            }
                        ]
                    }
                }
            }
        }
        with unittest.mock.patch("ani_cli_sync.cli.gql_query", return_value=resp):
            node, reason = find_sequel(100)
            self.assertIsNone(node)
            self.assertIn("announced, not yet released", reason)

    def test_find_sequel_ambiguous(self):
        resp = {
            "data": {
                "Media": {
                    "relations": {
                        "edges": [
                            {"relationType": "SEQUEL", "node": {"id": 201, "format": "TV"}},
                            {"relationType": "SEQUEL", "node": {"id": 202, "format": "TV"}},
                        ]
                    }
                }
            }
        }
        with unittest.mock.patch("ani_cli_sync.cli.gql_query", return_value=resp):
            node, reason = find_sequel(100)
            self.assertIsNone(node)
            self.assertIn("ambiguous", reason)

    def test_get_media_list_entry(self):
        resp = {"data": {"MediaList": {"status": "CURRENT", "progress": 3}}}
        with unittest.mock.patch("ani_cli_sync.cli.gql_query", return_value=resp):
            entry = get_media_list_entry("tok", 42, 100)
            self.assertEqual(entry, {"status": "CURRENT", "progress": 3})

    def test_get_media_list_entry_not_found(self):
        with unittest.mock.patch("ani_cli_sync.cli.gql_query", side_effect=RuntimeError("Not Found")):
            entry = get_media_list_entry("tok", 42, 100)
            self.assertIsNone(entry)

    def test_has_table_offset_match(self):
        self.assertTrue(has_table_offset_match("[01/24] That Time I Got Reincarnated as a Slime Season 3", 1))
        self.assertFalse(has_table_offset_match("[01/12] Unlisted Anime Season 2", 1))

    def test_cmd_watch_subtitles_fallback_mpv(self):
        import ani_cli_sync.cli as cli_module
        from ani_cli_sync.subtitles import StreamInfo, SubtitlePlan

        mock_update = unittest.mock.MagicMock()
        mock_subproc = unittest.mock.MagicMock(return_value=unittest.mock.MagicMock(returncode=0))
        mock_stream = StreamInfo(
            video_link="https://stream.example/1080/index.m3u8",
            referrer="https://zokoanime.video/",
            subtitles=[],
            intro_skip=(100.0, 190.0),
        )
        mock_plan = SubtitlePlan(
            sub_files=["/cache/de.vtt", "/cache/zh.vtt"],
            sid=1,
            secondary_sid=2,
        )

        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 42, "name": "nils"}),
            unittest.mock.patch.object(
                cli_module,
                "get_watching_list",
                return_value=[
                    {
                        "id": 1,
                        "mediaId": 100,
                        "progress": 0,
                        "media": {
                            "id": 100,
                            "title": {"english": "Show", "romaji": "Show"},
                            "episodes": 12,
                        },
                    }
                ],
            ),
            unittest.mock.patch("ani_cli_sync.subtitles.resolve_stream_info", return_value=mock_stream),
            unittest.mock.patch("ani_cli_sync.subtitles.prepare_subtitles", return_value=mock_plan),
            # The watch loop starts a daemon thread (target prefetch_next_episode)
            # once stream_info is truthy. Stub it at the ani_cli_sync.subtitles
            # boundary -- the watch loop imports it function-locally from there,
            # so this is the only patch site that intercepts it. Without the stub
            # the thread runs real resolve/prepare work after these patches expire
            # (observed racing into later tests' subprocess.run mocks).
            unittest.mock.patch("ani_cli_sync.subtitles.prefetch_next_episode"),
            unittest.mock.patch.object(cli_module, "update_progress", mock_update),
            unittest.mock.patch.object(cli_module.subprocess, "run", mock_subproc),
            unittest.mock.patch("builtins.input", return_value="q"),
            unittest.mock.patch.object(cli_module.time, "time", side_effect=[0.0, 700.0]),
        ):
            cli_module.cmd_watch(query="Show")

        self.assertTrue(mock_subproc.called)
        called_cmd = mock_subproc.call_args[0][0]
        self.assertEqual(called_cmd[0], "mpv")
        self.assertIn("--sub-file=/cache/de.vtt", called_cmd)
        self.assertIn("--sub-file=/cache/zh.vtt", called_cmd)
        self.assertIn("--sid=1", called_cmd)
        self.assertIn("--secondary-sid=2", called_cmd)

    def test_cmd_watch_no_sub_fallback(self):
        import ani_cli_sync.cli as cli_module

        mock_update = unittest.mock.MagicMock()
        mock_subproc = unittest.mock.MagicMock(return_value=unittest.mock.MagicMock(returncode=0))
        mock_resolve = unittest.mock.MagicMock()

        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 42, "name": "nils"}),
            unittest.mock.patch.object(
                cli_module,
                "get_watching_list",
                return_value=[
                    {
                        "id": 1,
                        "mediaId": 100,
                        "progress": 0,
                        "media": {
                            "id": 100,
                            "title": {"english": "Show", "romaji": "Show"},
                            "episodes": 12,
                        },
                    }
                ],
            ),
            unittest.mock.patch("ani_cli_sync.subtitles.resolve_stream_info", mock_resolve),
            unittest.mock.patch.object(cli_module, "update_progress", mock_update),
            unittest.mock.patch.object(cli_module.subprocess, "run", mock_subproc),
            unittest.mock.patch("builtins.input", return_value="q"),
            unittest.mock.patch.object(cli_module.time, "time", side_effect=[0.0, 700.0]),
        ):
            cli_module.cmd_watch(query="Show", no_sub_fallback=True)

        self.assertFalse(mock_resolve.called)
        called_cmd = mock_subproc.call_args[0][0]
        self.assertEqual(called_cmd[0], "ani-cli")

    def test_cmd_watch_passes_uncensored_to_resolve(self):
        import ani_cli_sync.cli as cli_module

        mock_update = unittest.mock.MagicMock()
        mock_subproc = unittest.mock.MagicMock(return_value=unittest.mock.MagicMock(returncode=0))
        mock_resolve = unittest.mock.MagicMock(return_value=None)

        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 42, "name": "nils"}),
            unittest.mock.patch.object(
                cli_module,
                "get_watching_list",
                return_value=[
                    {
                        "id": 1,
                        "mediaId": 100,
                        "progress": 0,
                        "media": {
                            "id": 100,
                            "title": {"english": "Show", "romaji": "Show"},
                            "episodes": 12,
                        },
                    }
                ],
            ),
            unittest.mock.patch("ani_cli_sync.subtitles.resolve_stream_info", mock_resolve),
            unittest.mock.patch.object(cli_module, "update_progress", mock_update),
            unittest.mock.patch.object(cli_module.subprocess, "run", mock_subproc),
            unittest.mock.patch("builtins.input", return_value="q"),
            unittest.mock.patch.object(cli_module.time, "time", side_effect=[0.0, 700.0]),
        ):
            cli_module.cmd_watch(query="Show", uncensored=True)

        self.assertTrue(mock_resolve.called)
        self.assertEqual(mock_resolve.call_args[1].get("uncensored"), True)
        called_cmd = mock_subproc.call_args[0][0]
        self.assertNotIn("-S", called_cmd)
        called_env = mock_subproc.call_args[1].get("env", {})
        self.assertEqual(called_env.get("ANI_CLI_SYNC_UNCENSORED"), "1")

    def test_cli_uncensored_args(self):
        import ani_cli_sync.cli as cli_module

        with unittest.mock.patch.object(cli_module, "cmd_watch") as mock_watch:
            with unittest.mock.patch("sys.argv", ["ani-cli-sync", "watch", "--no-uncensored", "Show"]):
                cli_module.main()
            mock_watch.assert_called_once()
            self.assertFalse(mock_watch.call_args[1]["uncensored"])

        with unittest.mock.patch.object(cli_module, "cmd_watch") as mock_watch:
            with unittest.mock.patch("sys.argv", ["ani-cli-sync", "watch", "--uncensored", "Show"]):
                cli_module.main()
            mock_watch.assert_called_once()
            self.assertTrue(mock_watch.call_args[1]["uncensored"])



class TestEpisodeProbeFallback(unittest.TestCase):
    """Unit tests for the two-pass probe and fallback when continuous offset fails."""

    def setUp(self):
        # _probe_duration fetches the HLS media playlist over the network. Keep the
        # unit suite hermetic: an unknown duration falls back to the conservative
        # full-episode threshold, which is what these tests assert against.
        import ani_cli_sync.cli as cli_module

        patcher = unittest.mock.patch.object(cli_module, "_probe_duration", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)


    def test_stream_resolution_probe_fallback_to_season_relative(self):
        """When resolve_stream_info fails on continuous ep (e.g. 25), retry season ep (1) and cache 0."""
        import ani_cli_sync.cli as cli_module
        from ani_cli_sync.subtitles import StreamInfo, SubtitlePlan

        cli_module._PREQUEL_OFFSET_CACHE.clear()

        mock_stream = StreamInfo(
            video_link="https://video.example.com/master.m3u8",
            referrer="https://zokoanime.video/",
            subtitles=[],
            intro_skip=None,
            outro_skip=None,
        )
        mock_plan = SubtitlePlan(sub_files=["/cache/de.vtt"])

        # Mock resolve_stream_info to fail on ep 25, succeed on ep 1
        def mock_resolve(search_arg, ep_no, **kwargs):
            if ep_no == 25:
                return None
            if ep_no == 1:
                return mock_stream
            return None

        mock_update = unittest.mock.MagicMock()
        mock_subproc = unittest.mock.MagicMock(return_value=unittest.mock.MagicMock(returncode=0))
        mock_prepare = unittest.mock.MagicMock(return_value=mock_plan)

        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 42, "name": "nils"}),
            unittest.mock.patch.object(
                cli_module,
                "get_watching_list",
                return_value=[
                    {
                        "id": 1,
                        "mediaId": 300,
                        "progress": 0,
                        "media": {
                            "id": 300,
                            "title": {"english": "Unlisted Show S3", "romaji": "Unlisted Show S3"},
                            "episodes": 12,
                        },
                    }
                ],
            ),
            unittest.mock.patch.object(cli_module, "compute_prequel_offset", return_value=24),
            unittest.mock.patch("ani_cli_sync.subtitles.resolve_stream_info", side_effect=mock_resolve) as mock_res_spy,
            unittest.mock.patch("ani_cli_sync.subtitles.prepare_subtitles", mock_prepare),
            unittest.mock.patch("ani_cli_sync.subtitles.prefetch_next_episode"),
            unittest.mock.patch.object(cli_module, "update_progress", mock_update),
            unittest.mock.patch.object(cli_module.subprocess, "run", mock_subproc),
            unittest.mock.patch("builtins.input", return_value="q"),
            unittest.mock.patch.object(cli_module.time, "time", side_effect=[0.0, 700.0]),
        ):
            cli_module.cmd_watch(query="Unlisted Show S3")

        # Must have probed 25 first, then fallen back to 1
        self.assertEqual(mock_res_spy.call_count, 2)
        self.assertEqual(mock_res_spy.call_args_list[0][0][1], 25)
        self.assertEqual(mock_res_spy.call_args_list[1][0][1], 1)

        # prepare_subtitles and mpv must have received episode 1
        mock_prepare.assert_called_once()
        self.assertEqual(mock_prepare.call_args[0][2], 1)

        # Cache must be updated to 0 for subsequent episodes
        self.assertEqual(cli_module._PREQUEL_OFFSET_CACHE.get(300), 0)

    def test_native_ani_cli_probe_fallback_on_fast_failure(self):
        """When native ani-cli fails on continuous ep (e.g. 25 in < 5s), retry season ep (1)."""
        import ani_cli_sync.cli as cli_module

        cli_module._PREQUEL_OFFSET_CACHE.clear()

        # First run fails fast (1s, code 1); second run succeeds (700s, code 0)
        ret1 = unittest.mock.MagicMock(returncode=1)
        ret2 = unittest.mock.MagicMock(returncode=0)
        mock_subproc = unittest.mock.MagicMock(side_effect=[ret1, ret2])
        mock_update = unittest.mock.MagicMock()

        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 42, "name": "nils"}),
            unittest.mock.patch.object(
                cli_module,
                "get_watching_list",
                return_value=[
                    {
                        "id": 1,
                        "mediaId": 300,
                        "progress": 0,
                        "media": {
                            "id": 300,
                            "title": {"english": "Unlisted Show S3", "romaji": "Unlisted Show S3"},
                            "episodes": 12,
                        },
                    }
                ],
            ),
            unittest.mock.patch.object(cli_module, "compute_prequel_offset", return_value=24),
            unittest.mock.patch.object(cli_module, "update_progress", mock_update),
            unittest.mock.patch.object(cli_module.subprocess, "run", mock_subproc),
            unittest.mock.patch("builtins.input", return_value="q"),
            # Timestamps: run1 start=0.0, end=1.0 (elapsed 1s); run2 start=1.0, end=701.0 (elapsed 700s)
            unittest.mock.patch.object(cli_module.time, "time", side_effect=[0.0, 1.0, 1.0, 701.0]),
        ):
            cli_module.cmd_watch(query="Unlisted Show S3", no_sub_fallback=True)

        self.assertEqual(mock_subproc.call_count, 2)
        cmd1 = mock_subproc.call_args_list[0][0][0]
        cmd2 = mock_subproc.call_args_list[1][0][0]
        self.assertIn("-e", cmd1)
        self.assertEqual(cmd1[cmd1.index("-e") + 1], "25")
        self.assertIn("-e", cmd2)
        self.assertEqual(cmd2[cmd2.index("-e") + 1], "1")

        self.assertEqual(cli_module._PREQUEL_OFFSET_CACHE.get(300), 0)


class TestCmdListAuth(unittest.TestCase):
    """Baseline for `list`: a stored token is required, an authenticated list shows
    progress with known or unknown totals, and an empty CURRENT list is not a failure."""

    @staticmethod
    def _entry(progress: int, english: str, romaji: str, episodes: int | None, media_id: int) -> dict:
        return {
            "id": media_id,
            "mediaId": media_id,
            "progress": progress,
            "media": {
                "id": media_id,
                "title": {"english": english, "romaji": romaji},
                "episodes": episodes,
            },
        }

    def test_missing_token_exits_1_with_login_instruction(self):
        import ani_cli_sync.cli as cli_module

        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value=None),
            unittest.mock.patch.object(cli_module, "get_viewer") as mock_viewer,
            contextlib.redirect_stderr(io.StringIO()) as err,
            self.assertRaises(SystemExit) as ctx,
        ):
            cli_module.cmd_list()

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("login", err.getvalue().lower())
        mock_viewer.assert_not_called()

    def test_authenticated_list_shows_progress_and_totals(self):
        import ani_cli_sync.cli as cli_module

        entries = [
            self._entry(4, "Frieren: Beyond Journey's End Season 2", "Sousou no Frieren 2nd Season", 10, 182255),
            self._entry(2, "Mystery Show", "Nazomeita Show", None, 99),
        ]
        out = io.StringIO()
        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 42, "name": "test-user"}),
            unittest.mock.patch.object(cli_module, "get_watching_list", return_value=entries),
            contextlib.redirect_stdout(out),
        ):
            cli_module.cmd_list()

        text = out.getvalue()
        self.assertIn("[04/10]", text)
        self.assertIn("[02/?]", text)  # unknown total renders as '?', not a crash
        self.assertIn("Frieren: Beyond Journey's End Season 2", text)
        self.assertIn("Mystery Show", text)

    def test_empty_current_list_is_reported_not_failed(self):
        import ani_cli_sync.cli as cli_module

        out = io.StringIO()
        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 42, "name": "test-user"}),
            unittest.mock.patch.object(cli_module, "get_watching_list", return_value=[]),
            contextlib.redirect_stdout(out),
        ):
            cli_module.cmd_list()  # must complete without raising or exiting non-zero

        self.assertIn("empty", out.getvalue().lower())


class TestCmdLoginTokenHandling(unittest.TestCase):
    """Baseline for `login`: the token is validated before it is saved."""

    def _login(self, inputs: list[str], viewer) -> unittest.mock.MagicMock:
        import ani_cli_sync.cli as cli_module

        with (
            unittest.mock.patch("builtins.input", side_effect=inputs),
            unittest.mock.patch.object(cli_module, "get_viewer", viewer),
            unittest.mock.patch.object(cli_module, "save_token") as mock_save,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            cli_module.cmd_login()
        return mock_save

    def test_validated_token_is_saved(self):
        viewer = unittest.mock.MagicMock(return_value={"id": 7, "name": "alice"})
        mock_save = self._login(["", "tok123"], viewer)
        mock_save.assert_called_once_with("tok123")

    def test_token_validation_failure_does_not_save(self):
        import ani_cli_sync.cli as cli_module

        with (
            unittest.mock.patch("builtins.input", side_effect=["", "badtok"]),
            unittest.mock.patch.object(cli_module, "get_viewer", side_effect=RuntimeError("400 Bad Request")),
            unittest.mock.patch.object(cli_module, "save_token") as mock_save,
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(RuntimeError),
        ):
            cli_module.cmd_login()

        mock_save.assert_not_called()

    def test_token_is_extracted_from_url_fragment(self):
        url = "https://anilist.co/api/v2/oauth/pin#access_token=frag123&token_type=Bearer"
        viewer = unittest.mock.MagicMock(return_value={"id": 7, "name": "alice"})
        mock_save = self._login(["", url], viewer)
        mock_save.assert_called_once_with("frag123")

    def test_saved_token_file_has_restricted_permissions(self):
        import ani_cli_sync.cli as cli_module

        with tempfile.TemporaryDirectory() as td:
            config_dir = Path(td) / "anilist"
            token_file = config_dir / "token"
            with (
                unittest.mock.patch.object(cli_module, "CONFIG_DIR", config_dir),
                unittest.mock.patch.object(cli_module, "TOKEN_FILE", token_file),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                cli_module.save_token("  sekret  ")

            self.assertEqual(token_file.read_text(encoding="utf-8"), "sekret")
            self.assertEqual(stat.S_IMODE(os.stat(token_file).st_mode), 0o600)


class TestCmdSetProgressBounds(unittest.TestCase):
    """Baseline for explicit `set` progress: deliberate correction reopens an entry,
    an unknown total never infers completion, a missing token writes nothing, and a
    watchlist miss falls through to global search.

    The above-total refusal and the at-total COMPLETED transition are already pinned
    by TestCmdSetGuard; these complete the supported-bounds picture.
    """

    @staticmethod
    def _media(media_id: int, episodes: int | None) -> dict:
        return {
            "id": media_id,
            "title": {"english": "Show Season 1", "romaji": "Show S1"},
            "episodes": episodes,
        }

    @staticmethod
    def _watch_entry(progress: int, media: dict) -> dict:
        return {"id": 1, "mediaId": media["id"], "progress": progress, "media": media}

    def test_deliberate_correction_to_lower_episode_submits_current(self):
        """Setting 3 on an entry at progress 11 must submit CURRENT 3, not refuse."""
        import ani_cli_sync.cli as cli_module

        media = self._media(100, 12)
        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 1, "name": "u"}),
            unittest.mock.patch.object(cli_module, "get_watching_list", return_value=[self._watch_entry(11, media)]),
            unittest.mock.patch.object(cli_module, "update_progress") as mock_update,
        ):
            cli_module.cmd_set("Show Season 1", 3)

        mock_update.assert_called_once_with("tok", 100, 3, status="CURRENT")

    def test_unknown_total_submits_current_without_completion(self):
        import ani_cli_sync.cli as cli_module

        media = self._media(100, None)
        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 1, "name": "u"}),
            unittest.mock.patch.object(cli_module, "get_watching_list", return_value=[]),
            unittest.mock.patch.object(cli_module, "search_anime", return_value=media),
            unittest.mock.patch.object(cli_module, "update_progress") as mock_update,
        ):
            cli_module.cmd_set("Show Season 1", 5)

        mock_update.assert_called_once_with("tok", 100, 5, status="CURRENT")

    def test_missing_token_exits_1_without_any_write(self):
        import ani_cli_sync.cli as cli_module

        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value=None),
            unittest.mock.patch.object(cli_module, "get_viewer") as mock_viewer,
            unittest.mock.patch.object(cli_module, "get_watching_list") as mock_list,
            unittest.mock.patch.object(cli_module, "search_anime") as mock_search,
            unittest.mock.patch.object(cli_module, "update_progress") as mock_update,
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as ctx,
        ):
            cli_module.cmd_set("Show Season 1", 3)

        self.assertEqual(ctx.exception.code, 1)
        mock_viewer.assert_not_called()
        mock_list.assert_not_called()
        mock_search.assert_not_called()
        mock_update.assert_not_called()

    def test_no_watchlist_match_falls_back_to_global_search(self):
        import ani_cli_sync.cli as cli_module

        unrelated = self._media(777, 24)
        global_media = self._media(555, 12)
        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 1, "name": "u"}),
            unittest.mock.patch.object(cli_module, "get_watching_list", return_value=[self._watch_entry(2, unrelated)]),
            unittest.mock.patch.object(cli_module, "search_anime", return_value=global_media) as mock_search,
            unittest.mock.patch.object(cli_module, "update_progress") as mock_update,
        ):
            cli_module.cmd_set("Frieren Season 2", 2)

        mock_search.assert_called_once_with("Frieren Season 2")
        mock_update.assert_called_once_with("tok", 555, 2, status="CURRENT")


class TestCliInvocationSurface(unittest.TestCase):
    """Baseline for the command surface: bare and option-only invocations watch,
    a command-like watch title stays a query, help exits 0 without playback, and
    usage errors exit 2 before any command dispatch."""

    @staticmethod
    def _clean_env() -> dict[str, str]:
        # Parser defaults read ANI_CLI_SYNC_* at main() time; strip them so the
        # assertions characterize the code, not this workstation's environment.
        return {k: v for k, v in os.environ.items() if not k.startswith("ANI_CLI_SYNC_")}

    def _invoke(self, argv: list[str]) -> dict:
        import ani_cli_sync.cli as cli_module

        captured: dict = {}

        def fake_watch(**kwargs):
            captured.update(kwargs)

        with (
            unittest.mock.patch.dict(os.environ, self._clean_env(), clear=True),
            unittest.mock.patch.object(sys, "argv", argv),
            unittest.mock.patch.object(cli_module, "cmd_watch", side_effect=fake_watch) as mock_watch,
        ):
            cli_module.main()

        self.assertTrue(mock_watch.called, f"expected cmd_watch dispatch for {argv}")
        return captured

    def test_bare_invocation_runs_watch_workflow(self):
        captured = self._invoke(["ani-cli-sync"])
        self.assertIsNone(captured.get("query"))
        # The full watch-subcommand call supplies every watch flag; the fallback
        # else-branch in main() would leave most of them absent.
        self.assertIs(captured.get("autoplay"), False)
        self.assertEqual(captured.get("sub_sync"), "off")

    def test_implicit_title_becomes_watch_query(self):
        captured = self._invoke(["ani-cli-sync", "Attack on Titan"])
        self.assertEqual(captured.get("query"), "Attack on Titan")

    def test_command_like_watch_query_is_not_executed(self):
        captured = self._invoke(["ani-cli-sync", "watch", "list"])
        self.assertEqual(captured.get("query"), "list")

    def test_help_request_exits_zero_without_playback(self):
        import ani_cli_sync.cli as cli_module

        out = io.StringIO()
        with (
            unittest.mock.patch.dict(os.environ, self._clean_env(), clear=True),
            unittest.mock.patch.object(sys, "argv", ["ani-cli-sync", "--help"]),
            unittest.mock.patch.object(cli_module, "cmd_watch") as mock_watch,
            contextlib.redirect_stdout(out),
            self.assertRaises(SystemExit) as ctx,
        ):
            cli_module.main()

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())
        mock_watch.assert_not_called()

    def test_set_non_integer_episode_is_usage_error_without_dispatch(self):
        import ani_cli_sync.cli as cli_module

        with (
            unittest.mock.patch.dict(os.environ, self._clean_env(), clear=True),
            unittest.mock.patch.object(sys, "argv", ["ani-cli-sync", "set", "Show", "twelve"]),
            unittest.mock.patch.object(cli_module, "cmd_set") as mock_set,
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as ctx,
        ):
            cli_module.main()

        self.assertEqual(ctx.exception.code, 2)
        mock_set.assert_not_called()

    def test_unknown_sub_sync_value_is_usage_error_without_watch(self):
        import ani_cli_sync.cli as cli_module

        with (
            unittest.mock.patch.dict(os.environ, self._clean_env(), clear=True),
            unittest.mock.patch.object(sys, "argv", ["ani-cli-sync", "watch", "--sub-sync=guess"]),
            unittest.mock.patch.object(cli_module, "cmd_watch") as mock_watch,
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as ctx,
        ):
            cli_module.main()

        self.assertEqual(ctx.exception.code, 2)
        mock_watch.assert_not_called()

    def test_subtitle_defaults_without_env_overrides(self):
        captured = self._invoke(["ani-cli-sync", "watch"])
        self.assertEqual(captured.get("sub_primary"), "de")
        self.assertIsNone(captured.get("sub_secondary"))
        self.assertEqual(captured.get("sub_delay"), 0.0)
        self.assertEqual(captured.get("sub_sync"), "off")

    def test_explicit_secondary_flag_is_forwarded(self):
        captured = self._invoke(["ani-cli-sync", "watch", "--sub-secondary=en", "Show"])
        self.assertEqual(captured.get("sub_secondary"), "en")
        self.assertEqual(captured.get("query"), "Show")

    def test_option_only_invocation_forwards_delay_to_watch(self):
        captured = self._invoke(["ani-cli-sync", "--sub-delay", "-1.5"])
        self.assertEqual(captured.get("sub_delay"), -1.5)
        self.assertIsNone(captured.get("query"))

    def test_console_aliases_share_the_main_entrypoint(self):
        content = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        for alias in ("ani-cli-sync", "ani-sync"):
            self.assertRegex(
                content,
                rf'(?m)^{re.escape(alias)} = "ani_cli_sync\.cli:main"$',
                f"console-script alias '{alias}' must dispatch to ani_cli_sync.cli:main",
            )


class TestWatchNativeDelegation(unittest.TestCase):
    """Baseline: watching without a stored token, or with an empty CURRENT list and
    no query, delegates to native ani-cli and performs no AniList synchronization."""

    def test_no_token_delegates_to_native_without_sync(self):
        import ani_cli_sync.cli as cli_module

        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value=None),
            unittest.mock.patch.object(cli_module, "get_viewer") as mock_viewer,
            unittest.mock.patch.object(cli_module, "get_watching_list") as mock_list,
            unittest.mock.patch.object(cli_module, "update_progress") as mock_update,
            unittest.mock.patch.object(cli_module.subprocess, "run") as mock_run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            cli_module.cmd_watch()

        mock_run.assert_called_once_with(["ani-cli", "--skip"], check=False)
        mock_viewer.assert_not_called()
        mock_list.assert_not_called()
        mock_update.assert_not_called()

    def test_empty_watchlist_without_query_delegates_native_without_sync(self):
        import ani_cli_sync.cli as cli_module

        with (
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 42, "name": "test-user"}),
            unittest.mock.patch.object(cli_module, "get_watching_list", return_value=[]),
            unittest.mock.patch.object(cli_module, "search_anime") as mock_search,
            unittest.mock.patch.object(cli_module, "update_progress") as mock_update,
            unittest.mock.patch.object(cli_module.subprocess, "run") as mock_run,
            unittest.mock.patch("builtins.input", return_value=""),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            cli_module.cmd_watch()

        mock_run.assert_called_once_with(["ani-cli", "--skip"], check=False)
        mock_search.assert_not_called()
        mock_update.assert_not_called()


class TestWatchSelectionCancellation(unittest.TestCase):
    """Baseline: with fzf unavailable, selection is numbered; invalid or empty input
    cancels rather than selecting an arbitrary episode."""

    ENTRY_ALPHA: ClassVar[dict] = {
        "id": 1,
        "mediaId": 101,
        "progress": 3,
        "media": {"id": 101, "title": {"english": "Alpha Show", "romaji": "Alpha"}, "episodes": 12},
    }
    ENTRY_BETA: ClassVar[dict] = {
        "id": 2,
        "mediaId": 102,
        "progress": 0,
        "media": {"id": 102, "title": {"english": "Beta Show", "romaji": "Beta"}, "episodes": 12},
    }

    def _watch(self, inputs: list[str]) -> tuple[unittest.mock.MagicMock, unittest.mock.MagicMock, str]:
        import ani_cli_sync.cli as cli_module

        cli_module._PREQUEL_OFFSET_CACHE.clear()
        out = io.StringIO()
        input_iter = iter(inputs)
        mock_update = unittest.mock.MagicMock()
        mock_run = unittest.mock.MagicMock(return_value=unittest.mock.MagicMock(returncode=0))

        def mock_gql(query, variables=None, token=None, retries=3):
            return {"data": {"Media": {"relations": {"edges": []}}}}

        with (
            tempfile.TemporaryDirectory() as cache_home,
            unittest.mock.patch.dict(os.environ, {"XDG_CACHE_HOME": cache_home}),
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 42, "name": "test-user"}),
            unittest.mock.patch.object(
                cli_module,
                "get_watching_list",
                return_value=[self.ENTRY_ALPHA, self.ENTRY_BETA],
            ),
            unittest.mock.patch.object(cli_module, "gql_query", side_effect=mock_gql),
            unittest.mock.patch.object(cli_module, "update_progress", mock_update),
            unittest.mock.patch.object(cli_module.subprocess, "run", mock_run),
            unittest.mock.patch.object(cli_module.subprocess, "Popen", side_effect=FileNotFoundError("fzf")),
            unittest.mock.patch("builtins.input", side_effect=lambda *_: next(input_iter)),
            unittest.mock.patch.object(cli_module.time, "time", side_effect=[0.0, 700.0]),
            contextlib.redirect_stdout(out),
        ):
            cli_module.cmd_watch(no_sub_fallback=True)

        return mock_run, mock_update, out.getvalue()

    def test_valid_numbered_choice_selects_that_entry(self):
        mock_run, mock_update, _ = self._watch(["2", "q"])
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], "ani-cli")
        self.assertEqual(cmd[-3:], ["-e", "1", "Beta"])
        mock_update.assert_not_called()  # 700s of unknown duration is below the advance floor

    def test_invalid_or_empty_numbered_input_cancels_without_launch(self):
        for choice in ("", "abc", "0", "9"):
            with self.subTest(choice=choice):
                mock_run, mock_update, _ = self._watch([choice])
                mock_run.assert_not_called()
                mock_update.assert_not_called()

    def test_cancelled_fzf_return_code_stops_without_launch(self):
        import ani_cli_sync.cli as cli_module

        mock_update = unittest.mock.MagicMock()
        mock_run = unittest.mock.MagicMock(return_value=unittest.mock.MagicMock(returncode=0))
        fzf_proc = unittest.mock.MagicMock()
        fzf_proc.communicate.return_value = ("", None)
        fzf_proc.returncode = 130  # ESC in fzf

        with (
            tempfile.TemporaryDirectory() as cache_home,
            unittest.mock.patch.dict(os.environ, {"XDG_CACHE_HOME": cache_home}),
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 42, "name": "test-user"}),
            unittest.mock.patch.object(
                cli_module,
                "get_watching_list",
                return_value=[self.ENTRY_ALPHA, self.ENTRY_BETA],
            ),
            unittest.mock.patch.object(cli_module, "update_progress", mock_update),
            unittest.mock.patch.object(cli_module.subprocess, "run", mock_run),
            unittest.mock.patch.object(cli_module.subprocess, "Popen", return_value=fzf_proc),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            cli_module.cmd_watch(no_sub_fallback=True)

        mock_run.assert_not_called()
        mock_update.assert_not_called()


class TestWatchQueryNarrowing(unittest.TestCase):
    """Baseline for watch-query selection: an exact title wins among several
    matches, and several non-exact matches are offered as a narrowed selection
    rather than playing one without selection."""

    @staticmethod
    def _entry(english: str, romaji: str, media_id: int) -> dict:
        return {
            "id": media_id,
            "mediaId": media_id,
            "progress": 0,
            "media": {"id": media_id, "title": {"english": english, "romaji": romaji}, "episodes": 12},
        }

    def _watch(self, entries: list[dict], query: str, inputs: list[str]):
        import ani_cli_sync.cli as cli_module

        cli_module._PREQUEL_OFFSET_CACHE.clear()
        out = io.StringIO()
        input_iter = iter(inputs)
        mock_update = unittest.mock.MagicMock()
        mock_run = unittest.mock.MagicMock(return_value=unittest.mock.MagicMock(returncode=0))

        def mock_gql(query, variables=None, token=None, retries=3):
            return {"data": {"Media": {"relations": {"edges": []}}}}

        with (
            tempfile.TemporaryDirectory() as cache_home,
            unittest.mock.patch.dict(os.environ, {"XDG_CACHE_HOME": cache_home}),
            unittest.mock.patch.object(cli_module, "get_token", return_value="tok"),
            unittest.mock.patch.object(cli_module, "get_viewer", return_value={"id": 42, "name": "test-user"}),
            unittest.mock.patch.object(cli_module, "get_watching_list", return_value=entries),
            unittest.mock.patch.object(cli_module, "gql_query", side_effect=mock_gql),
            unittest.mock.patch.object(cli_module, "update_progress", mock_update),
            unittest.mock.patch.object(cli_module.subprocess, "run", mock_run),
            unittest.mock.patch.object(cli_module.subprocess, "Popen", side_effect=FileNotFoundError("fzf")),
            unittest.mock.patch("builtins.input", side_effect=lambda *_: next(input_iter)),
            unittest.mock.patch.object(cli_module.time, "time", side_effect=[0.0, 700.0]),
            contextlib.redirect_stdout(out),
        ):
            cli_module.cmd_watch(query=query, no_sub_fallback=True)

        return mock_run, mock_update, out.getvalue()

    def test_exact_title_wins_among_several_matches(self):
        # The non-exact substring match is listed FIRST: without the exact-title
        # check, "Show Season 2" would be the selection.
        entries = [self._entry("Show Season 2", "Show S2", 202), self._entry("Show", "Show", 201)]
        mock_run, mock_update, _ = self._watch(entries, "Show", ["q"])

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[-3:], ["-e", "1", "Show"])
        mock_update.assert_not_called()

    def test_several_non_exact_matches_offer_narrowed_selection(self):
        entries = [
            self._entry("Alpha Season 1", "Alpha S1", 201),
            self._entry("Alpha Season 2", "Alpha S2", 202),
            self._entry("Other Anime", "Other", 203),
        ]
        mock_run, _, out = self._watch(entries, "Season", ["2", "q"])

        self.assertNotIn("Other Anime", out, "the offered menu must contain only the narrowed matches")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[-3:], ["-e", "1", "Alpha S2"])


class TestPrefetchHermeticity(unittest.TestCase):
    """Hermeticity guard for the watch loop's lookahead prefetch thread.

    Exactly two fixtures in this suite drive cmd_watch into the
    subtitle-fallback branch far enough to start the lookahead daemon thread
    (target prefetch_next_episode, which the watch loop imports
    function-locally from ani_cli_sync.subtitles, so that module attribute is
    the only patch boundary that intercepts it). Both must stub the target
    there: without the stub, real stream resolution, translation, or ani-cli
    processes can run after their mock contexts expire and race into later
    tests' subprocess.run mocks.

    - test_subtitle_fallback_fixture_starts_no_real_prefetch_thread re-runs the
      fully mocked fixture under a recording threading.Thread wrapper (a thread
      whose target is the real function is captured, never started, and fails
      the guard), so an escape is observed without being performed.
    - test_global_search_fallback_fixture_stubs_prefetch_at_source pins the
      stub inside the fallback fixture statically, because that fixture
      exercises a real foreground resolve by design and must not be executed
      from here.
    """

    def test_subtitle_fallback_fixture_starts_no_real_prefetch_thread(self):
        import threading

        import ani_cli_sync.subtitles as subtitles_module

        real_prefetch = subtitles_module.prefetch_next_episode
        real_thread = threading.Thread
        captured_targets: list = []

        def thread_factory(*args, target=None, **kwargs):
            captured_targets.append(target)
            if target is real_prefetch:
                target = lambda *a, **k: None  # observe, never perform
            return real_thread(*args, target=target, **kwargs)

        result = unittest.TestResult()
        with unittest.mock.patch("threading.Thread", thread_factory):
            TestSequelHelpers("test_cmd_watch_subtitles_fallback_mpv").run(result)

        self.assertTrue(
            result.wasSuccessful(),
            msg=f"re-run fixture must still pass: {result.failures}{result.errors}",
        )
        # The fixture must still exercise the lookahead path (exactly one
        # thread) AND its target must be the stub, never the real function.
        self.assertEqual(len(captured_targets), 1, msg="fixture no longer exercises the lookahead thread")
        self.assertIsNot(
            captured_targets[0],
            real_prefetch,
            msg="fixture started a real prefetch_next_episode thread; stub it at the "
            'ani_cli_sync.subtitles boundary, not elsewhere (the watch loop imports '
            "it function-locally from that module)",
        )

    def test_global_search_fallback_fixture_stubs_prefetch_at_source(self):
        import inspect

        source = inspect.getsource(
            TestWatchQueryFallback.test_autoplay_query_not_in_watching_falls_back_to_global_search
        )
        self.assertIn(
            'unittest.mock.patch("ani_cli_sync.subtitles.prefetch_next_episode"',
            source,
            msg="the global-search fallback fixture must stub prefetch at the "
            "ani_cli_sync.subtitles boundary; without it its lookahead daemon "
            "thread runs real resolve/prepare work after the mock context expires",
        )


class TestSequelFormatEligibility(unittest.TestCase):
    """Rollover considers TV and ONA sequels; other formats (e.g. a MOVIE) are not eligible."""

    @staticmethod
    def _relations_resp(fmt: str) -> dict:
        return {
            "data": {
                "Media": {
                    "relations": {
                        "edges": [
                            {
                                "relationType": "SEQUEL",
                                "node": {
                                    "id": 200,
                                    "title": {"english": "Side Film", "romaji": "Side Film"},
                                    "episodes": 2,
                                    "format": fmt,
                                    "status": "FINISHED",
                                },
                            }
                        ]
                    }
                }
            }
        }

    def test_movie_sequel_is_not_eligible(self):
        with unittest.mock.patch("ani_cli_sync.cli.gql_query", return_value=self._relations_resp("MOVIE")):
            node, reason = find_sequel(100)
        self.assertIsNone(node)
        self.assertIsNone(reason)

    def test_ona_sequel_is_eligible(self):
        with unittest.mock.patch("ani_cli_sync.cli.gql_query", return_value=self._relations_resp("ONA")):
            node, reason = find_sequel(100)
        self.assertIsNotNone(node)
        self.assertEqual(node["id"], 200)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()


