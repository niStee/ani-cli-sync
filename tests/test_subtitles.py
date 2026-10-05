from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar
from unittest.mock import MagicMock, patch

from ani_cli_sync.subtitles import (
    DEFAULT_MODEL,
    StreamInfo,
    SubtitlePlan,
    VTTCue,
    _translate_single_batch,
    build_mpv_command,
    count_vtt_cues,
    fetch_vtt_text,
    format_vtt,
    get_cached_subtitle_path,
    is_forced_track,
    parse_vtt,
    prepare_subtitles,
    resolve_stream_info,
    translate_cues_llm,
)

SAMPLE_VTT = """WEBVTT

00:00.460 --> 00:01.880
<b>— 300 YEARS AGO —</b>

00:01.960 --> 00:03.710
<b>The only thing I remember is...</b>

00:03.960 --> 00:06.380
<b>I went on a rampage.</b>
"""

SAMPLE_FORCED_VTT = """WEBVTT

00:00.460 --> 00:01.880
<b>— 300 JAHRE ZUVOR —</b>

00:23.000 --> 00:25.000
<b>TITEL</b>
"""


class TestVTTProcessing(unittest.TestCase):
    def test_parse_vtt(self):
        cues = parse_vtt(SAMPLE_VTT)
        self.assertEqual(len(cues), 3)
        self.assertEqual(cues[0].timing, "00:00.460 --> 00:01.880")
        self.assertEqual(cues[0].lines, ["<b>— 300 YEARS AGO —</b>"])
        self.assertEqual(cues[1].lines, ["<b>The only thing I remember is...</b>"])

    def test_format_vtt(self):
        cues = parse_vtt(SAMPLE_VTT)
        formatted = format_vtt(cues)
        self.assertTrue(formatted.startswith("WEBVTT\n\n"))
        self.assertIn("00:00.460 --> 00:01.880\n<b>— 300 YEARS AGO —</b>", formatted)
        self.assertIn("00:03.960 --> 00:06.380\n<b>I went on a rampage.</b>", formatted)

    def test_count_vtt_cues(self):
        self.assertEqual(count_vtt_cues(SAMPLE_VTT), 3)
        self.assertEqual(count_vtt_cues(""), 0)

    def test_is_forced_track(self):
        # Sample forced has 2 cues (< 50)
        self.assertTrue(is_forced_track(SAMPLE_FORCED_VTT))
        # Synthesize a full track of 55 cues
        cues_55 = [VTTCue(identifier=str(i), timing=f"00:{i:02d}.000 --> 00:{i:02d}.900", lines=[f"Line {i}"]) for i in range(55)]
        full_vtt = format_vtt(cues_55)
        self.assertFalse(is_forced_track(full_vtt))


class TestCachePaths(unittest.TestCase):
    def test_get_cached_subtitle_path(self):
        path = get_cached_subtitle_path(
            "That Time I Got Reincarnated as a Slime Season 4",
            15,
            "de",
            base_dir=Path("/var/cache/test-subtitles"),
        )
        self.assertEqual(
            path,
            Path("/var/cache/test-subtitles/that_time_i_got_reincarnated_as_a_slime_season_4_ep15_de.vtt"),
        )

    def test_get_cached_subtitle_path_zh_pinyin(self):
        path = get_cached_subtitle_path(
            "Sousou no Frieren",
            2,
            "zh-pinyin",
            base_dir=Path("/var/cache/test-subtitles"),
        )
        self.assertEqual(
            path,
            Path("/var/cache/test-subtitles/sousou_no_frieren_ep2_zh-pinyin.vtt"),
        )


class TestStreamInfoResolution(unittest.TestCase):
    @patch("ani_cli_sync.subtitles.subprocess.run")
    def test_resolve_stream_info_success(self, mock_run):
        mock_output = (
            "Checking dependencies...\n"
            "hianime.at links fetched\n"
            "All links:\n"
            "1080 >https://stream.example/1080/index.m3u8\n"
            "Selected link:\n"
            "https://stream.example/1080/index.m3u8\n"
            "Subtitles:\n"
            "https://stream.example/subs/de_forced.vtt\n"
            'JSON:\n{"download_url":"/download/mal/123/15/sub","src":"https://stream.example/master.m3u8",'
            '"subtitles":[{"lang":"en","label":"English (CR)","default":true,"src":"https://stream.example/subs/en.vtt"},'
            '{"lang":"de","label":"German (CR)","default":false,"src":"https://stream.example/subs/de_forced.vtt"}],'
            '"skip":{"intro":{"start":107,"end":197},"outro":{"start":1345,"end":1435}}}\n'
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)

        info = resolve_stream_info("Slime S4", 15)
        self.assertIsNotNone(info)
        self.assertEqual(info.video_link, "https://stream.example/1080/index.m3u8")
        self.assertEqual(info.referrer, "https://zokoanime.video/")
        self.assertEqual(len(info.subtitles), 2)
        self.assertEqual(info.subtitles[0]["lang"], "en")
        self.assertEqual(info.intro_skip, (107.0, 197.0))
        self.assertEqual(info.outro_skip, (1345.0, 1435.0))

    @patch("ani_cli_sync.subtitles.subprocess.run")
    def test_resolve_stream_info_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        info = resolve_stream_info("Nonexistent", 1)
        self.assertIsNone(info)

    @patch("ani_cli_sync.subtitles.subprocess.run")
    def test_resolve_stream_info_null_skip(self, mock_run):
        mock_output = (
            "Selected link:\n"
            "https://stream.example/1080/index.m3u8\n"
            'JSON:\n{"download_url":"/download/mal/123/16/sub","src":"https://stream.example/master.m3u8",'
            '"subtitles":[{"lang":"en","label":"English","src":"https://stream.example/subs/en.vtt"}],'
            '"skip":null}\n'
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)

        info = resolve_stream_info("Slime S4", 16)
        self.assertIsNotNone(info)
        self.assertIsNone(info.intro_skip)
        self.assertIsNone(info.outro_skip)

    @patch("ani_cli_sync.subtitles.subprocess.run")
    def test_resolve_stream_info_uncensored_env(self, mock_run):
        mock_output = (
            "Selected link:\nhttps://stream.example/1080/index.m3u8\n"
            'JSON:{"subtitles":[]}\n'
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)

        resolve_stream_info("High School DxD", 1, uncensored=True)
        self.assertTrue(mock_run.called)
        called_env = mock_run.call_args[1].get("env", {})
        self.assertIn("ANI_CLI_MENU", called_env)
        self.assertEqual(called_env.get("ANI_CLI_SYNC_UNCENSORED"), "1")
        self.assertEqual(called_env.get("ANI_CLI_SYNC_TARGET_TITLE"), "High School DxD")

    @patch("ani_cli_sync.subtitles.subprocess.run")
    def test_resolve_stream_info_censored_env(self, mock_run):
        mock_output = (
            "Selected link:\nhttps://stream.example/1080/index.m3u8\n"
            'JSON:{"subtitles":[]}\n'
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)

        resolve_stream_info("High School DxD", 1, uncensored=False)
        self.assertTrue(mock_run.called)
        called_env = mock_run.call_args[1].get("env", {})
        self.assertEqual(called_env.get("ANI_CLI_SYNC_UNCENSORED"), "0")


class TestMPVCommandBuilder(unittest.TestCase):
    def test_build_mpv_command(self):
        info = StreamInfo(
            video_link="https://stream.example/1080/index.m3u8",
            referrer="https://zokoanime.video/",
            subtitles=[],
            intro_skip=(107.0, 197.0),
            outro_skip=(1345.0, 1435.0),
        )
        plan = SubtitlePlan(
            sub_files=["/cache/de.vtt", "/cache/zh-pinyin.vtt", "https://stream.example/subs/en.vtt"],
            sid=1,
            secondary_sid=2,
        )
        cmd = build_mpv_command(info, plan, "Slime Season 4", 15)
        self.assertEqual(cmd[0], "mpv")
        self.assertIn("--referrer=https://zokoanime.video/", cmd)
        self.assertIn("--sub-file=/cache/de.vtt", cmd)
        self.assertIn("--sub-file=/cache/zh-pinyin.vtt", cmd)
        self.assertIn("--sub-file=https://stream.example/subs/en.vtt", cmd)
        self.assertIn("--sid=1", cmd)
        self.assertIn("--secondary-sid=2", cmd)
        self.assertIn("--script-opts-append=skip-op_start=107.0", cmd)
        self.assertIn("--script-opts-append=skip-op_end=197.0", cmd)
        self.assertIn("--script-opts-append=skip-ed_start=1345.0", cmd)
        self.assertIn("--script-opts-append=skip-ed_end=1435.0", cmd)
        self.assertIn("--force-media-title=Slime Season 4 Episode 15", cmd)
        self.assertEqual(cmd[-1], "https://stream.example/1080/index.m3u8")

    def test_build_mpv_command_omits_sub_delay_by_default(self):
        info = StreamInfo(
            video_link="https://stream.example/1080/index.m3u8",
            referrer="https://zokoanime.video/",
            subtitles=[],
        )
        plan = SubtitlePlan(sub_files=["/cache/de.vtt"], sid=1, secondary_sid=0)
        cmd = build_mpv_command(info, plan, "AoT", 1)
        self.assertFalse(any(a.startswith("--sub-delay") for a in cmd))

    def test_build_mpv_command_applies_negative_sub_delay(self):
        info = StreamInfo(
            video_link="https://stream.example/1080/index.m3u8",
            referrer="https://zokoanime.video/",
            subtitles=[],
        )
        plan = SubtitlePlan(sub_files=["/cache/de.vtt"], sid=1, secondary_sid=0)
        cmd = build_mpv_command(info, plan, "AoT", 1, sub_delay=-4.0)
        self.assertIn("--sub-delay=-4.0", cmd)

    def test_build_mpv_command_applies_positive_sub_delay(self):
        info = StreamInfo(
            video_link="https://stream.example/1080/index.m3u8",
            referrer="https://zokoanime.video/",
            subtitles=[],
        )
        plan = SubtitlePlan(sub_files=["/cache/de.vtt"], sid=1, secondary_sid=0)
        cmd = build_mpv_command(info, plan, "AoT", 1, sub_delay=0.5)
        self.assertIn("--sub-delay=0.5", cmd)


class TestSubtitleTranslationAndPlanning(unittest.TestCase):
    def test_prepare_subtitles_does_not_treat_uniform_lang_as_english(self):
        """The provider stamps lang="en" on every track, so lang must not decide which
        track is English. Selecting by lang alone picks the first track in the payload,
        which on some releases is Arabic."""
        tracks = [
            {"lang": "en", "label": "Arabic", "src": "https://s/arabic.vtt"},
            {"lang": "en", "label": "English", "src": "https://s/english.vtt"},
            {"lang": "en", "label": "German (- Deutsch)", "src": "https://s/german.vtt"},
        ]
        info = StreamInfo(
            video_link="https://s/1080/index.m3u8",
            referrer="https://zokoanime.video/",
            subtitles=tracks,
        )

        arabic_vtt = "WEBVTT\n\n00:00.460 --> 00:01.880\nARABIC-LINE\n"
        english_vtt = "WEBVTT\n\n00:00.460 --> 00:01.880\nENGLISH-LINE\n"

        def fake_fetch(url, timeout=30, referrer=None):
            if url.endswith("arabic.vtt"):
                return arabic_vtt
            if url.endswith("english.vtt"):
                return english_vtt
            return SAMPLE_FORCED_VTT  # German is sign-only, so it is not used as primary

        with (
            tempfile.TemporaryDirectory() as td,
            patch("ani_cli_sync.subtitles.fetch_vtt_text", side_effect=fake_fetch),
            patch("ani_cli_sync.subtitles.translate_cues_llm", return_value=None) as mock_translate,
        ):
            prepare_subtitles(info, "JJK", 1, primary_lang="de", cache_dir=Path(td))

        if mock_translate.called:
            base_cues = mock_translate.call_args[0][0]
            text = " ".join(line for cue in base_cues for line in cue.lines)
            self.assertNotIn("ARABIC-LINE", text)

    @patch("ani_cli_sync.subtitles.urllib.request.urlopen")
    def test_translate_cues_llm_german(self, mock_urlopen):
        resp_json = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            [
                                "<b>— VOR 300 JAHREN —</b>",
                                "<b>Das Einzige, woran ich mich erinnere, ist...</b>",
                                "<b>Ich habe gewütet.</b>",
                            ]
                        )
                    }
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(resp_json).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        cues = parse_vtt(SAMPLE_VTT)
        translated = translate_cues_llm(cues, target_lang="de")
        self.assertIsNotNone(translated)
        self.assertEqual(len(translated), 3)
        self.assertIn("VOR 300 JAHREN", translated[0].lines[0])

    @patch("ani_cli_sync.subtitles.urllib.request.urlopen")
    def test_translate_cues_llm_zh_pinyin(self, mock_urlopen):
        # Each element is two lines: pinyin then hanzi, joined with \n inside the
        # JSON string so the same parser can split it back into cue lines.
        resp_json = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            [
                                "<b>— Sānbǎi nián qián —</b>\n<b>— 三百年前 —</b>",
                                "<b>Wǒ wéiyī jìde de shì...</b>\n<b>我唯一記得的是...</b>",
                                "<b>Wǒ fākuáng le.</b>\n<b>我發狂了。</b>",
                            ]
                        )
                    }
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(resp_json).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        cues = parse_vtt(SAMPLE_VTT)
        translated = translate_cues_llm(cues, target_lang="zh-pinyin")
        self.assertIsNotNone(translated)
        self.assertEqual(len(translated), 3)
        self.assertEqual(len(translated[0].lines), 2)
        self.assertIn("Sānbǎi nián qián", translated[0].lines[0])
        self.assertIn("三百年前", translated[0].lines[1])

    @patch("ani_cli_sync.subtitles.fetch_vtt_text")
    def test_prepare_subtitles_cached(self, mock_fetch):
        # If cache files exist, fetch_vtt_text is never called
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            de_path = tmp_dir / "slime_ep15_de.vtt"
            zh_path = tmp_dir / "slime_ep15_zh-pinyin.vtt"
            de_path.write_text(SAMPLE_VTT, encoding="utf-8")
            zh_path.write_text(SAMPLE_VTT, encoding="utf-8")

            info = StreamInfo(
                video_link="https://stream.example/1080/index.m3u8",
                referrer="https://zokoanime.video/",
                subtitles=[{"lang": "en", "label": "English (CR)", "src": "https://stream.example/en.vtt"}],
            )

            plan = prepare_subtitles(
                info,
                "slime",
                15,
                primary_lang="de",
                secondary_lang="zh-pinyin",
                cache_dir=tmp_dir,
            )

            self.assertEqual(plan.sub_files[0], str(de_path))
            self.assertEqual(plan.sub_files[1], str(zh_path))
            self.assertEqual(plan.sid, 1)
            self.assertEqual(plan.secondary_sid, 2)
            mock_fetch.assert_not_called()

    @patch("ani_cli_sync.subtitles.translate_cues_llm")
    @patch("ani_cli_sync.subtitles.fetch_vtt_text")
    def test_prepare_subtitles_default_secondary_none(self, mock_fetch, mock_translate):
        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            mock_fetch.return_value = SAMPLE_VTT
            mock_translate.return_value = parse_vtt(SAMPLE_VTT)

            info = StreamInfo(
                video_link="https://stream.example/1080/index.m3u8",
                referrer="https://zokoanime.video/",
                subtitles=[{"lang": "en", "label": "English (CR)", "src": "https://stream.example/en.vtt"}],
            )

            plan = prepare_subtitles(
                info,
                "slime",
                15,
                primary_lang="de",
                secondary_lang=None,
                cache_dir=tmp_dir,
            )

            # German translated once, Chinese never translated
            self.assertEqual(mock_translate.call_count, 1)
            self.assertEqual(mock_translate.call_args[1]["target_lang"], "de")
            # Secondary track falls back to stream English
            self.assertEqual(len(plan.sub_files), 2)
            self.assertEqual(plan.sub_files[1], "https://stream.example/en.vtt")
            self.assertEqual(plan.sid, 1)
            self.assertEqual(plan.secondary_sid, 2)

    @patch("ani_cli_sync.subtitles.prepare_subtitles")
    @patch("ani_cli_sync.subtitles.resolve_stream_info")
    def test_prefetch_next_episode(self, mock_resolve, mock_prepare):
        info = StreamInfo(video_link="https://stream.example/video.m3u8", referrer="https://zokoanime.video/", subtitles=[])
        mock_resolve.return_value = info

        from ani_cli_sync.subtitles import prefetch_next_episode
        prefetch_next_episode("Show", 2, primary_lang="de", secondary_lang=None, uncensored=True)

        mock_resolve.assert_called_once_with("Show", 2, quality=None, dub=False, uncensored=True)
        mock_prepare.assert_called_once()
        self.assertEqual(mock_prepare.call_args[1]["primary_lang"], "de")
        self.assertIsNone(mock_prepare.call_args[1]["secondary_lang"])


class TestTranslationReassemblyAfterModelDrift(unittest.TestCase):

    """Issue #64: the German model occasionally merges/drops cues in a batch,
    which used to silently shift every subsequent cue by +1 and produce the
    translation of cue N-1 paired with the timing of cue N. The fix moves
    timings out of the request entirely and reassembles cues client-side, so
    a length mismatch must never shift a translation onto a different timing.
    """

    # Five cues, distinct text and distinct IDs, with timings the test can
    # byte-compare against the input batch.
    INPUT_CUES: ClassVar = [
        VTTCue(identifier="1", timing="00:00.460 --> 00:01.880", lines=["Fire!"]),
        VTTCue(identifier="2", timing="00:01.960 --> 00:03.710", lines=["Charge!"]),
        VTTCue(identifier="3", timing="00:03.960 --> 00:06.380", lines=["Retreat!"]),
        VTTCue(identifier="4", timing="00:06.500 --> 00:08.000", lines=["Hold!"]),
        VTTCue(identifier="5", timing="00:08.200 --> 00:09.700", lines=["Move!"]),
    ]

    EXPECTED_DE: ClassVar = ["Feuer!", "Angriff!", "Rückzug!", "Halten!", "Bewegen!"]

    def _make_urlopen_mock(self, response_by_index):
        """Build a mock urlopen whose response depends on the size of the
        batch in the request body. `response_by_index` maps
        len(user_message_lines) -> response JSON dict.
        """

        def fake_urlopen(req, timeout=None):
            body = json.loads(req.data.decode("utf-8"))
            user_content = body["messages"][1]["content"]
            n_lines = sum(1 for line in user_content.split("\n") if line)
            res_data = response_by_index[n_lines]
            resp = MagicMock()
            resp.read.return_value = json.dumps(res_data).encode("utf-8")
            resp.__enter__.return_value = resp
            return resp

        return fake_urlopen

    def test_request_body_contains_no_timestamps(self):
        """Capture the JSON sent and assert no timing pattern leaks through.
        Otherwise the model could echo a shifted timing back and the +1 bug
        would silently come back.
        """
        captured: dict = {}

        def fake_urlopen(req, timeout=None):
            captured["body"] = json.loads(req.data.decode("utf-8"))
            res_data = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(["Feuer!", "Angriff!", "Rückzug!", "Halten!", "Bewegen!"]),
                        }
                    }
                ]
            }
            resp = MagicMock()
            resp.read.return_value = json.dumps(res_data).encode("utf-8")
            resp.__enter__.return_value = resp
            return resp

        with patch("ani_cli_sync.subtitles.urllib.request.urlopen", side_effect=fake_urlopen):
            result = translate_cues_llm(self.INPUT_CUES, target_lang="de")
        self.assertIsNotNone(result)

        body = captured["body"]
        user_content = body["messages"][1]["content"]
        self.assertNotIn("-->", user_content)

        self.assertNotRegex(user_content, r"\d\d:\d\d")
        # No identifier, no timing, no WEBVTT marker either.
        self.assertNotIn("WEBVTT", user_content)

    def test_bisect_recovers_correct_alignment_when_model_drops_a_cue(self):
        """The whole-batch response has 4 items instead of 5 (model dropped
        one). After bisect the per-cue translations land on the correct
        timings -- none shift +1 -- and timings are byte-identical to input.
        """
        # Full batch returns 4 items (model dropped cue 1). Bisect halves
        # into cues 0..1 and cues 2..4; each half is translated correctly.
        responses = {
            5: {
                "choices": [
                    {
                        "message": {
                            # Drops "Charge!" entirely -> old buggy code
                            # would have paired "Angriff!" with the timing
                            # of "Fire!" (a +1 backward shift).
                            "content": json.dumps(
                                ["Feuer!", "Angriff!", "Rückzug!", "Halten!"]
                            ),
                        }
                    }
                ]
            },
            # Left half (2 cues): translated correctly.
            2: {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(["Feuer!", "Angriff!"]),
                        }
                    }
                ]
            },
            # Right half (3 cues): translated correctly.
            3: {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                ["Rückzug!", "Halten!", "Bewegen!"]
                            ),
                        }
                    }
                ]
            },
        }
        with patch(
            "ani_cli_sync.subtitles.urllib.request.urlopen",
            side_effect=self._make_urlopen_mock(responses),
        ):
            result = translate_cues_llm(self.INPUT_CUES, target_lang="de")
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 5)
        # Every timing byte-identical to input.
        for got, orig in zip(result, self.INPUT_CUES):
            self.assertEqual(got.timing, orig.timing)
            self.assertEqual(got.identifier, orig.identifier)
        # The translation paired with timing 01.960 is "Angriff!", which is
        # the translation of "Charge!" (input cue index 1). It is NOT
        # "Rückzug!" (the translation of input cue index 2), which is what
        # the old +1-shift bug would have produced.
        self.assertEqual(result[1].lines, ["Angriff!"])
        self.assertEqual(result[1].timing, "00:01.960 --> 00:03.710")
        # Other cues also map to their own translation, not a neighbour's.
        self.assertEqual(result[0].lines, ["Feuer!"])
        self.assertEqual(result[2].lines, ["Rückzug!"])
        self.assertEqual(result[3].lines, ["Halten!"])
        self.assertEqual(result[4].lines, ["Bewegen!"])
    def test_leaf_persistent_mismatch_falls_back_to_original_english(self):
        """After bisect down to a single cue that still misaligns after the
        retry budget, that cue falls back to its original English lines at
        its own timing. Its neighbours are still translated.
        """
        # For the full batch, return only 1 item (simulate everything dropped).
        # That forces bisect -> bisect -> leaf of size 1.
        responses = {
            5: {"choices": [{"message": {"content": json.dumps(["Feuer!"])}}]},
        }
        # For the recursive half-batches of size 2 and 3, also return too few.
        responses[3] = {"choices": [{"message": {"content": json.dumps(["Feuer!"])}}]}
        responses[2] = {"choices": [{"message": {"content": json.dumps(["Feuer!"])}}]}
        # For the leaf of size 1, still return too few. Now we fall back.
        responses[1] = {"choices": [{"message": {"content": json.dumps([])}}]}

        with patch(
            "ani_cli_sync.subtitles.urllib.request.urlopen",
            side_effect=self._make_urlopen_mock(responses),
        ):
            result = translate_cues_llm(self.INPUT_CUES, target_lang="de")

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 5)
        for got, orig in zip(result, self.INPUT_CUES):
            self.assertEqual(got.timing, orig.timing)
            self.assertEqual(got.identifier, orig.identifier)
        # Every cue is the original English: nothing got the chance to translate.
        for got, orig in zip(result, self.INPUT_CUES):
            self.assertEqual(got.lines, list(orig.lines))

    def test_no_shift_when_model_drops_first_cue_in_batch(self):
        """Regression for issue #64: when the model drops cue 0 of a batch,
        the old code paired every translation with the cue immediately after
        it. The translation of cue T must now pair with the timing of cue T
        (or with English fallback if bisect reaches it).
        """
        # Two-cue input that mirrors the AoT S1 ep5 symptom: "Fire!" then
        # "Charge!". Model returns only "Angriff!" (the translation of
        # "Charge!"), dropping "Feuer!" entirely. Old buggy code would have
        # paired "Angriff!" with the timing of "Fire!" (a +1 backward shift).
        batch = [
            VTTCue(identifier="a", timing="00:00.460 --> 00:01.880", lines=["Fire!"]),
            VTTCue(identifier="b", timing="00:01.960 --> 00:03.710", lines=["Charge!"]),
        ]
        # First request is the full 2-cue batch; the model returns 1 item.
        # At leaf size <=2 the function falls back to original English for
        # the whole batch when the count is still off, so result[0] is
        # "Fire!" at its own timing and result[1] is "Charge!" at its own.
        responses = {
            2: {"choices": [{"message": {"content": json.dumps(["Angriff!"])}}]},
        }
        with patch(
            "ani_cli_sync.subtitles.urllib.request.urlopen",
            side_effect=self._make_urlopen_mock(responses),
        ):
            result = translate_cues_llm(batch, target_lang="de")
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        # Timings are byte-identical to the input -- no shift.
        self.assertEqual(result[0].timing, "00:00.460 --> 00:01.880")
        self.assertEqual(result[1].timing, "00:01.960 --> 00:03.710")
        # Neither cue carries the translation of a different cue at its own
        # timing: result[0] is the original English "Fire!" (fallback),
        # NOT "Angriff!". result[1] is the original English "Charge!".
        # The crucial anti-shift assertion:
        self.assertNotEqual(result[0].lines, ["Angriff!"])
        self.assertEqual(result[0].lines, ["Fire!"])
        self.assertEqual(result[1].lines, ["Charge!"])

    def test_bisect_recovers_correct_alignment_zh_pinyin(self):
        """Same regression as the German bisect test, for the zh-pinyin
        path where each element is two lines (pinyin + hanzi).
        """
        cues = [
            VTTCue(identifier="1", timing="00:00.460 --> 00:01.880", lines=["Hello"]),
            VTTCue(identifier="2", timing="00:01.960 --> 00:03.710", lines=["World"]),
            VTTCue(identifier="3", timing="00:03.960 --> 00:06.380", lines=["Goodbye"]),
            VTTCue(identifier="4", timing="00:06.500 --> 00:08.000", lines=["Friend"]),
        ]
        # Drop one element on the full 4-cue call -> bisect kicks in.
        responses = {
            4: {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                [
                                    "Nǐ hǎo\n你好",
                                    "Shìjiè\n世界",
                                    "Zàijiàn\n再見",
                                ]
                            ),
                        }
                    }
                ]
            },
        }
        # For the half of size 2 the model returns the correct 2-item array.
        responses[2] = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            ["Zàijiàn\n再見", "Péngyǒu\n朋友"],
                        )
                    }
                }
            ]
        }
        with patch(
            "ani_cli_sync.subtitles.urllib.request.urlopen",
            side_effect=self._make_urlopen_mock(responses),
        ):
            result = translate_cues_llm(cues, target_lang="zh-pinyin")
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 4)
        # Every timing byte-identical to input.
        for got, orig in zip(result, cues):
            self.assertEqual(got.timing, orig.timing)
        # No +1 drift: timing of cue 2 carries the translation of cue 2,
        # not the translation of cue 1.
        self.assertEqual(result[2].lines[0], "Zàijiàn")
        self.assertEqual(result[3].lines[0], "Péngyǒu")


class TestTranslationDefaults(unittest.TestCase):
    """The translation defaults are measured facts, not preferences.

    Measured 2026-10-05 against the local LiteLLM proxy, one real 50-cue AoT S1 ep6
    batch through the shipped code path: minimax-m3 17.5s, gemini-3.1-flash-lite 5.5s,
    minimax-m2.7-highspeed 29.9s, minimax-m2.7 31.8s, deepseek-v4-flash 139.4s.
    gemini-3.6-flash answers HTTP 400 and is not a candidate.

    deepseek-v4-flash is a reasoning model: it burns reasoning tokens before any
    content, so a 50-cue batch does not finish inside the socket timeout. That is why
    a single episode stalled for the full 180s retry budget and still returned the
    English track.
    """

    def test_default_model_is_a_non_reasoning_model(self):
        self.assertEqual(DEFAULT_MODEL, "minimax-m3")

    def test_default_model_is_overridable_by_env(self):
        import importlib

        import ani_cli_sync.subtitles as subtitles_module

        with patch.dict(os.environ, {"ANI_CLI_SYNC_LLM_MODEL": "some-other-model"}):
            reloaded = importlib.reload(subtitles_module)
            try:
                self.assertEqual(reloaded.DEFAULT_MODEL, "some-other-model")
            finally:
                patch.dict(os.environ)
                importlib.reload(subtitles_module)  # restore for other tests

    def test_batch_timeout_is_bounded(self):
        # 45s is ~2.5x the measured healthy batch (17.5s) while capping a stalled
        # batch well below the old 90s, which is what let one episode hang for 180s.
        import inspect

        params = inspect.signature(_translate_single_batch).parameters
        self.assertEqual(params["timeout"].default, 45)

    def test_client_retries_do_not_multiply_the_proxy_retries(self):
        # LiteLLM already retries internally (num_retries: 3). A client-side second
        # attempt doubled the wall time for no benefit.
        import inspect

        params = inspect.signature(_translate_single_batch).parameters
        self.assertEqual(params["retries"].default, 1)


class TestTranslateAbortsWithoutWaitingForStragglers(unittest.TestCase):
    """A failed batch must return promptly, not after every sibling finishes.

    translate_cues_llm returns None on the first failed batch, but it does so from
    inside the `with ThreadPoolExecutor` block, so __exit__ shut the executor down
    with wait=True and blocked until every in-flight batch had burned its full
    timeout x retries budget. With cancel_futures the abort is immediate.
    """

    def test_returns_before_slow_siblings_finish(self):
        import threading
        import time

        import ani_cli_sync.subtitles as subtitles_module

        started = threading.Event()
        release = threading.Event()

        def fake_single_batch(batch_idx, batch, endpoint, model, sys_prompt, timeout=90, retries=2):
            if batch_idx == 0:
                started.set()
                return batch_idx, None  # immediate failure
            started.set()
            release.wait(30)  # a sibling that would otherwise stall the caller
            return batch_idx, batch

        cues = parse_vtt(SAMPLE_VTT) * 20  # 60 cues -> 2 batches, so a sibling exists
        with patch.object(subtitles_module, "_translate_single_batch", side_effect=fake_single_batch):
            t0 = time.time()
            try:
                result = subtitles_module.translate_cues_llm(cues, "de")
            finally:
                release.set()  # never leave the sibling thread blocked
        elapsed = time.time() - t0
        self.assertIsNone(result)
        self.assertLess(elapsed, 10.0, f"abort waited {elapsed:.1f}s for in-flight batches")

    def test_all_batches_ok_still_returns_translations(self):
        import ani_cli_sync.subtitles as subtitles_module

        def fake_single_batch(batch_idx, batch, endpoint, model, sys_prompt, timeout=90, retries=2):
            return batch_idx, [c for c in batch]

        cues = parse_vtt(SAMPLE_VTT) * 20
        with patch.object(subtitles_module, "_translate_single_batch", side_effect=fake_single_batch):
            result = subtitles_module.translate_cues_llm(cues, "de")
        self.assertIsNotNone(result)
        self.assertEqual(len(result), len(cues))


class TestFetchVttHeaders(unittest.TestCase):
    """The subtitle CDN 403s a fetch that omits the stream's Referer.

    Verified live against hls.dramahot.top with a freshly resolved stream: identical URL,
    HTTP 403 with only a User-Agent, HTTP 200 with the stream's Referer. mpv already sends
    it via --referrer, which is why subtitles play but never reached the cache.
    """

    URL = "https://hls.example/v/abc/subs/en.vtt"
    REFERRER = "https://zokoanime.video/"

    def _capture(self):
        captured: dict = {}

        class _Resp:
            def read(self, *_a):
                return SAMPLE_VTT.encode()

            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

        def fake_urlopen(req, timeout=None):
            captured["headers"] = {k.lower(): v for k, v in req.header_items()}
            return _Resp()

        patcher = patch("urllib.request.urlopen", side_effect=fake_urlopen)
        patcher.start()
        self.addCleanup(patcher.stop)
        return captured

    def test_sends_referer_when_given(self):
        captured = self._capture()
        self.assertIn("WEBVTT", fetch_vtt_text(self.URL, referrer=self.REFERRER))
        self.assertEqual(captured["headers"].get("referer"), self.REFERRER)

    def test_no_referrer_still_fetches(self):
        # Providers that do not gate on Referer, and existing callers, keep working.
        captured = self._capture()
        self.assertIn("WEBVTT", fetch_vtt_text(self.URL))
        self.assertNotIn("referer", captured["headers"])

    def test_user_agent_is_always_sent(self):
        captured = self._capture()
        fetch_vtt_text(self.URL, referrer=self.REFERRER)
        self.assertIn("ani-cli-sync", captured["headers"].get("user-agent", ""))

    def test_prepare_subtitles_forwards_the_stream_referrer(self):
        captured = self._capture()
        info = StreamInfo(
            video_link="https://hls.example/1080/index.m3u8",
            referrer=self.REFERRER,
            subtitles=[{"lang": "en", "label": "English", "src": self.URL}],
        )
        with (
            tempfile.TemporaryDirectory() as td,
            patch("ani_cli_sync.subtitles.translate_cues_llm", return_value=None),
        ):
            plan = prepare_subtitles(info, "aot", 6, primary_lang="de", cache_dir=Path(td))
        self.assertEqual(captured["headers"].get("referer"), self.REFERRER)
        # German track absent -> base English fetched (and translation stubbed out below is
        # not needed: without a translator the plan falls back to the English URL).
        self.assertTrue(plan.sub_files)


class TestFetchVttSecurity(unittest.TestCase):
    def test_rejects_file_scheme(self):
        with self.assertRaises(ValueError):
            fetch_vtt_text("file:///etc/passwd")

    def test_rejects_non_http_scheme(self):
        with self.assertRaises(ValueError):
            fetch_vtt_text("ftp://example.com/subs.vtt")

    def test_rejects_empty_netloc(self):
        with self.assertRaises(ValueError):
            fetch_vtt_text("http:///subs.vtt")


if __name__ == "__main__":
    unittest.main()
