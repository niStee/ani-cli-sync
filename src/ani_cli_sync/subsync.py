"""ani_cli_sync.subsync: measure per-episode subtitle desync from speech onset.

Some releases ship subtitles cut against a different audio track than the one streamed --
typically English subtitles timed to the English dub while the audio is Japanese original.
mpv reports ``A-V: 0.000`` in that case because it only tracks demuxer PTS, not dialogue
alignment, so nothing local detects the drift.

The offset is a property of the individual subtitle file, not of the series: measured on
Attack on Titan S1, episode 1 needs -3.8s (first cue 41.870, speech 38.50) while episode 2
needs 0 (first cue 21.540, speech 21.79). Never carry a value across episodes.

Method: compare the first subtitle cue against the first speech onset. A neural VAD is
required because an anime cold open has a music bed under the narration, and energy-based
detection (ffmpeg ``silencedetect``) and WebRTC VAD both lock onto the music instead of the
voice. Whole-file FFT cross-correlation -- what ffsubsync, subresync and m314ss do -- is worse
still: dialogue-dense anime has no silence structure, so the correlation is a plateau rather
than a peak and the reported offset walks to the search boundary. One unambiguous
correspondence has no such plateau.

The VAD is an optional dependency. Without it ``measure_offset`` returns ``None`` and the core
keeps working with the standard library alone.
"""

from __future__ import annotations

import json
import logging
import re
import os
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from ani_cli_sync.subtitles import StreamInfo, parse_vtt

logger = logging.getLogger(__name__)

# A subtitle file cut against an entirely different print drifts by minutes, not seconds.
# Beyond this the cause is a different cut, not a timing shift, and shifting is wrong.
MAX_PLAUSIBLE_OFFSET = 60.0

# Speech before this is almost never dialogue: an ambient intro or a sting.
MIN_PLAUSIBLE_ONSET = 0.5

DEFAULT_WINDOW_SECONDS = 180.0

# ffmpeg's HLS demuxer rejects the provider's segment naming. The segments are MPEG-TS
# payloads served as "seg_00000.ts.jpg"; av_match_ext only inspects the final suffix, so
# "jpg" fails the allow-list. allowed_segment_extensions alone is not enough either -- the
# format probe then also rejects the file as unidentifiable. extension_picky 0 short-circuits
# both checks. See https://github.com/FFmpeg/FFmpeg/commit/f99f223 for the upstream split.
FFMPEG_EXTENSION_PICKY_FLAG = "-extension_picky"

_FFMPEG_SAMPLE_RATE = 16000


_TIMING_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?\.\d{1,3})\s*-->\s*(?P<end>\d{1,2}:\d{2}(?::\d{2})?\.\d{1,3})"
)


def _timing_to_seconds(timing: str) -> float | None:
    """Seconds from one side of a WebVTT cue timing line.

    Deliberately written against the ``timing`` string that ``parse_vtt`` already returns,
    rather than re-deriving timestamps from raw lines: there is exactly one timestamp parser
    in the project and this only converts what it produced.
    """
    match = _TIMING_RE.search(timing)
    if not match:
        return None
    parts = match.group("start").split(":")
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds


@dataclass
class OffsetResult:
    """Measured offset plus the evidence behind it.

    ``offset`` is ``speech_onset - first_cue``. mpv's ``--sub-delay`` is negative to pull
    subtitles earlier, so subtitles that appear late yield a negative offset directly.
    """

    offset: float
    onset: float | None
    first_cue: float | None
    confident: bool
    reason: str = ""

    def describe(self) -> str:
        if not self.confident:
            return f"not confident ({self.reason})"
        return f"speech {self.onset:.2f}s vs first cue {self.first_cue:.2f}s -> {self.offset:+.2f}s"


def vad_available() -> bool:
    """True when the optional neural VAD is importable."""
    try:
        import silero_vad  # noqa: F401
    except ImportError:
        return False
    return True


def _extract_audio(
    stream_info: StreamInfo,
    window_seconds: float,
    dest_dir: Path,
) -> Path | None:
    """Decode the first ``window_seconds`` of audio to 16 kHz mono WAV.

    Returns ``None`` if ffmpeg is missing or fails. Audio-only decoding is not possible for
    HLS, so this still pulls the video segments for the window; the window is the cost
    control.
    """
    out = dest_dir / "probe.wav"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        FFMPEG_EXTENSION_PICKY_FLAG,
        "0",
        "-headers",
        f"Referer: {stream_info.referrer}\r\n",
        "-t",
        str(window_seconds),
        "-i",
        stream_info.video_link,
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(_FFMPEG_SAMPLE_RATE),
        "-c:a",
        "pcm_s16le",
        str(out),
        "-y",
    ]
    try:
        # nosec B603
        proc = subprocess.run(  # nosec B603 # nosemgrep
            cmd,
            capture_output=True,
            check=False,
            timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("ffmpeg unavailable for sub-sync: %s", exc)
        return None
    if proc.returncode != 0:
        logger.debug("ffmpeg failed for sub-sync: %s", proc.stderr[:200])
        return None
    return out if out.is_file() else None


def _read_wav(path: Path):
    """Read a mono 16-bit PCM WAV as float32 in [-1, 1].

    Uses the stdlib ``wave`` module so the core keeps its zero-dependency property; the
    optional dependency is the VAD, not the decoder.
    """
    import array
    import wave

    with wave.open(str(path), "rb") as wf:
        if wf.getsampwidth() != 2 or wf.getnchannels() != 1:
            raise ValueError(f"unexpected WAV layout: {wf.getnchannels()}ch/{wf.getsampwidth() * 8}bit")
        rate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    samples = array.array("h")
    samples.frombytes(raw)
    # int16 -> float32, avoiding a numpy dependency in the core.
    return [s / 32768.0 for s in samples], rate


def _first_speech_onset(wav_path: Path) -> float | None:
    """First speech onset in seconds, or ``None`` when nothing is detected.

    ``min_silence_duration_ms`` is deliberately long: anime narration is broken by short
    breaths, and a short minimum fragments one line into many segments.
    """
    try:
        from silero_vad import get_speech_timestamps, load_silero_vad
    except ImportError:
        return None

    try:
        samples, rate = _read_wav(wav_path)
    except (OSError, ValueError) as exc:
        logger.debug("could not decode probe audio: %s", exc)
        return None
    if not samples:
        return None

    try:
        # get_speech_timestamps indexes the audio buffer as an array. numpy ships as a
        # hard dependency of silero-vad, so this is available whenever the VAD is.
        import numpy as np

        audio = np.asarray(samples, dtype=np.float32)
    except ImportError:
        return None

    try:
        model = load_silero_vad()
        timestamps = get_speech_timestamps(
            audio,
            model,
            sampling_rate=rate,
            threshold=0.5,
            min_speech_duration_ms=200,
            min_silence_duration_ms=300,
            speech_pad_ms=0,
        )
    except Exception as exc:  # noqa: BLE001 - a VAD failure must not break playback
        logger.debug("VAD failed: %s", exc)
        return None

    for segment in timestamps:
        onset = segment["start"] / rate
        if onset >= MIN_PLAUSIBLE_ONSET:
            return onset
    return None


def _first_cue(sub_file: str) -> float | None:
    """Start time of the first cue in seconds.

    Reuses the module's own VTT parser so there is exactly one timestamp parser in the
    project; a second implementation would drift from it.
    """
    text: str | None = None
    if os.path.isfile(sub_file):
        try:
            text = Path(sub_file).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.debug("could not read subtitle file %s: %s", sub_file, exc)
            return None
    elif sub_file.startswith(("http://", "https://")):
        try:
            req = urllib.request.Request(  # nosemgrep
                sub_file,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ani-cli-sync/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310 # nosemgrep
                text = resp.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001 - network failure must not break playback
            logger.debug("could not fetch subtitle %s: %s", sub_file, exc)
            return None

    if not text:
        return None
    cues = parse_vtt(text)
    if not cues:
        return None
    return _timing_to_seconds(cues[0].timing)


def measure_offset(
    stream_info: StreamInfo,
    sub_file: str,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
) -> OffsetResult | None:
    """Measure the subtitle offset for one episode.

    Returns ``None`` when the optional VAD is unavailable or the audio probe failed, so the
    caller can continue unshifted. Otherwise returns a result whose ``confident`` flag
    decides whether the caller may apply it.
    """
    if not vad_available():
        return None

    first_cue = _first_cue(sub_file)
    if first_cue is None:
        return OffsetResult(
            offset=0.0,
            onset=None,
            first_cue=None,
            confident=False,
            reason="no cues in the subtitle file",
        )

    with tempfile.TemporaryDirectory(prefix="ani-subsync-") as td:
        wav = _extract_audio(stream_info, window_seconds, Path(td))
        if wav is None:
            return OffsetResult(
                offset=0.0,
                onset=None,
                first_cue=first_cue,
                confident=False,
                reason="could not decode audio for sub-sync",
            )
        onset = _first_speech_onset(wav)

    if onset is None:
        return OffsetResult(
            offset=0.0,
            onset=None,
            first_cue=first_cue,
            confident=False,
            reason=f"no dialogue detected in the first {window_seconds:.0f}s",
        )

    offset = onset - first_cue
    if abs(offset) > MAX_PLAUSIBLE_OFFSET:
        return OffsetResult(
            offset=offset,
            onset=onset,
            first_cue=first_cue,
            confident=False,
            reason=(
                f"implausible offset ({offset:+.1f}s > {MAX_PLAUSIBLE_OFFSET:.0f}s); "
                "this is likely a different cut, not a timing shift"
            ),
        )

    return OffsetResult(
        offset=offset,
        onset=onset,
        first_cue=first_cue,
        confident=True,
    )


def _dump_result(result: OffsetResult) -> str:
    """JSON summary, for logging or an issue report without re-running the measurement."""
    return json.dumps(
        {
            "offset": round(result.offset, 3),
            "onset": result.onset,
            "first_cue": result.first_cue,
            "confident": result.confident,
            "reason": result.reason,
        },
        sort_keys=True,
    )