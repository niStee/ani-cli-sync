from __future__ import annotations

import re
import tempfile
import unittest
from contextlib import ExitStack
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from ani_cli_sync import cli
from ani_cli_sync.subtitles import SubtitlePlan

# Passed by name, never as a literal at the call site: a literal in a `token=`
# keyword argument trips Bandit B106 ("possible hardcoded password"), which the
# repository's Codacy gate counts as a new issue and blocks the merge on.
_AUTH = "test-token"


def media(media_id=100, title="Show", episodes=1, duration=...):
    result = {
        "id": media_id,
        "title": {"english": title, "romaji": f"{title} Romaji"},
        "episodes": episodes,
    }
    if duration is not ...:
        result["duration"] = duration
    return result


def entry(media_id=100, title="Show", episodes=1, progress=0, duration=...):
    return {
        "id": media_id,
        "mediaId": media_id,
        "progress": progress,
        "media": media(media_id, title, episodes, duration),
    }


def relation(node=None):
    edges = [] if node is None else [{"relationType": "SEQUEL", "node": node}]
    return {"data": {"Media": {"relations": {"edges": edges}}}}


class WatchHarness:
    """Drive the real watch loop with every external boundary mocked."""

    def __init__(self, test, entries, elapsed, *, search_result=None, returncodes=None):
        self.test = test
        self.entries = entries
        self.elapsed = iter(elapsed)
        self.returncodes = iter(returncodes or [0] * len(elapsed))
        self.search_result = search_result
        self.now = 0.0
        self.played = []
        self.updates_at_player_boundary = []
        self.gql_calls = []
        self.gql_responses = []
        self.update = MagicMock()
        self.player = MagicMock(side_effect=self._play)
        self.probe = MagicMock(return_value=None)
        self.fzf = MagicMock()
        self.stdout = StringIO()
        self.stack = ExitStack()
        self.stream = SimpleNamespace(
            video_link="https://hls.invalid/media.m3u8",
            referrer="https://stream.invalid/",
            intro_skip=None,
            outro_skip=None,
        )

    def _play(self, args, *_args, **_kwargs):
        self.played.append(list(args))
        self.updates_at_player_boundary.append(self.update.call_count)
        try:
            seconds = next(self.elapsed)
            returncode = next(self.returncodes)
        except StopIteration as exc:
            raise AssertionError("watch loop played an unexpected extra episode") from exc
        self.now += seconds
        return SimpleNamespace(returncode=returncode)

    def queue_gql(self, response=None, *, error=None):
        self.gql_responses.append((response, error))

    def _gql(self, query, variables=None, token=None, retries=3):
        self.gql_calls.append((query, variables))
        self.test.assertTrue(self.gql_responses, "unexpected GraphQL request")
        response, error = self.gql_responses.pop(0)
        if error is not None:
            raise error
        return response

    def run(self, *, autoplay=True, no_sub_fallback=True, dub=False, interactive=None, query="Show"):
        temp_home = self.stack.enter_context(tempfile.TemporaryDirectory())
        patches = [
            patch.dict("os.environ", {"XDG_CACHE_HOME": temp_home, "HOME": temp_home}),
            patch.object(cli, "get_token", return_value="test-token"),
            patch.object(cli, "get_viewer", return_value={"id": 42}),
            patch.object(cli, "get_watching_list", return_value=self.entries),
            patch.object(cli, "search_anime", return_value=self.search_result),
            patch.object(cli, "gql_query", side_effect=self._gql),
            patch.object(cli, "update_progress", self.update),
            patch.object(cli, "_probe_duration", self.probe),
            patch.object(cli.subprocess, "run", self.player),
            patch.object(cli.subprocess, "Popen", self.fzf),
            patch.object(cli.time, "time", side_effect=lambda: self.now),
            patch.object(cli.time, "sleep"),
            patch.object(cli, "compute_prequel_offset", return_value=0),
            patch.object(cli, "prepare_menu_env", return_value={}),
            patch("sys.stdout", self.stdout),
            patch("builtins.input", return_value=interactive if interactive is not None else "q"),
        ]
        if not no_sub_fallback and not dub:
            patches.extend(
                [
                    patch("ani_cli_sync.subtitles.resolve_stream_info", return_value=self.stream),
                    patch("ani_cli_sync.subtitles.prepare_subtitles", return_value=SubtitlePlan(sub_files=[])),
                    patch("ani_cli_sync.subtitles.build_mpv_command", return_value=["mpv"]),
                    patch("ani_cli_sync.subtitles.prefetch_next_episode"),
                ]
            )
        for patcher in patches:
            self.stack.enter_context(patcher)
        cli._PREQUEL_OFFSET_CACHE.clear()
        try:
            cli.cmd_watch(query=query, autoplay=autoplay, no_sub_fallback=no_sub_fallback, dub=dub)
        finally:
            # Subtests must not inherit environment, patches, clocks, or tempdirs.
            self.stack.close()
            cli._PREQUEL_OFFSET_CACHE.clear()


def drive(test, elapsed, *, advance=False, entries=None, entry_duration=None, **kwargs):
    """Complete a one-episode show on advance, or stop with progress preserved."""
    if entries is None:
        entries = [entry(duration=entry_duration)]
    harness = WatchHarness(test, entries, elapsed, **kwargs)
    if advance:
        harness.queue_gql(relation())
    harness.run()
    return harness


class TestDurationDecisionContract(unittest.TestCase):
    """Observable command outcomes for the three duration-evidence tiers."""

    def test_hls_precedence_with_skips_advances_and_conflicts_stop(self):
        for hls, minutes, advance in ((1463.0, 30, True), (1800.0, 20, False)):
            with self.subTest(hls=hls, minutes=minutes):
                # Both pairs use elapsed=1000 and 176s of skips. Metadata-first
                # reverses the outcomes; HLS-first gives these exact results.
                harness = WatchHarness(self, [entry(duration=minutes)], [1000.0])
                harness.probe.return_value = hls
                harness.stream.intro_skip = (0.0, 88.0)
                harness.stream.outro_skip = (1000.0, 1088.0)
                if advance:
                    harness.queue_gql(relation())
                harness.run(no_sub_fallback=False)
                self.assertEqual(harness.update.called, advance)

    def test_hls_precedence_without_skips_advances_and_conflicts_stop(self):
        for hls, minutes, advance in ((1463.0, 30, True), (1800.0, 20, False)):
            with self.subTest(hls=hls, minutes=minutes):
                # No skips: metadata-first reverses these outcomes at elapsed=1200.
                harness = WatchHarness(self, [entry(duration=minutes)], [1200.0])
                harness.probe.return_value = hls
                if advance:
                    harness.queue_gql(relation())
                harness.run(no_sub_fallback=False)
                self.assertEqual(harness.update.called, advance)

    def test_unknown_hls_uses_anilist_exact_ratio_boundaries(self):
        for hls in (None, 0.0):
            for minutes, elapsed, advance in (
                (24, 1150.0, False),
                (24, 1152.0, True),
                (60, 2879.9, False),
                (60, 2880.0, True),
            ):
                with self.subTest(hls=hls, minutes=minutes, elapsed=elapsed):
                    harness = WatchHarness(self, [entry(duration=minutes)], [elapsed])
                    harness.probe.return_value = hls
                    if advance:
                        harness.queue_gql(relation())
                    harness.run()
                    self.assertEqual(harness.update.called, advance)

    def test_anilist_skip_aware_boundary_and_short_duration(self):
        for elapsed, advance in ((881.9, False), (882.0, True)):
            with self.subTest(elapsed=elapsed):
                harness = WatchHarness(self, [entry(duration=24)], [elapsed])
                harness.stream.intro_skip = (0.0, 90.0)
                harness.stream.outro_skip = (1000.0, 1090.0)
                if advance:
                    harness.queue_gql(relation())
                harness.run(no_sub_fallback=False)
                self.assertEqual(harness.update.called, advance)

        # Minutes must be converted once: one minute gives an exact 48s boundary.
        for elapsed, advance in ((47.9, False), (48.0, True)):
            with self.subTest(short_elapsed=elapsed):
                harness = drive(self, [elapsed], advance=advance, entry_duration=1)
                self.assertEqual(harness.update.called, advance)

    def test_invalid_metadata_preserves_constant_fallback(self):
        invalid = [..., None, True, False, 24.0, "24", 0, -24, float("nan"), float("inf"), float("-inf")]
        for duration in invalid:
            for elapsed, advance in ((1149.0, False), (1150.0, True)):
                with self.subTest(duration=duration, elapsed=elapsed):
                    harness = drive(self, [elapsed], advance=advance, entry_duration=duration)
                    self.assertEqual(harness.update.called, advance)

    def test_missing_metadata_with_skips_preserves_adjusted_constant(self):
        for elapsed, advance in ((973.0, False), (974.0, True)):
            with self.subTest(elapsed=elapsed):
                harness = WatchHarness(self, [entry(duration=None)], [elapsed])
                harness.stream.intro_skip = (0.0, 88.0)
                harness.stream.outro_skip = (1000.0, 1088.0)
                if advance:
                    harness.queue_gql(relation())
                harness.run(no_sub_fallback=False)
                self.assertEqual(harness.update.called, advance)

    def test_nonzero_exit_stops_without_probe_or_progress_mutation(self):
        harness = WatchHarness(self, [entry(duration=24)], [2000.0], returncodes=[1])
        harness.run()
        harness.probe.assert_not_called()
        harness.update.assert_not_called()
        self.assertEqual(harness.gql_calls, [])
        self.assertIn("player exited with code 1", harness.stdout.getvalue())


class TestSelectionAndSequelDuration(unittest.TestCase):
    def test_watchlist_duration_is_used_by_dub_and_no_sub_fallback(self):
        for no_sub_fallback, dub in ((True, False), (False, True)):
            with self.subTest(no_sub_fallback=no_sub_fallback, dub=dub):
                harness = WatchHarness(self, [entry(duration=24)], [1150.0])
                harness.run(no_sub_fallback=no_sub_fallback, dub=dub)
                self.assertFalse(harness.update.called)
                self.assertIn("--dub" if dub else "--skip", harness.player.call_args.args[0])

    def test_global_search_retains_duration_without_an_episode_lookup(self):
        harness = WatchHarness(self, [], [1150.0], search_result=media(200, "Show", 1, 24))
        # Let an incorrect completion terminate normally so the post-play delta is observed.
        harness.queue_gql(relation())
        harness.run()
        self.assertEqual(len(harness.updates_at_player_boundary), 1)
        enrollment_count = harness.updates_at_player_boundary[0]
        post_play_updates = harness.update.call_args_list[enrollment_count:]
        self.assertEqual(post_play_updates, [], "insufficient playback caused a post-play write")
        self.assertEqual(len(harness.gql_calls), 0)  # no completion or per-episode lookup

    def test_interactive_selection_uses_chosen_entry_not_list_neighbor(self):
        entries = [entry(200, "Other", duration=30), entry(100, "Show", duration=24)]
        harness = WatchHarness(self, entries, [1152.0])
        selected = "[00/1] Show | Show Romaji ###100###0###1\n"
        harness.fzf.return_value.communicate.return_value = (selected, "")
        harness.fzf.return_value.returncode = 0
        harness.queue_gql(relation())
        harness.run(autoplay=False, query="not a watchlist title")
        self.assertTrue(harness.update.called)
        harness.update.assert_called_once_with("test-token", 100, 1, status="COMPLETED")
        self.assertEqual(len(harness.gql_calls), 1)  # existing completion/sequel query only

    def test_manual_selection_without_fzf_uses_selected_media(self):
        entries = [entry(200, "Other", duration=30), entry(100, "Show", duration=24)]
        harness = WatchHarness(self, entries, [1152.0])
        harness.fzf.side_effect = FileNotFoundError
        harness.queue_gql(relation())
        harness.run(autoplay=False, interactive="2", query="not a watchlist title")
        self.assertTrue(harness.update.called)
        harness.update.assert_called_once_with("test-token", 100, 1, status="COMPLETED")
        self.assertEqual(len(harness.gql_calls), 1)  # existing completion/sequel query only

    def _sequel_run(self, sequel_duration, *, expect_sequel_advance):
        prior = entry(100, "Show", duration=24)
        sequel = media(200, "Show Sequel", episodes=2, duration=sequel_duration)
        sequel.update(format="TV", status="FINISHED")
        elapsed = [1450.0, 1150.0, 0.0]
        codes = [0, 0, 1]
        harness = WatchHarness(self, [prior], elapsed, returncodes=codes)
        harness.queue_gql(relation(sequel))
        harness.queue_gql({"data": {"MediaList": None}})
        harness.run()
        expected_player_count = 3 if expect_sequel_advance else 2
        self.assertEqual(len(harness.played), expected_player_count, "sequel episode was not played")
        self.assertEqual(harness.played[0][-2:], ["1", "Show Romaji"])
        self.assertEqual(harness.played[1][-2:], ["1", "Show Sequel Romaji"])
        # Sequel episode 1/2 is CURRENT: no completion query or second list read.
        # Episode 2 exits non-zero, so it also stops before any completion query.
        self.assertEqual(len(harness.gql_calls), 2)
        self.assertEqual(harness.gql_responses, [], "an unexpected GraphQL response was left unused")
        return harness

    def test_sequel_duration_replaces_prior_media(self):
        harness = self._sequel_run(30, expect_sequel_advance=False)
        self.assertNotIn(call("test-token", 200, 1, status="CURRENT"), harness.update.call_args_list)

    def test_missing_sequel_duration_falls_back_not_inherits(self):
        harness = self._sequel_run(None, expect_sequel_advance=True)
        self.assertIn(call("test-token", 200, 1, status="CURRENT"), harness.update.call_args_list)
        self.assertEqual(harness.played[2][-2:], ["2", "Show Sequel Romaji"])

    def test_invalid_sequel_duration_falls_back_not_inherits(self):
        harness = self._sequel_run(False, expect_sequel_advance=True)
        self.assertIn(call("test-token", 200, 1, status="CURRENT"), harness.update.call_args_list)
        self.assertEqual(harness.played[2][-2:], ["2", "Show Sequel Romaji"])


class TestExistingGraphQLBoundaries(unittest.TestCase):
    def test_three_existing_queries_request_duration(self):
        responses = [
            {"data": {"MediaListCollection": {"lists": [{"entries": [entry()]}]}}},
            {"data": {"Media": media(duration=24)}},
            relation(media(200, "Show Sequel", 2, 30) | {"format": "TV", "status": "FINISHED"}),
        ]
        calls = []

        def fake_gql(query, variables=None, token=None, retries=3):
            calls.append((query, variables))
            return responses[len(calls) - 1]

        with patch.object(cli, "gql_query", side_effect=fake_gql):
            cli.get_watching_list("test-token", 42)
            cli.search_anime("Show")
            cli.find_sequel(100, token=_AUTH)

        self.assertEqual(len(calls), 3)
        starts = (r"media\s*\{", r"Media\s*\([^)]*search[^)]*\)\s*\{", r"node\s*\{")
        for (query, _), start in zip(calls, starts, strict=True):
            match = re.search(start + r"([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", query)
            self.assertIsNotNone(match, query)
            self.assertRegex(match.group(1), r"\bduration\b")


if __name__ == "__main__":
    unittest.main()
