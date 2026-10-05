from __future__ import annotations

import math
import subprocess
import sys
import tempfile
import types
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from ani_cli_sync.subsync import (
    MAX_PLAUSIBLE_OFFSET,
    _first_cue,
    _first_speech_onset,
    measure_offset,
)
from ani_cli_sync.subtitles import StreamInfo, parse_vtt

SAMPLE_VTT = """WEBVTT

00:00:41.870 --> 00:00:45.620
Humanity was suddenly reminded that day...

00:00:51.620 --> 00:00:54.580
...of the terror of being at their mercy...
"""

EP2_VTT = """WEBVTT

00:00:21.540 --> 00:00:27.660
Over a century ago, beings that

00:00:32.200 --> 00:00:37.790
Their absolutely overwhelming strength
"""

INFO = StreamInfo(
    video_link="https://hls.example/1080/index.m3u8",
    referrer="https://zokoanime.video/",
)


def _write_vtt(tmp: Path, text: str = SAMPLE_VTT) -> Path:
    p = tmp / "sub.vtt"
    p.write_text(text, encoding="utf-8")
    return p


class TestMeasureOffset(unittest.TestCase):
    """offset = first speech onset - first cue start.

    Sign is load-bearing: mpv's --sub-delay is negative to pull subtitles EARLIER, so a
    subtitle file that is late (cue after speech) must yield a negative offset.
    """

    def _measure(self, tmp: Path, onset: float | None, cue_text: str = SAMPLE_VTT):
        sub = _write_vtt(tmp, cue_text)
        with (
            patch("ani_cli_sync.subsync.vad_available", return_value=True),
            patch("ani_cli_sync.subsync._extract_audio", return_value=tmp / "a.wav"),
            patch("ani_cli_sync.subsync._first_speech_onset", return_value=onset),
        ):
            return measure_offset(INFO, str(sub))

    def test_late_subtitles_yield_negative_offset(self):
        # Ep 1 of Attack on Titan: cue 41.870, speech 38.50 -> -3.37
        with tempfile.TemporaryDirectory() as td:
            r = self._measure(Path(td), onset=38.50)
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r.offset, 38.50 - 41.870, places=2)
        self.assertLess(r.offset, 0, "late subtitles must produce a negative offset")

    def test_early_subtitles_yield_positive_offset(self):
        # Ep 2: cue 21.540, speech 21.79 -> +0.25
        with tempfile.TemporaryDirectory() as td:
            r = self._measure(Path(td), onset=21.79, cue_text=EP2_VTT)
        self.assertAlmostEqual(r.offset, 21.79 - 21.540, places=2)
        self.assertGreater(r.offset, 0)

    def test_aligned_subtitles_yield_near_zero(self):
        with tempfile.TemporaryDirectory() as td:
            r = self._measure(Path(td), onset=41.9)
        self.assertAlmostEqual(r.offset, 0.03, places=2)

    def test_result_reports_onset_and_cue_for_logging(self):
        with tempfile.TemporaryDirectory() as td:
            r = self._measure(Path(td), onset=38.5)
        self.assertAlmostEqual(r.onset, 38.5, places=3)
        self.assertAlmostEqual(r.first_cue, 41.870, places=3)


class TestConfidenceGate(unittest.TestCase):
    """A wrong auto-shift is worse than no shift, so anything uncertain reports instead."""

    def _measure(self, tmp: Path, onset, cue_text=SAMPLE_VTT):
        sub = _write_vtt(tmp, cue_text)
        with (
            patch("ani_cli_sync.subsync.vad_available", return_value=True),
            patch("ani_cli_sync.subsync._extract_audio", return_value=tmp / "a.wav"),
            patch("ani_cli_sync.subsync._first_speech_onset", return_value=onset),
        ):
            return measure_offset(INFO, str(sub))

    def test_no_speech_detected_is_not_confident(self):
        with tempfile.TemporaryDirectory() as td:
            r = self._measure(Path(td), onset=None)
        self.assertFalse(r.confident)
        self.assertIn("no dialogue", r.reason)

    def test_implausible_offset_is_not_confident(self):
        with tempfile.TemporaryDirectory() as td:
            r = self._measure(Path(td), onset=500.0)
        self.assertFalse(r.confident)
        self.assertGreater(abs(r.offset), MAX_PLAUSIBLE_OFFSET)
        self.assertIn("implausible", r.reason)

    def test_empty_subtitle_file_is_not_confident(self):
        with tempfile.TemporaryDirectory() as td:
            r = self._measure(Path(td), onset=38.0, cue_text="WEBVTT\n\n")
        self.assertFalse(r.confident)
        self.assertIn("no cues", r.reason)

    def test_typical_offset_is_confident(self):
        with tempfile.TemporaryDirectory() as td:
            r = self._measure(Path(td), onset=38.5)
        self.assertTrue(r.confident)


class TestGracefulDegradation(unittest.TestCase):
    """The core must keep working with zero third-party dependencies installed."""

    def test_missing_vad_dependency_returns_none_without_raising(self):
        with tempfile.TemporaryDirectory() as td:
            sub = _write_vtt(Path(td))
            real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

            def fake_import(name, *a, **k):
                if name.startswith("silero_vad"):
                    raise ImportError("No module named 'silero_vad'")
                return real_import(name, *a, **k)

            with (
                patch("ani_cli_sync.subsync._extract_audio", return_value=Path(td) / "a.wav"),
                patch("builtins.__import__", side_effect=fake_import),
            ):
                r = measure_offset(INFO, str(sub))
        self.assertIsNone(r)

    def test_vad_available_flag_is_false_when_missing(self):
        from ani_cli_sync import subsync

        real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

        def fake_import(name, *a, **k):
            if name.startswith("silero_vad"):
                raise ImportError("nope")
            return real_import(name, *a, **k)

        with patch("builtins.__import__", side_effect=fake_import):
            self.assertFalse(subsync.vad_available())


class TestFfmpegExtraction(unittest.TestCase):
    """-extension_picky 0 is mandatory: the provider serves .ts.jpg segments, which ffmpeg
    otherwise rejects with 'not in allowed_segment_extensions'."""

    def test_extract_audio_passes_extension_picky_and_referer(self):
        from ani_cli_sync import subsync

        with patch("ani_cli_sync.subsync.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0, b"", b"")
            with tempfile.TemporaryDirectory() as td:
                subsync._extract_audio(INFO, 30.0, Path(td))

        argv = mock_run.call_args[0][0]
        self.assertIn("-extension_picky", argv)
        self.assertEqual(argv[argv.index("-extension_picky") + 1], "0")
        self.assertIn("-headers", argv)
        self.assertTrue(
            any("Referer:" in a for a in argv if a != "-headers"),
            f"a Referer header value is required, argv={argv}",
        )

    def test_extract_audio_returns_none_on_ffmpeg_failure(self):
        from ani_cli_sync import subsync

        with patch("ani_cli_sync.subsync.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 1, b"", b"boom")
            with tempfile.TemporaryDirectory() as td:
                self.assertIsNone(subsync._extract_audio(INFO, 30.0, Path(td)))


class TestFirstCueReuse(unittest.TestCase):
    def test_first_cue_reads_local_file(self):
        from ani_cli_sync.subsync import _first_cue

        with tempfile.TemporaryDirectory() as td:
            sub = _write_vtt(Path(td))
            self.assertAlmostEqual(_first_cue(str(sub)), 41.870, places=3)

    def test_first_cue_parses_existing_vtt_parser(self):
        """Guard against a second, divergent timestamp parser.

        ``subsync`` must consume what ``parse_vtt`` produces rather than re-parsing raw
        lines, so there is exactly one timestamp parser in the project.
        """
        from ani_cli_sync.subsync import _timing_to_seconds

        cues = parse_vtt(SAMPLE_VTT)
        self.assertEqual(len(cues), 2)
        self.assertAlmostEqual(_timing_to_seconds(cues[0].timing), 41.870, places=3)

    def test_timing_accepts_hh_mm_ss_and_mm_ss(self):
        from ani_cli_sync.subsync import _timing_to_seconds

        self.assertAlmostEqual(_timing_to_seconds("00:00:41.870 --> 00:00:45.620"), 41.870, places=3)
        self.assertAlmostEqual(_timing_to_seconds("01:02:03.500 --> 01:02:04.000"), 3723.5, places=3)
        self.assertAlmostEqual(_timing_to_seconds("02:03.500 --> 02:04.000"), 123.5, places=3)
        self.assertIsNone(_timing_to_seconds("not a timing line"))


if __name__ == "__main__":
    unittest.main()

class TestVadAudioType(unittest.TestCase):
    """The VAD must be handed an array, not the raw list _read_wav returns."""

    def _write_wav(self, path, seconds=1.0, rate=16000):
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(b"\x00\x01" * int(rate * seconds))

    def _fake_vad(self, captured, start_ms):
        silero = types.ModuleType("silero_vad")
        silero.load_silero_vad = lambda: "MODEL"

        def get_speech_timestamps(audio, model, **_kwargs):
            captured["audio"] = audio
            captured["model"] = model
            return [{"start": start_ms, "end": start_ms + 500}]

        silero.get_speech_timestamps = get_speech_timestamps
        return silero

    def test_audio_is_converted_to_an_array(self):
        captured = {}
        fake_numpy = types.ModuleType("numpy")
        fake_numpy.float32 = "float32"
        fake_numpy.asarray = lambda values, dtype=None: {"array": list(values), "dtype": dtype}
        silero = self._fake_vad(captured, start_ms=32000)

        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "probe.wav"
            self._write_wav(wav, seconds=3.0)
            with patch.dict(sys.modules, {"silero_vad": silero, "numpy": fake_numpy}):
                onset = _first_speech_onset(wav)

        self.assertEqual(captured["model"], "MODEL")
        self.assertIsInstance(captured["audio"], dict, "VAD received the bare list, not an array")
        self.assertEqual(captured["audio"]["dtype"], "float32")
        self.assertTrue(math.isclose(onset, 2.0))

    def test_returns_none_when_numpy_missing(self):
        # numpy is a hard dependency of silero-vad; without it we must not guess rather
        # than hand the VAD something it cannot index.
        #
        # sys.meta_path is the right hook because it is consulted only on a sys.modules
        # miss. Patching builtins.__import__ instead breaks the earlier
        # `from silero_vad import ...` first, so the function returns None via a
        # different branch and the numpy path is never exercised.
        blocked: list[str] = []

        class BlockNumpy:
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "numpy" or fullname.startswith("numpy."):
                    blocked.append(fullname)
                    raise ImportError(f"numpy blocked for test: {fullname}")

        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "probe.wav"
            self._write_wav(wav, seconds=3.0)
            with (
                patch.dict(sys.modules, {"silero_vad": self._fake_vad({}, 0)}),
                patch.dict(sys.modules),
                patch.object(sys, "meta_path", [BlockNumpy(), *sys.meta_path]),
            ):
                sys.modules.pop("numpy", None)
                self.assertIsNone(_first_speech_onset(wav))

        # Proves the silero import succeeded and execution really reached the numpy step.
        self.assertIn("numpy", blocked)


class TestSubtitleFetchHeaders(unittest.TestCase):
    """The provider 403s subtitle URLs unless the stream's Referer is sent.

    Verified live against hls.dramahot.top with a freshly resolved stream: the same URL
    returns HTTP 403 with only a User-Agent and HTTP 200 with the Referer that mpv
    already receives via --referrer. Without this the measurement silently reports
    "no cues in the subtitle file" on every episode.
    """

    URL = "https://hls.example/v/abc/subs/de.vtt"
    REFERRER = "https://zokoanime.video/"

    def _capture(self, body: bytes):
        """Patch urlopen and return the dict that ends up holding request headers."""
        captured: dict = {}

        class _Resp:
            def read(self, *_a):
                return body

            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

        def fake_urlopen(req, timeout=None):
            captured["headers"] = {k.lower(): v for k, v in req.header_items()}
            captured["url"] = req.full_url
            return _Resp()

        patcher = patch("urllib.request.urlopen", side_effect=fake_urlopen)
        patcher.start()
        self.addCleanup(patcher.stop)
        return captured

    def test_first_cue_sends_referer(self):
        captured = self._capture(SAMPLE_VTT.encode())
        cue = _first_cue(self.URL, referrer=self.REFERRER)
        self.assertAlmostEqual(cue, 41.87, places=2)
        self.assertEqual(captured["headers"].get("referer"), self.REFERRER)

    def test_first_cue_still_works_without_a_referrer(self):
        # Local cache paths and providers that do not gate on Referer must keep working.
        self._capture(SAMPLE_VTT.encode())
        self.assertAlmostEqual(_first_cue(self.URL), 41.87, places=2)

    def test_measure_offset_forwards_the_stream_referrer(self):
        captured = self._capture(SAMPLE_VTT.encode())
        info = StreamInfo(video_link="https://hls.example/1080/index.m3u8", referrer=self.REFERRER)
        with (
            patch("ani_cli_sync.subsync.vad_available", return_value=True),
            patch("ani_cli_sync.subsync._extract_audio", return_value=None),
        ):
            result = measure_offset(info, self.URL)
        self.assertEqual(captured["headers"].get("referer"), self.REFERRER)
        # Audio decode was stubbed out, so the measurement is not confident, but the cue
        # must have been fetched successfully for us to get that far.
        self.assertFalse(result.confident)
        self.assertEqual(result.first_cue, 41.87)
