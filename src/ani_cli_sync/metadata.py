"""Dynamic anime series metadata and character entity resolution.

Retrieves and caches media information (canonical titles, synopsis, and character
gender profiles) from AniList GraphQL without external runtime dependencies.
Provides scene-level active entity extraction to condition LLM subtitle translation
with minimal prompt pollution.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ani_cli_sync.subtitles import VTTCue

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://graphql.anilist.co"

SERIES_METADATA_QUERY = """
query ($search: String, $id: Int) {
  Media(search: $search, id: $id, type: ANIME) {
    id
    title {
      romaji
      english
      native
    }
    description(asHtml: false)
    characters(sort: ROLE, perPage: 25) {
      edges {
        role
        node {
          name {
            userPreferred
            alternative
          }
          gender
        }
      }
    }
  }
}
"""


@dataclass(frozen=True)
class CharacterProfile:
    """Character identity and grammatical reference card for subtitle localization."""

    name: str
    gender: str | None = None
    role: str = "SUPPORTING"
    aliases: tuple[str, ...] = field(default_factory=tuple)

    def format_card(self) -> str:
        """Render prompt card for LLM system context."""
        g = self.gender if self.gender else "unspecified"
        return f"{self.name} ({g})"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "gender": self.gender,
            "role": self.role,
            "aliases": list(self.aliases),
        }

    @classmethod
    def from_dict(cls, data: dict) -> CharacterProfile:
        return cls(
            name=data["name"],
            gender=data.get("gender"),
            role=data.get("role", "SUPPORTING"),
            aliases=tuple(data.get("aliases", ())),
        )


@dataclass
class SeriesMetadata:
    """Structured series metadata for translation conditioning."""

    media_id: int
    title_romaji: str
    title_english: str | None = None
    synopsis: str | None = None
    characters: list[CharacterProfile] = field(default_factory=list)

    @property
    def canonical_title(self) -> str:
        return self.title_english or self.title_romaji

    def to_dict(self) -> dict:
        return {
            "media_id": self.media_id,
            "title_romaji": self.title_romaji,
            "title_english": self.title_english,
            "synopsis": self.synopsis,
            "characters": [c.to_dict() for c in self.characters],
        }

    @classmethod
    def from_dict(cls, data: dict) -> SeriesMetadata:
        chars = [CharacterProfile.from_dict(c) for c in data.get("characters", [])]
        return cls(
            media_id=data["media_id"],
            title_romaji=data["title_romaji"],
            title_english=data.get("title_english"),
            synopsis=data.get("synopsis"),
            characters=chars,
        )


def extract_active_characters(
    cues: list[VTTCue],
    characters: list[CharacterProfile],
    max_chars: int = 8,
) -> list[CharacterProfile]:
    """Return characters actively mentioned or addressed in this cue batch.

    Deduplicates while preserving prominence (character list order). Matches on
    word boundaries for canonical names and aliases (minimum token length 3).
    """
    if not characters or not cues:
        return []

    combined_text = " ".join(" ".join(c.lines) for c in cues).lower()
    active: list[CharacterProfile] = []

    for char in characters:
        tokens = [char.name] + list(char.aliases)
        matched = False
        for token in tokens:
            cleaned = token.strip()
            if len(cleaned) < 3:
                continue
            pattern = rf"\b{re.escape(cleaned.lower())}\b"
            if re.search(pattern, combined_text):
                matched = True
                break

        if matched:
            active.append(char)
            if len(active) >= max_chars:
                break

    return active


def get_metadata_cache_dir() -> Path:
    """Return the base cache directory for anime series metadata."""
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg_cache) if xdg_cache else Path.home() / ".cache"
    cache_dir = base / "ani-cli" / "metadata"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _execute_graphql(
    query: str, variables: dict | None = None, timeout: int = 10
) -> dict:
    """Execute standard library GraphQL HTTP POST request."""
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ani-cli-sync/1.0",
        },
        method="POST",
    )
    # nosec B310 - standard library safe URL endpoint
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosemgrep
        return json.loads(resp.read().decode("utf-8"))


def _parse_media_to_metadata(media: dict) -> SeriesMetadata | None:
    """Parse AniList Media object into SeriesMetadata."""
    media_id = media.get("id")
    title_obj = media.get("title") or {}
    title_romaji = title_obj.get("romaji") or ""
    title_english = title_obj.get("english")

    if not media_id or not title_romaji:
        return None

    chars: list[CharacterProfile] = []
    edges = (media.get("characters") or {}).get("edges") or []
    for edge in edges:
        node = edge.get("node") or {}
        name_info = node.get("name") or {}
        user_pref = (name_info.get("userPreferred") or "").strip()
        if not user_pref:
            continue

        raw_gender = node.get("gender")
        gender = raw_gender.strip().lower() if raw_gender else None
        role = edge.get("role") or "SUPPORTING"

        aliases: set[str] = set()
        for alt in name_info.get("alternative") or []:
            alt_clean = alt.strip()
            if len(alt_clean) >= 3 and alt_clean.lower() != user_pref.lower():
                aliases.add(alt_clean)

        for part in user_pref.split():
            clean_part = re.sub(r"[^\w\s-]", "", part).strip()
            if len(clean_part) >= 3 and clean_part.lower() != user_pref.lower():
                aliases.add(clean_part)

        chars.append(
            CharacterProfile(
                name=user_pref,
                gender=gender,
                role=role,
                aliases=tuple(sorted(aliases)),
            )
        )

    return SeriesMetadata(
        media_id=media_id,
        title_romaji=title_romaji,
        title_english=title_english,
        synopsis=media.get("description"),
        characters=chars,
    )


def resolve_series_metadata(
    title: str | None = None,
    media_id: int | None = None,
    timeout: int = 10,
    use_cache: bool = True,
) -> SeriesMetadata | None:
    """Resolve series metadata with disk caching and graceful error fallback."""
    if not title and not media_id:
        return None

    cache_dir = get_metadata_cache_dir()

    # 1. Try disk cache if media_id is provided
    if use_cache and media_id:
        cache_file = cache_dir / f"{media_id}.json"
        if cache_file.is_file():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                return SeriesMetadata.from_dict(data)
            except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
                logger.debug("Failed reading metadata cache for %d: %s", media_id, e)

    # 2. Fetch from GraphQL
    variables: dict[str, str | int] = {}
    if media_id:
        variables["id"] = media_id
    elif title:
        variables["search"] = title

    try:
        response = _execute_graphql(
            SERIES_METADATA_QUERY, variables=variables, timeout=timeout
        )
        media = (response.get("data") or {}).get("Media")
        if not media:
            return None

        metadata = _parse_media_to_metadata(media)
        if not metadata:
            return None

        # 3. Write to disk cache
        if use_cache:
            cache_file = cache_dir / f"{metadata.media_id}.json"
            try:
                cache_file.write_text(
                    json.dumps(metadata.to_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except OSError as e:
                logger.debug(
                    "Failed writing metadata cache for %d: %s", metadata.media_id, e
                )

        return metadata
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        logger.debug("Failed resolving metadata for %s: %s", title or media_id, e)
        return None
