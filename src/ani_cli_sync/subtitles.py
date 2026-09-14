"""ani_cli_sync.subtitles: Automated anime subtitle fallback, multi-track inspection,
and dual-language subtitle generation (German + Traditional Chinese with Pinyin).

Features:
  - Stream metadata and subtitle inspection via ani-cli debug mode.
  - Distinction of forced tracks (signs/songs only) vs. full dialogue tracks.
  - Context-aware G2P translation via local LiteLLM proxy (deepseek-v4-flash).
  - Dual-line CJK cue formatting (Line 1: Hanyu Pinyin with tones, Line 2: Traditional Hanzi).
  - Local caching in XDG_CACHE_HOME (~/.cache/ani-cli/subtitles/).
  - MPV command builder supporting primary (--sid=1, bottom) and secondary (--secondary-sid=2, top).
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

FORCED_CUE_THRESHOLD = 50
DEFAULT_API_BASE = os.environ.get("LITELLM_API_BASE", "http://localhost:4000/v1")
DEFAULT_MODEL = os.environ.get("ANI_CLI_SYNC_LLM_MODEL", "deepseek-v4-flash")


@dataclass
class VTTCue:
    identifier: str | None
    timing: str
    lines: list[str] = field(default_factory=list)


@dataclass
class StreamInfo:
    video_link: str
    referrer: str
    subtitles: list[dict[str, Any]] = field(default_factory=list)
    intro_skip: tuple[float, float] | None = None
    outro_skip: tuple[float, float] | None = None


@dataclass
class SubtitlePlan:
    sub_files: list[str] = field(default_factory=list)
    sid: int = 1
    secondary_sid: int = 2


def parse_vtt(vtt_text: str) -> list[VTTCue]:
    """Parse WebVTT content into structured VTTCue objects."""
    cues: list[VTTCue] = []
    # Normalize line endings and strip BOM
    text = vtt_text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\n+", text.strip())

    for block in blocks:
        lines = block.strip().split("\n")
        if not lines or lines[0].startswith("WEBVTT") or lines[0].startswith("NOTE"):
            continue

        timing_idx = -1
        for idx, line in enumerate(lines):
            if "-->" in line:
                timing_idx = idx
                break

        if timing_idx == -1:
            continue

        identifier = lines[timing_idx - 1].strip() if timing_idx > 0 else None
        timing = lines[timing_idx].strip()
        cue_lines = lines[timing_idx + 1 :]
        cues.append(VTTCue(identifier=identifier, timing=timing, lines=cue_lines))

    return cues


def format_vtt(cues: list[VTTCue]) -> str:
    """Format structured cues into standard WebVTT text."""
    out = ["WEBVTT\n"]
    for cue in cues:
        block: list[str] = []
        if cue.identifier:
            block.append(cue.identifier)
        block.append(cue.timing)
        block.extend(cue.lines)
        out.append("\n".join(block))
    return "\n\n".join(out) + "\n"


def count_vtt_cues(vtt_text: str) -> int:
    """Count the number of timestamp lines in a VTT string."""
    return len(re.findall(r"\b\d{2}:\d{2}(?::\d{2})?\.\d{3}\s+-->\s+\d{2}:\d{2}(?::\d{2})?\.\d{3}\b", vtt_text))


def is_forced_track(vtt_content: str, threshold: int = FORCED_CUE_THRESHOLD) -> bool:
    """Determine if a subtitle file is a forced/signs track based on cue density."""
    return count_vtt_cues(vtt_content) < threshold


def get_cached_subtitle_path(
    anime_title: str,
    ep_no: int,
    lang: str,
    base_dir: Path | None = None,
) -> Path:
    """Generate deterministic cache file path for an anime episode subtitle."""
    if base_dir is None:
        cache_base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        base_dir = cache_base / "ani-cli" / "subtitles"
    safe_slug = re.sub(r"[^\w\s-]", "", anime_title.lower()).strip()
    safe_slug = re.sub(r"[-\s]+", "_", safe_slug)
    return base_dir / f"{safe_slug}_ep{ep_no}_{lang}.vtt"


def resolve_stream_info(
    search_arg: str,
    ep_no: int,
    quality: str | None = None,
    dub: bool = False,
) -> StreamInfo | None:
    """Extract stream links, referrer, subtitles, and skip times using ani-cli debug mode."""
    env = os.environ.copy()
    env["ANI_CLI_PLAYER"] = "debug"
    cmd = ["ani-cli", "-e", str(ep_no), search_arg]
    if dub:
        cmd.append("--dub")
    if quality:
        cmd.extend(["-q", quality])

    try:
        res = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
            check=False,
        )
        if res.returncode != 0:
            return None
        output = res.stdout

        video_match = re.search(r"Selected link:\s*\n(https?://[^\s]+)", output)
        if not video_match:
            return None
        video_link = video_match.group(1).strip()

        json_match = re.search(r"JSON:\s*\n(\{.*\})", output, re.DOTALL)
        if not json_match:
            return None
        json_data = json.loads(json_match.group(1).strip())

        subtitles = json_data.get("subtitles", [])
        refr = "https://zokoanime.video/"
        if "download_url" in json_data:
            refr = "https://zokoanime.video/"

        intro_skip = None
        outro_skip = None
        skip_obj = json_data.get("skip", {})
        if "intro" in skip_obj and isinstance(skip_obj["intro"], dict):
            s = skip_obj["intro"].get("start")
            e = skip_obj["intro"].get("end")
            if s is not None and e is not None:
                intro_skip = (float(s), float(e))
        if "outro" in skip_obj and isinstance(skip_obj["outro"], dict):
            s = skip_obj["outro"].get("start")
            e = skip_obj["outro"].get("end")
            if s is not None and e is not None:
                outro_skip = (float(s), float(e))

        return StreamInfo(
            video_link=video_link,
            referrer=refr,
            subtitles=subtitles,
            intro_skip=intro_skip,
            outro_skip=outro_skip,
        )
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as e:
        logger.debug("Failed to resolve stream info: %s", e)
        return None


def fetch_vtt_text(url: str, timeout: int = 30) -> str:
    """Download VTT subtitle text from a URL."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ani-cli-sync/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _translate_single_batch(
    batch_idx: int,
    batch: list[VTTCue],
    endpoint: str,
    model: str,
    sys_prompt: str,
    timeout: int = 90,
    retries: int = 2,
) -> tuple[int, list[VTTCue] | None]:
    """Translate an individual batch of cues with retries."""
    input_vtt = format_vtt(batch)
    req_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": input_vtt},
        ],
        "temperature": 0.1,
    }
    data = json.dumps(req_body).encode("utf-8")

    for attempt in range(retries):
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json", "Authorization": "Bearer dummy"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                content = res_data["choices"][0]["message"]["content"]
                batch_translated = parse_vtt(content)
                if len(batch_translated) == len(batch):
                    return batch_idx, batch_translated

                reconstructed: list[VTTCue] = []
                for idx, orig in enumerate(batch):
                    lines = batch_translated[idx].lines if idx < len(batch_translated) else orig.lines
                    reconstructed.append(VTTCue(identifier=orig.identifier, timing=orig.timing, lines=lines))
                return batch_idx, reconstructed
        except (urllib.error.URLError, json.JSONDecodeError, OSError, KeyError, IndexError) as e:
            logger.warning("Batch %d attempt %d failed: %s", batch_idx, attempt + 1, e)
            if attempt < retries - 1:
                continue
            return batch_idx, None
    return batch_idx, None


def translate_cues_llm(
    cues: list[VTTCue],
    target_lang: str,
    api_base: str = DEFAULT_API_BASE,
    model: str = DEFAULT_MODEL,
    batch_size: int = 25,
    max_workers: int = 5,
) -> list[VTTCue] | None:
    """
    Translate cues via local LiteLLM proxy concurrently across worker threads.
    For 'de': Produces natural German anime dialogue.
    For 'zh-pinyin': Produces 2 lines per cue:
      Line 1: Context-accurate Hanyu Pinyin with tone marks
      Line 2: Traditional Chinese characters (繁體中文)
    """
    if not cues:
        return []

    if target_lang == "de":
        sys_prompt = (
            "You are an expert anime subtitle translator. Translate the following English anime subtitle "
            "cues into natural, authentic German dialogue (Deutsche Synchron-/Untertitel-Konventionen). "
            "Maintain all HTML tags (such as <b>, <i>). For each cue, preserve the exact cue index and "
            "timecode line, and provide the German translation. Output ONLY the translated WEBVTT cues."
        )
    elif target_lang == "zh-pinyin":
        sys_prompt = (
            "You are an expert anime subtitle translator specializing in Traditional Chinese and Hanyu Pinyin. "
            "For each English anime subtitle cue, provide a two-line translation:\n"
            "Line 1: Accurate Hanyu Pinyin with tone marks (e.g. Wǒ míngbái le, Lìmǔlǔ dàrén.)\n"
            "Line 2: Traditional Chinese characters (繁體中文, e.g. 我明白了，利姆路大人。)\n"
            "Maintain all HTML tags (such as <b>, <i>). For each cue, preserve the exact cue index and "
            "timecode line. Output ONLY the translated WEBVTT cues."
        )
    else:
        return None

    endpoint = f"{api_base.rstrip('/')}/chat/completions"
    batches = [cues[i : i + batch_size] for i in range(0, len(cues), batch_size)]
    results: list[list[VTTCue] | None] = [None] * len(batches)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_translate_single_batch, idx, b, endpoint, model, sys_prompt)
            for idx, b in enumerate(batches)
        ]
        for future in as_completed(futures):
            b_idx, b_cues = future.result()
            if b_cues is None:
                logger.warning("Translation failed on batch %d", b_idx)
                return None
            results[b_idx] = b_cues

    all_cues: list[VTTCue] = []
    for r in results:
        if r is None:
            return None
        all_cues.extend(r)

    return all_cues


def prepare_subtitles(
    stream_info: StreamInfo,
    anime_title: str,
    ep_no: int,
    primary_lang: str = "de",
    secondary_lang: str = "zh-pinyin",
    cache_dir: Path | None = None,
    api_base: str = DEFAULT_API_BASE,
    model: str = DEFAULT_MODEL,
) -> SubtitlePlan:
    """
    Prepare and validate subtitle tracks.
    1. Checks local cache for primary and secondary tracks.
    2. Inspects stream tracks: if stream has full primary (cue_count >= 50), uses it.
    3. If primary is missing/forced or secondary is missing, translates using base English track.
    4. Caches all generated files and returns an MPV SubtitlePlan.
    """
    if cache_dir is None:
        cache_base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        cache_dir = cache_base / "ani-cli" / "subtitles"
    cache_dir.mkdir(parents=True, exist_ok=True)

    primary_cache_path = get_cached_subtitle_path(anime_title, ep_no, primary_lang, base_dir=cache_dir)
    secondary_cache_path = get_cached_subtitle_path(anime_title, ep_no, secondary_lang, base_dir=cache_dir)

    primary_file: str | None = str(primary_cache_path) if primary_cache_path.is_file() else None
    secondary_file: str | None = str(secondary_cache_path) if secondary_cache_path.is_file() else None

    # Identify candidate tracks on the stream
    stream_de_url = None
    stream_en_url = None
    for sub in stream_info.subtitles:
        lang = (sub.get("lang") or "").lower()
        label = (sub.get("label") or "").lower()
        src = sub.get("src")
        if not src:
            continue
        if ("de" in lang or "german" in label) and not stream_de_url:
            stream_de_url = src
        if ("en" in lang or "english" in label) and not stream_en_url:
            stream_en_url = src

    # Check if stream primary is full dialogue or forced signs
    if not primary_file and stream_de_url:
        try:
            de_content = fetch_vtt_text(stream_de_url)
            if not is_forced_track(de_content):
                primary_cache_path.write_text(de_content, encoding="utf-8")
                primary_file = str(primary_cache_path)
        except (urllib.error.URLError, OSError) as e:
            logger.debug("Failed to fetch stream German subtitle: %s", e)

    # If primary or secondary still need generation, download base English track
    if (not primary_file or not secondary_file) and stream_en_url:
        try:
            base_content = fetch_vtt_text(stream_en_url)
            base_cues = parse_vtt(base_content)

            if not primary_file:
                translated_de = translate_cues_llm(base_cues, target_lang="de", api_base=api_base, model=model)
                if translated_de:
                    primary_cache_path.write_text(format_vtt(translated_de), encoding="utf-8")
                    primary_file = str(primary_cache_path)

            if not secondary_file:
                translated_zh = translate_cues_llm(base_cues, target_lang="zh-pinyin", api_base=api_base, model=model)
                if translated_zh:
                    secondary_cache_path.write_text(format_vtt(translated_zh), encoding="utf-8")
                    secondary_file = str(secondary_cache_path)
        except (urllib.error.URLError, OSError) as e:
            logger.debug("Failed to translate fallback subtitles: %s", e)

    sub_files: list[str] = []
    sid = 1
    secondary_sid = 2

    if primary_file:
        sub_files.append(primary_file)
    elif stream_de_url:
        sub_files.append(stream_de_url)

    if secondary_file:
        sub_files.append(secondary_file)

    if stream_en_url and stream_en_url not in sub_files:
        sub_files.append(stream_en_url)

    # Adjust track indices if tracks are missing
    if len(sub_files) < 2:
        secondary_sid = 0

    return SubtitlePlan(sub_files=sub_files, sid=sid, secondary_sid=secondary_sid)


def build_mpv_command(
    stream_info: StreamInfo,
    plan: SubtitlePlan,
    anime_title: str,
    ep_no: int,
) -> list[str]:
    """Assemble final MPV playback command with dual subtitles and intro/outro skips."""
    cmd = [
        "mpv",
        f"--referrer={stream_info.referrer}",
    ]
    for sub_path in plan.sub_files:
        cmd.append(f"--sub-file={sub_path}")
    if plan.sid:
        cmd.append(f"--sid={plan.sid}")
    if plan.secondary_sid:
        cmd.append(f"--secondary-sid={plan.secondary_sid}")
    if stream_info.intro_skip:
        start, end = stream_info.intro_skip
        cmd.append(f"--script-opts-append=skip-op_start={start},skip-op_end={end}")
    if stream_info.outro_skip:
        start, end = stream_info.outro_skip
        cmd.append(f"--script-opts-append=skip-ed_start={start},skip-ed_end={end}")

    cmd.append(f"--force-media-title={anime_title} Episode {ep_no}")
    cmd.append(stream_info.video_link)
    return cmd
