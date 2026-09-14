from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ani_cli_sync.subtitles import (
    StreamInfo,
    SubtitlePlan,
    VTTCue,
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
        self.assertIn("--script-opts-append=skip-op_start=107.0,skip-op_end=197.0", cmd)
        self.assertIn("--script-opts-append=skip-ed_start=1345.0,skip-ed_end=1435.0", cmd)
        self.assertIn("--force-media-title=Slime Season 4 Episode 15", cmd)
        self.assertEqual(cmd[-1], "https://stream.example/1080/index.m3u8")


class TestSubtitleTranslationAndPlanning(unittest.TestCase):
    @patch("ani_cli_sync.subtitles.urllib.request.urlopen")
    def test_translate_cues_llm_german(self, mock_urlopen):
        resp_json = {
            "choices": [
                {
                    "message": {
                        "content": (
                            "WEBVTT\n\n"
                            "00:00.460 --> 00:01.880\n<b>— VOR 300 JAHREN —</b>\n\n"
                            "00:01.960 --> 00:03.710\n<b>Das Einzige, woran ich mich erinnere, ist...</b>\n\n"
                            "00:03.960 --> 00:06.380\n<b>Ich habe gewütet.</b>\n"
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
        resp_json = {
            "choices": [
                {
                    "message": {
                        "content": (
                            "WEBVTT\n\n"
                            "00:00.460 --> 00:01.880\n"
                            "<b>— Sānbǎi nián qián —</b>\n"
                            "<b>— 三百年前 —</b>\n\n"
                            "00:01.960 --> 00:03.710\n"
                            "<b>Wǒ wéiyī jìde de shì...</b>\n"
                            "<b>我唯一記得的是...</b>\n\n"
                            "00:03.960 --> 00:06.380\n"
                            "<b>Wǒ fākuáng le.</b>\n"
                            "<b>我發狂了。</b>\n"
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
