from __future__ import annotations

import unittest
import unittest.mock
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
    # ── Slime S3 ──────────────────────────────────────────────────────────────
    def test_slime_s3_season3_ep1_maps_to_49(self):
        search, ep = resolve_episode_offset(
            "[01/24] That Time I Got Reincarnated as a Slime Season 3 | Tensei Shitara Slime Datta Ken 3rd Season",
            "Tensei Shitara Slime Datta Ken 3rd Season",
            1,
        )
        self.assertEqual(ep, 49)
        self.assertEqual(search, "That Time I Got Reincarnated as a Slime Season 3")

    def test_slime_s3_season3_ep24_maps_to_72(self):
        search, ep = resolve_episode_offset(
            "[24/24] That Time I Got Reincarnated as a Slime Season 3 | Tensei Shitara Slime Datta Ken 3rd Season",
            "Tensei Shitara Slime Datta Ken 3rd Season",
            24,
        )
        self.assertEqual(ep, 72)
        self.assertEqual(search, "That Time I Got Reincarnated as a Slime Season 3")

    def test_slime_s3_season3_ep_beyond_max_falls_through_to_identity(self):
        search, ep = resolve_episode_offset(
            "[25/24] That Time I Got Reincarnated as a Slime Season 3 | Tensei Shitara Slime Datta Ken 3rd Season",
            "Tensei Shitara Slime Datta Ken 3rd Season",
            25,
        )
        self.assertEqual(ep, 25)
        self.assertEqual(search, "Tensei Shitara Slime Datta Ken 3rd Season")

    def test_slime_s3_3rd_season_ep1_maps_to_49(self):
        search, ep = resolve_episode_offset(
            "[01/24] Tensei Shitara Slime Datta Ken 3rd Season",
            "Tensei Shitara Slime Datta Ken 3rd Season",
            1,
        )
        self.assertEqual(ep, 49)
        self.assertEqual(search, "That Time I Got Reincarnated as a Slime Season 3")

    def test_slime_s3_3rd_season_ep24_maps_to_72(self):
        search, ep = resolve_episode_offset(
            "[24/24] Tensei Shitara Slime Datta Ken 3rd Season",
            "Tensei Shitara Slime Datta Ken 3rd Season",
            24,
        )
        self.assertEqual(ep, 72)
        self.assertEqual(search, "That Time I Got Reincarnated as a Slime Season 3")

    def test_slime_s3_3rd_season_ep_beyond_max_falls_through_to_identity(self):
        search, ep = resolve_episode_offset(
            "[25/24] Tensei Shitara Slime Datta Ken 3rd Season",
            "Tensei Shitara Slime Datta Ken 3rd Season",
            25,
        )
        self.assertEqual(ep, 25)
        self.assertEqual(search, "Tensei Shitara Slime Datta Ken 3rd Season")

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
        # Slime Season 3 is in table (+48 with search override)
        search, ep = resolve_episode_offset(
            "[01/24] That Time I Got Reincarnated as a Slime Season 3",
            "Tensei Shitara Slime Datta Ken 3rd Season",
            1,
            computed_offset=999,
        )
        self.assertEqual(ep, 49)  # 1 + 48 (table), not 1 + 999
        self.assertEqual(search, "That Time I Got Reincarnated as a Slime Season 3")

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
                cli_module.time, "time", side_effect=[0.0, 700.0, 700.0, 1400.0, 1400.0, 2100.0]
            ),
            unittest.mock.patch.object(cli_module.time, "sleep"),
        ):
            cli_module.cmd_watch(query="Show", autoplay=autoplay)

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
                cli_module.time, "time", side_effect=[0.0, 700.0, 700.0, 1400.0, 1400.0, 2100.0]
            ),
            unittest.mock.patch.object(cli_module.time, "sleep"),
        ):
            cli_module.cmd_watch(query="Show", autoplay=True)

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


if __name__ == "__main__":
    unittest.main()
