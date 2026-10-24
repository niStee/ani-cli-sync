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

import html
import json
import logging
import os
import re
import subprocess  # nosec B404
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ani_cli_sync.menu import prepare_menu_env
from ani_cli_sync.metadata import (
    CharacterProfile,
    SeriesMetadata,
    extract_active_characters,
    resolve_series_metadata,
)

logger = logging.getLogger(__name__)

FORCED_CUE_THRESHOLD = 50
DEFAULT_API_BASE = os.environ.get("LITELLM_API_BASE", "http://localhost:4000/v1")
# Every member must be a handle the local LiteLLM gateway accepts, i.e. one
# registered in ai-infra's model-governance.json. The gateway fails closed on an
# undeclared handle, so a dead member here is a failover that walks into HTTP
# 400 exactly when the cascade is needed. See AGENTS.md, "Model Governance
# Contract", and the vendored registry in ani_cli_sync.model_registry.
DEFAULT_FALLBACK_MODELS: tuple[str, ...] = (
    "minimax-m3.1-flash",
    "gemini-3.1-flash-lite",
)
DEFAULT_MODEL = os.environ.get("ANI_CLI_SYNC_LLM_MODEL", DEFAULT_FALLBACK_MODELS[0])


def get_candidate_models(model: str | None = None) -> list[str]:
    """Resolve candidate LLM translation models in priority order."""
    if model:
        return [model]
    env_models = os.environ.get("ANI_CLI_SYNC_LLM_MODELS")
    if env_models:
        models = [m.strip() for m in env_models.split(",") if m.strip()]
        if models:
            return models
    env_model = os.environ.get("ANI_CLI_SYNC_LLM_MODEL")
    if env_model:
        return [env_model.strip()]
    return list(DEFAULT_FALLBACK_MODELS)


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


_RUBY_RT_RE = re.compile(r"<rt\b[^>]*>.*?</rt>", re.IGNORECASE | re.DOTALL)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG_RE = re.compile(
    r"</?(?:[a-zA-Z]+(?:\.[a-zA-Z0-9_-]+)*|[biu]|v(?:\s+[^>]*)?|c(?:\.[a-zA-Z0-9_-]+)*|span|div|p|ruby|rt)(?:\s+[^>]*)?>",
    re.IGNORECASE,
)
_UNICODE_ARTIFACTS_RE = re.compile(r"[\u200B-\u200D\u200E\u200F\uFEFF]")


def sanitize_cue_text(text: str) -> str:
    """Sanitize raw WebVTT cue text by stripping tags, entities, and unicode artifacts."""
    if not text:
        return ""
    # 1. Normalize line break tags to spaces before stripping tags to avoid word concatenation
    text = _BR_RE.sub(" ", text)
    # 2. Strip ruby reading annotations (<rt>...</rt>) first before stripping outer tags
    text = _RUBY_RT_RE.sub("", text)
    # 3. Strip WebVTT formatting/styling/voice tags
    text = _TAG_RE.sub("", text)
    # 4. Decode HTML entities (&amp;, &quot;, &#39;, etc.) and normalize non-breaking spaces
    text = html.unescape(text).replace("\xa0", " ")
    # 5. Remove zero-width and directional control characters
    text = _UNICODE_ARTIFACTS_RE.sub("", text)
    return text.strip()


def parse_vtt(vtt_text: str, sanitize: bool = True) -> list[VTTCue]:
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
        raw_lines = lines[timing_idx + 1 :]
        if sanitize:
            sanitized_lines = [sanitize_cue_text(line) for line in raw_lines]
            cue_lines = [line for line in sanitized_lines if line]
            if not cue_lines:
                continue
        else:
            cue_lines = raw_lines
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
        for line in cue.lines:
            # Ensure stray <br> tags are split into separate lines to prevent libass bold parsing bug
            sub_lines = _BR_RE.split(line)
            for sub in sub_lines:
                cleaned_sub = sub.strip()
                if cleaned_sub:
                    block.append(cleaned_sub)
        out.append("\n".join(block))
    return "\n\n".join(out) + "\n"


def count_vtt_cues(vtt_text: str) -> int:
    """Count the number of timestamp lines in a VTT string."""
    return len(
        re.findall(
            r"\b\d{2}:\d{2}(?::\d{2})?\.\d{3}\s+-->\s+\d{2}:\d{2}(?::\d{2})?\.\d{3}\b",
            vtt_text,
        )
    )


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
    uncensored: bool | None = None,
) -> StreamInfo | None:
    """Extract stream links, referrer, subtitles, and skip times using ani-cli debug mode."""
    if uncensored is None:
        uncensored = os.environ.get("ANI_CLI_SYNC_UNCENSORED", "1").lower() in (
            "1",
            "true",
            "yes",
        )

    env = prepare_menu_env(target_title=search_arg, uncensored=uncensored)
    env["ANI_CLI_PLAYER"] = "debug"
    cmd = ["ani-cli", "-e", str(ep_no), search_arg]
    if dub:
        cmd.append("--dub")
    if quality:
        cmd.extend(["-q", quality])

    try:
        # nosec B603
        # nosemgrep
        res = subprocess.run(  # nosec B603 # nosemgrep
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

        subtitles = json_data.get("subtitles") or []
        refr = "https://zokoanime.video/"
        if "download_url" in json_data:
            refr = "https://zokoanime.video/"

        intro_skip = None
        outro_skip = None
        skip_obj = json_data.get("skip")
        if isinstance(skip_obj, dict):
            intro = skip_obj.get("intro")
            if isinstance(intro, dict):
                s = intro.get("start")
                e = intro.get("end")
                if s is not None and e is not None:
                    try:
                        intro_skip = (float(s), float(e))
                    except (ValueError, TypeError):
                        pass
            outro = skip_obj.get("outro")
            if isinstance(outro, dict):
                s = outro.get("start")
                e = outro.get("end")
                if s is not None and e is not None:
                    try:
                        outro_skip = (float(s), float(e))
                    except (ValueError, TypeError):
                        pass

        return StreamInfo(
            video_link=video_link,
            referrer=refr,
            subtitles=subtitles,
            intro_skip=intro_skip,
            outro_skip=outro_skip,
        )
    except Exception as e:  # noqa: BLE001 - stream resolution must not crash caller
        logger.debug("Failed to resolve stream info: %s", e)
        return None


def fetch_vtt_text(url: str, timeout: int = 30, referrer: str | None = None) -> str:
    """Download VTT subtitle text from a URL.

    ``referrer`` is required in practice for CDN-hosted tracks: hls.dramahot.top answers
    HTTP 403 to a subtitle URL carrying only a User-Agent and 200 once the stream's Referer
    is present. mpv already receives it via --referrer, so playback shows subtitles that this
    function could not fetch, and the translation pipeline silently produced nothing.
    """
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Unsupported or insecure URL: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ani-cli-sync/1.0"
    }
    if referrer:
        headers["Referer"] = referrer
    # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
    req = urllib.request.Request(url, headers=headers)
    # nosec B310
    # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 # nosemgrep
        return resp.read().decode("utf-8", errors="replace")


BUILTIN_SERIES_GLOSSARIES: dict[str, dict[str, dict[str, str]]] = {
    "attack on titan": {
        "de": {
            "ODM gear": "3D-Manöver-Apparat",
            "Omni-Directional Mobility gear": "3D-Manöver-Apparat",
            "Survey Corps": "der Aufklärungstrupp",
            "Scout Regiment": "der Aufklärungstrupp",
            "Scouts": "die Aufklärungstruppen",
            "Garrison": "die Mauergarnison",
            "Garrison Regiment": "die Mauergarnison",
            "Military Police": "die Militärpolizei",
            "Military Police Brigade": "die Militärpolizei",
            "Colossal Titan": "der Kolossale Titan",
            "Armored Titan": "der Gepanzerte Titan",
            "Beast Titan": "der Tiertitan",
            "Attack Titan": "der Attackierende Titan",
            "Founding Titan": "der Urvater-Titan",
            "Female Titan": "der Weibliche Titan",
            "Jaw Titan": "der Kiefer-Titan",
            "Cart Titan": "der Karren-Titan",
            "War Hammer Titan": "der Kriegshammer-Titan",
            "Wall Maria": "die Mauer Maria",
            "Wall Rose": "die Mauer Rose",
            "Wall Sina": "die Mauer Sina",
            "Eldia": "Eldia",
            "Eldian": "Eldier",
            "Marley": "Marley",
            "Marleyan": "Marleyer",
            "Commander": "Kommandant",
            "Captain": "Hauptgefreiter",
        }
    },
}
BUILTIN_SERIES_ALIASES: dict[str, str] = {
    "shingeki no kyojin": "attack on titan",
    "snk": "attack on titan",
    "aot": "attack on titan",
    "tensei shitara slime datta ken": "that time i got reincarnated as a slime",
    "tensura": "that time i got reincarnated as a slime",
    "frieren": "sousou no frieren",
    "beyond journey's end": "sousou no frieren",
    "jjk": "jujutsu kaisen",
}


def resolve_canonical_series_key(anime_title: str) -> str:
    """Normalize anime title using built-in aliases (e.g. Romaji to English canonical)."""
    title_lower = anime_title.lower()
    for alias, canonical in BUILTIN_SERIES_ALIASES.items():
        if alias in title_lower:
            return canonical
    return title_lower


def get_series_glossary(anime_title: str | None, target_lang: str) -> dict[str, str]:
    """Resolve terminology glossary for an anime series and target language."""
    if not anime_title:
        return {}

    title_lower = anime_title.lower()
    canonical_key = resolve_canonical_series_key(anime_title)
    resolved: dict[str, str] = {}

    # 1. Match built-in series (checking both raw title and canonical alias)
    for series_key, lang_map in BUILTIN_SERIES_GLOSSARIES.items():
        if (
            series_key in title_lower
            or title_lower in series_key
            or series_key in canonical_key
            or canonical_key in series_key
        ):
            resolved.update(lang_map.get(target_lang, {}))
            break

    # 2. Check user config file ~/.config/ani-cli/glossary.json (XDG_CONFIG_HOME)
    config_base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    user_glossary_file = config_base / "ani-cli" / "glossary.json"
    if user_glossary_file.is_file():
        try:
            data = json.loads(user_glossary_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for series_key, lang_map in data.items():
                    if isinstance(lang_map, dict) and (
                        series_key.lower() in title_lower
                        or title_lower in series_key.lower()
                    ):
                        resolved.update(lang_map.get(target_lang, {}))
                        break
        except (OSError, json.JSONDecodeError) as exc:
            logger.debug(
                "Failed to read user glossary from %s: %s", user_glossary_file, exc
            )

    return resolved


def extract_active_glossary(
    cues: list[VTTCue], glossary: dict[str, str]
) -> dict[str, str]:
    """Filter glossary to only include terms present in the current cue batch."""
    if not glossary or not cues:
        return {}

    batch_text = " ".join(" ".join(c.lines) for c in cues)
    active: dict[str, str] = {}
    for term, translation in glossary.items():
        pattern = r"\b" + re.escape(term) + r"\b"
        if re.search(pattern, batch_text, re.IGNORECASE):
            active[term] = translation

    return active


def _build_translation_payload(
    model: str,
    sys_prompt: str,
    cues: list[VTTCue],
    anime_title: str | None = None,
    active_glossary: dict[str, str] | None = None,
    active_characters: list[CharacterProfile] | None = None,
) -> bytes:
    """Build the JSON request body for a translation call.

    The payload is text-only: timestamps and identifiers are deliberately
    stripped so the model can never echo a shifted timing, and re-attachment
    happens client-side from the original batch.
    """
    prompt_parts = [sys_prompt]
    if anime_title:
        prompt_parts.append(f'Anime series: "{anime_title}".')
    if active_characters:
        char_cards = ", ".join(c.format_card() for c in active_characters)
        prompt_parts.append(
            f"Key Character Profiles (grammatical reference for pronouns/gender): {char_cards}."
        )
    if active_glossary:
        glossary_items = ", ".join(
            f'"{k}": "{v}"' for k, v in sorted(active_glossary.items())
        )
        prompt_parts.append(
            f"Active Terminology Glossary: {{{glossary_items}}}.\n"
            "Strictly adhere to this glossary, inflecting grammatically with correct case, gender, and articles as required for natural dialogue."
        )
    effective_prompt = "\n\n".join(prompt_parts)

    numbered = [f"{i}: {chr(10).join(cue.lines)}" for i, cue in enumerate(cues)]
    user_content = "\n".join(numbered)
    req_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": effective_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.1,
    }
    return json.dumps(req_body).encode("utf-8")


def _parse_translation_response(content: str) -> list[list[str]] | None:
    """Parse the model's JSON response into per-cue text lines.

    Accepts either a JSON array of strings or a key-indexed JSON object
    mapping contiguous string indices ("0", "1", ...) to strings.
    Strips an optional ```json ... ``` code fence. Returns None on any
    structural failure so the caller can decide what to do (retry, bisect,
    fall back to English).
    """
    text = content.strip()
    if text.startswith("```"):
        # Drop the opening fence (```json or ```) and matching closing fence.
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    if isinstance(data, dict):
        try:
            int_keys = {int(k): k for k in data}
        except (ValueError, TypeError):
            return None
        n = len(data)
        if set(int_keys) != set(range(n)):
            return None
        raw_entries = [data[int_keys[i]] for i in range(n)]
    elif isinstance(data, list):
        raw_entries = data
    else:
        return None

    lines_per_cue: list[list[str]] = []
    for entry in raw_entries:
        if isinstance(entry, str):
            # Replace any HTML line-break tags with real newlines so libass does not interpret <br> as an open <b> tag
            entry = _BR_RE.sub("\n", entry)
            cleaned = [re.sub(r"^\d+:\s*", "", line) for line in entry.split("\n")]
            lines_per_cue.append([line.strip() for line in cleaned if line.strip()])
        else:
            return None
    return lines_per_cue


def _has_hallucinated_duplicates(batch: list[VTTCue], parsed: list[list[str]]) -> bool:
    """Detect adjacent duplicate translations when original source cues differed.

    When an LLM duplicates a cue and drops another, overall batch length remains equal
    to the source length, but the duplicate shifts all subsequent cues. If the source cues
    genuinely repeated identical lines, the duplicate is legitimate and permitted.
    """
    if len(batch) != len(parsed):
        return True
    for i in range(1, len(batch)):
        curr_trans = "\n".join(parsed[i]).strip()
        prev_trans = "\n".join(parsed[i - 1]).strip()
        curr_orig = "\n".join(batch[i].lines).strip()
        prev_orig = "\n".join(batch[i - 1].lines).strip()
        if curr_trans and curr_trans == prev_trans and curr_orig != prev_orig:
            return True
    return False


def _has_untranslated_echo(
    batch: list[VTTCue],
    parsed: list[list[str]],
    target_lang: str = "de",
) -> bool:
    """Detect if any cue was padded with an untranslated multi-word English source line."""
    if target_lang == "en" or len(batch) != len(parsed):
        return False
    for orig, trans in zip(batch, parsed):
        orig_text = " ".join(orig.lines).strip()
        trans_text = " ".join(trans).strip()
        if len(orig_text.split()) >= 3 and orig_text.lower() == trans_text.lower():
            return True
    return False


def _extract_anchors(lines: list[str]) -> set[str]:
    """Extract candidate entity anchors (proper nouns / capitalized names) from cue lines."""
    anchors = set()
    for line in lines:
        clean = re.sub(r"<[^>]+>", "", line)
        words = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", clean)
        for w in words:
            anchors.add(w.lower())
    return anchors


def _has_anchor_phase_shift(batch: list[VTTCue], parsed: list[list[str]]) -> bool:
    """Detect if a distinctive entity anchor jumped to an adjacent neighbor cue."""
    if len(batch) != len(parsed):
        return True
    n = len(batch)
    for i in range(n):
        orig_anchors = _extract_anchors(batch[i].lines)
        if not orig_anchors:
            continue
        trans_anchors = _extract_anchors(parsed[i])

        if i > 0:
            prev_orig = _extract_anchors(batch[i - 1].lines)
            prev_trans = _extract_anchors(parsed[i - 1])
            for a in orig_anchors:
                if a not in prev_orig and a in prev_trans and a not in trans_anchors:
                    return True

        if i < n - 1:
            next_orig = _extract_anchors(batch[i + 1].lines)
            next_trans = _extract_anchors(parsed[i + 1])
            for a in orig_anchors:
                if a not in next_orig and a in next_trans and a not in trans_anchors:
                    return True
    return False


def _translate_single_batch(
    batch_idx: int,
    batch: list[VTTCue],
    endpoint: str,
    model: str,
    sys_prompt: str,
    timeout: int = 45,
    retries: int = 1,
    anime_title: str | None = None,
    series_glossary: dict[str, str] | None = None,
    characters: list[CharacterProfile] | None = None,
) -> tuple[int, list[VTTCue] | None]:
    """Translate an individual batch of cues with retries.

    Text-only payload (no timestamps); the response is a JSON array or object
    in input order. Mismatches trigger a bisect into smaller sub-batches
    until the mismatched cue can be isolated; a single cue that still misaligns
    after the retry budget falls back to its original English lines so timings
    are never shifted.
    """
    parsed_ep = urllib.parse.urlsplit(endpoint)
    if parsed_ep.scheme not in ("http", "https") or not parsed_ep.netloc:
        raise ValueError(f"Unsupported or insecure endpoint: {endpoint}")

    target_lang = "de" if ("German" in sys_prompt or "de" in sys_prompt) else "other"
    active_glossary = (
        extract_active_glossary(batch, series_glossary) if series_glossary else None
    )
    active_chars = extract_active_characters(batch, characters) if characters else None
    data = _build_translation_payload(
        model,
        sys_prompt,
        batch,
        anime_title=anime_title,
        active_glossary=active_glossary,
        active_characters=active_chars,
    )

    for attempt in range(retries):
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer dummy",
            },
        )
        try:
            # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 # nosemgrep
                res_data = json.loads(resp.read().decode("utf-8"))
                content = res_data["choices"][0]["message"]["content"]
                parsed = _parse_translation_response(content)
                if (
                    parsed is not None
                    and len(parsed) == len(batch)
                    and not _has_hallucinated_duplicates(batch, parsed)
                    and not _has_untranslated_echo(
                        batch, parsed, target_lang=target_lang
                    )
                    and not _has_anchor_phase_shift(batch, parsed)
                ):
                    return batch_idx, [
                        VTTCue(
                            identifier=orig.identifier,
                            timing=orig.timing,
                            lines=translated,
                        )
                        for orig, translated in zip(batch, parsed)
                    ]
                # Length mismatch, hallucinated duplicate, or unparseable: bisect to
                # isolate the cue(s) the model corrupted/dropped. A leaf of size 1-2
                # that still misaligns after exhausting the retry budget falls back to
                # original text.
                if len(batch) <= 2:
                    logger.warning(
                        "Batch %d cue(s) %s..%s mismatched after retry; falling back to original",
                        batch_idx,
                        0,
                        len(batch) - 1,
                    )
                    return batch_idx, [
                        VTTCue(
                            identifier=orig.identifier,
                            timing=orig.timing,
                            lines=list(orig.lines),
                        )
                        for orig in batch
                    ]
                mid = len(batch) // 2
                logger.debug(
                    "Batch %d length mismatch or duplicate; bisecting at %d",
                    batch_idx,
                    mid,
                )
                _, left = _translate_single_batch(
                    batch_idx,
                    batch[:mid],
                    endpoint,
                    model,
                    sys_prompt,
                    timeout=timeout,
                    retries=retries,
                    anime_title=anime_title,
                    series_glossary=series_glossary,
                    characters=characters,
                )
                if left is None:
                    return batch_idx, None
                _, right = _translate_single_batch(
                    batch_idx,
                    batch[mid:],
                    endpoint,
                    model,
                    sys_prompt,
                    timeout=timeout,
                    retries=retries,
                    anime_title=anime_title,
                    series_glossary=series_glossary,
                    characters=characters,
                )
                if right is None:
                    return batch_idx, None
                return batch_idx, left + right
        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.warning(
                    "Batch %d: Model %s quota exhausted (429). Fast-failing to next candidate...",
                    batch_idx,
                    model,
                )
                return batch_idx, None
            logger.warning(
                "Batch %d attempt %d failed: HTTP %s", batch_idx, attempt + 1, e
            )
            if attempt < retries - 1:
                if e.code in (500, 502, 503, 504):
                    time.sleep(min(1.0 * (1.5**attempt), 5.0))
                continue
            return batch_idx, None
        except (
            urllib.error.URLError,
            json.JSONDecodeError,
            OSError,
            KeyError,
            IndexError,
        ) as e:
            logger.warning("Batch %d attempt %d failed: %s", batch_idx, attempt + 1, e)
            if attempt < retries - 1:
                time.sleep(min(1.0 * (1.5**attempt), 5.0))
                continue
            return batch_idx, None
    return batch_idx, None


def translate_cues_llm(
    cues: list[VTTCue],
    target_lang: str,
    api_base: str = DEFAULT_API_BASE,
    model: str | None = None,
    batch_size: int = 50,
    max_workers: int = 5,
    anime_title: str | None = None,
    series_metadata: SeriesMetadata | None = None,
    characters: list[CharacterProfile] | None = None,
) -> list[VTTCue] | None:
    """
    Translate cues via local LiteLLM proxy concurrently across worker threads with tiered failover.
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
            "Use standard newlines for line breaks (NEVER output <br> tags). "
            "Avoid literal cleft sentences with awkward gender guessing (e.g. translate 'I was the one who was wrong' "
            "naturally as 'Ich lag falsch' or 'Der Fehler lag bei mir', NOT 'Ich war derjenige/diejenige'). "
            "When grammatical gender is unavoidable, strictly adhere to the provided Character Profiles. "
            "For ungendered English roles, titles, or professions (e.g. 'a civilian', 'a soldier', 'a merchant', 'a doctor') "
            "without an explicit female referent in the scene context or character roster, use the standard generic masculine "
            "(e.g. 'einen Zivilisten', 'einen Soldaten', NOT 'eine Zivilistin'). Never use typographic gender markers (no '*', ':', '_') or double naming. "
            "For German compound nouns, grammatical gender and articles are strictly determined by the final element "
            "(e.g. 'der Aufklärungstrupp' because 'der Trupp', NOT 'das Aufklärungstrupp'). "
            "Maintain all HTML formatting tags (such as <b>, <i>). The user message is a numbered list of cues "
            "in the form 'i: text'. Return ONLY a JSON object mapping each cue index to its translation "
            '(e.g. {"0": "...", "1": "..."}). Every requested index must be present, with no '
            "missing indices, no commentary, and no markdown fences."
        )
    elif target_lang == "zh-pinyin":
        sys_prompt = (
            "You are an expert anime subtitle translator specializing in Traditional Chinese and Hanyu Pinyin. "
            "For each English anime subtitle cue, provide a two-line translation:\n"
            "Line 1: Accurate Hanyu Pinyin with tone marks (e.g. Wǒ míngbái le, Lìmǔlǔ dàrén.)\n"
            "Line 2: Traditional Chinese characters (繁體中文, e.g. 我明白了，利姆路大人。)\n"
            "Maintain all HTML tags (such as <b>, <i>). The user message is a numbered list of cues "
            "in the form 'i: text'. Return ONLY a JSON object mapping each cue index to its two-line translation "
            'joined with a newline (e.g. {"0": "...", "1": "..."}). Every requested index must be present, '
            "with no missing indices, no commentary, and no markdown fences."
        )
    else:
        return None

    if series_metadata is None and anime_title:
        series_metadata = resolve_series_metadata(title=anime_title)

    resolved_characters = characters
    if resolved_characters is None and series_metadata:
        resolved_characters = series_metadata.characters

    series_glossary = get_series_glossary(anime_title, target_lang)
    endpoint = f"{api_base.rstrip('/')}/chat/completions"
    batches = [cues[i : i + batch_size] for i in range(0, len(cues), batch_size)]
    candidates = get_candidate_models(model)

    for model_name in candidates:
        results: list[list[VTTCue] | None] = [None] * len(batches)

        # Not a `with` block on purpose: returning from inside one waits for every
        # in-flight future at __exit__ (shutdown(wait=True)), which is how a known
        # failure used to cost the full timeout x retries of the slowest sibling.
        executor = ThreadPoolExecutor(max_workers=max_workers)
        futures = [
            executor.submit(
                _translate_single_batch,
                idx,
                b,
                endpoint,
                model_name,
                sys_prompt,
                anime_title=anime_title,
                series_glossary=series_glossary,
                characters=resolved_characters,
            )
            for idx, b in enumerate(batches)
        ]
        failed = False
        try:
            for future in as_completed(futures):
                b_idx, b_cues = future.result()
                if b_cues is None:
                    logger.warning(
                        "Translation failed on batch %d with model %s",
                        b_idx,
                        model_name,
                    )
                    failed = True
                    break
                results[b_idx] = b_cues
        finally:
            # On abort: drop queued batches and stop waiting. Siblings already running
            # finish on their own, bounded by the per-batch timeout.
            executor.shutdown(wait=not failed, cancel_futures=failed)

        if not failed and all(r is not None for r in results):
            all_cues: list[VTTCue] = []
            for r in results:
                if r is not None:
                    all_cues.extend(r)
            return all_cues

        if model_name != candidates[-1]:
            logger.warning(
                "Model %s failed or exhausted; advancing to next candidate in cascade...",
                model_name,
            )

    logger.warning("All candidate models exhausted (%s)", candidates)
    return None


def prepare_subtitles(
    stream_info: StreamInfo,
    anime_title: str,
    ep_no: int,
    primary_lang: str = "de",
    secondary_lang: str | None = None,
    cache_dir: Path | None = None,
    api_base: str = DEFAULT_API_BASE,
    model: str | None = None,
    series_metadata: SeriesMetadata | None = None,
) -> SubtitlePlan:
    """
    Prepare and validate subtitle tracks.
    1. Checks local cache for primary and (if requested) secondary tracks.
    2. Inspects stream tracks: if stream has full primary (cue_count >= 50), uses it.
    3. If primary is missing/forced, translates using base English track.
    4. If secondary_lang is explicitly requested and missing, translates on demand.
    5. If secondary_lang is None and stream has English, attaches English as secondary track
       for on-demand toggle (e.g. mpv Ctrl+j) with secondary_sid=0 (inactive on startup).
    6. Caches all generated files and returns an MPV SubtitlePlan.
    """
    if cache_dir is None:
        cache_base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        cache_dir = cache_base / "ani-cli" / "subtitles"
    cache_dir.mkdir(parents=True, exist_ok=True)

    primary_cache_path = get_cached_subtitle_path(
        anime_title, ep_no, primary_lang, base_dir=cache_dir
    )
    secondary_cache_path = (
        get_cached_subtitle_path(anime_title, ep_no, secondary_lang, base_dir=cache_dir)
        if secondary_lang
        else None
    )

    primary_file: str | None = (
        str(primary_cache_path) if primary_cache_path.is_file() else None
    )
    secondary_file: str | None = (
        str(secondary_cache_path)
        if (secondary_cache_path and secondary_cache_path.is_file())
        else None
    )

    # Identify candidate tracks on the stream.
    # The provider currently stamps lang="en" on every track regardless of its real
    # language, so `lang` must never decide on its own: matching it alone binds the
    # first track in the payload, which on some releases is Arabic. Prefer `label`
    # (which is accurate) and consult `lang` only for tracks with no usable label.
    stream_de_url = None
    stream_en_url = None
    for sub in stream_info.subtitles:
        label = (sub.get("label") or "").lower()
        src = sub.get("src")
        if not src:
            continue
        if not stream_de_url and ("german" in label or "deutsch" in label):
            stream_de_url = src
        if not stream_en_url and "english" in label:
            stream_en_url = src

    # Fall back to `lang` only for tracks whose label carries no language name.
    if not stream_de_url:
        for sub in stream_info.subtitles:
            if (sub.get("lang") or "").lower() == "de" and sub.get("src"):
                stream_de_url = sub["src"]
                break
    if not stream_en_url:
        for sub in stream_info.subtitles:
            if (sub.get("lang") or "").lower() == "en" and sub.get("src"):
                stream_en_url = sub["src"]
                break

    # Check if stream primary is full dialogue or forced signs
    if not primary_file and stream_de_url:
        try:
            de_content = fetch_vtt_text(stream_de_url, referrer=stream_info.referrer)
            if not is_forced_track(de_content):
                primary_cache_path.write_text(de_content, encoding="utf-8")
                primary_file = str(primary_cache_path)
        except (urllib.error.URLError, OSError) as e:
            logger.debug("Failed to fetch stream German subtitle: %s", e)

    # If primary or on-demand secondary still need generation, download base English track
    needs_primary_translation = not primary_file
    needs_secondary_translation = bool(secondary_lang and not secondary_file)

    if (needs_primary_translation or needs_secondary_translation) and stream_en_url:
        try:
            base_content = fetch_vtt_text(stream_en_url, referrer=stream_info.referrer)
            base_cues = parse_vtt(base_content)

            if needs_primary_translation:
                translated_de = translate_cues_llm(
                    base_cues,
                    target_lang="de",
                    api_base=api_base,
                    model=model,
                    anime_title=anime_title,
                    series_metadata=series_metadata,
                )
                if translated_de:
                    primary_cache_path.write_text(
                        format_vtt(translated_de), encoding="utf-8"
                    )
                    primary_file = str(primary_cache_path)

            if needs_secondary_translation and secondary_cache_path and secondary_lang:
                translated_sec = translate_cues_llm(
                    base_cues,
                    target_lang=secondary_lang,
                    api_base=api_base,
                    model=model,
                    anime_title=anime_title,
                    series_metadata=series_metadata,
                )
                if translated_sec:
                    secondary_cache_path.write_text(
                        format_vtt(translated_sec), encoding="utf-8"
                    )
                    secondary_file = str(secondary_cache_path)
        except (urllib.error.URLError, OSError) as e:
            logger.debug("Failed to translate fallback subtitles: %s", e)

    sub_files: list[str] = []
    sid = 1
    secondary_sid = 2 if secondary_lang is not None else 0

    if primary_file:
        sub_files.append(primary_file)
    elif stream_de_url:
        sub_files.append(stream_de_url)

    if secondary_file:
        sub_files.append(secondary_file)
    elif stream_en_url and stream_en_url not in sub_files:
        sub_files.append(stream_en_url)

    # Adjust track indices if tracks are missing
    if len(sub_files) < 2:
        secondary_sid = 0

    return SubtitlePlan(sub_files=sub_files, sid=sid, secondary_sid=secondary_sid)


def prefetch_next_episode(
    anime_title: str,
    ep_no: int,
    primary_lang: str = "de",
    secondary_lang: str | None = None,
    quality: str | None = None,
    dub: bool = False,
    api_base: str = DEFAULT_API_BASE,
    model: str | None = None,
    uncensored: bool | None = None,
) -> None:
    """Pre-fetch and pre-translate the next episode's subtitles in the background."""
    if uncensored is None:
        uncensored = os.environ.get("ANI_CLI_SYNC_UNCENSORED", "1").lower() in (
            "1",
            "true",
            "yes",
        )
    try:
        next_info = resolve_stream_info(
            anime_title, ep_no, quality=quality, dub=dub, uncensored=uncensored
        )
        if next_info:
            prepare_subtitles(
                next_info,
                anime_title,
                ep_no,
                primary_lang=primary_lang,
                secondary_lang=secondary_lang,
                api_base=api_base,
                model=model,
            )
            logger.info("Prefetched subtitles for '%s' Ep %d", anime_title, ep_no)
    except Exception as e:  # noqa: BLE001 - background prefetch must not crash playback
        logger.debug(
            "Prefetch for '%s' Ep %d encountered an issue: %s", anime_title, ep_no, e
        )


def build_mpv_command(
    stream_info: StreamInfo,
    plan: SubtitlePlan,
    anime_title: str,
    ep_no: int,
    sub_delay: float = 0.0,
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
    if sub_delay:
        cmd.append(f"--sub-delay={sub_delay}")
    if stream_info.intro_skip:
        start, end = stream_info.intro_skip
        cmd.append(f"--script-opts-append=skip-op_start={start}")
        cmd.append(f"--script-opts-append=skip-op_end={end}")
    if stream_info.outro_skip:
        start, end = stream_info.outro_skip
        cmd.append(f"--script-opts-append=skip-ed_start={start}")
        cmd.append(f"--script-opts-append=skip-ed_end={end}")

    cmd.append(f"--force-media-title={anime_title} Episode {ep_no}")
    cmd.append(stream_info.video_link)
    return cmd
