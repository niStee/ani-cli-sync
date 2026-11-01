"""
ani-cli-sync: Automated AniList synchronization wrapper for ani-cli.

Features:
  - ani-cli-sync                 : Interactive fzf menu of currently watching anime from AniList,
                                   launches ani-cli at (progress + 1), and auto-updates AniList upon completion.
  - ani-cli-sync login           : Authenticates with AniList Personal Access Token.
  - ani-cli-sync list            : Lists currently watching anime with progress.
  - ani-cli-sync set <title> <ep>: Updates AniList progress for an anime directly.
  - ani-cli-sync import-netflix  : Imports watch history from Netflix CSV.
  - ani-cli-sync watch [query]   : Watches an anime and synchronizes progress.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from ani_cli_sync.menu import prepare_menu_env

logger = logging.getLogger(__name__)

ANILIST_API = "https://graphql.anilist.co"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "anilist"
TOKEN_FILE = CONFIG_DIR / "token"


def get_token() -> str | None:
    """Retrieve the stored AniList OAuth token, if present."""
    if TOKEN_FILE.is_file():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    return None


def save_token(token: str) -> None:
    """Save the AniList OAuth token with restricted permissions (0600)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token.strip(), encoding="utf-8")
    TOKEN_FILE.chmod(0o600)
    print(f"✓ AniList token saved to {TOKEN_FILE}")


def gql_query(query: str, variables: dict | None = None, token: str | None = None, retries: int = 3) -> dict:
    """Execute a GraphQL query or mutation against the AniList API."""
    data = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    # nosemgrep
    req = urllib.request.Request(
        ANILIST_API,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "ani-cli-sync/1.0"},
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    for attempt in range(retries):
        try:
            # nosemgrep
            with urllib.request.urlopen(req) as resp:  # nosemgrep
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                retry_after = int(e.headers.get("Retry-After", 2))
                time.sleep(retry_after + 1)
                continue
            err_body = e.read().decode("utf-8")
            try:
                err_json = json.loads(err_body)
                messages = [err.get("message", "") for err in err_json.get("errors", [])]
                raise RuntimeError(f"AniList API error: {'; '.join(messages)}") from e
            except (json.JSONDecodeError, KeyError):
                raise RuntimeError(f"AniList HTTP {e.code}: {err_body}") from e


def get_viewer(token: str) -> dict:
    """Fetch the authenticated user profile."""
    query = """
    query {
        Viewer {
            id
            name
        }
    }
    """
    res = gql_query(query, token=token)
    viewer = res.get("data", {}).get("Viewer")
    if not viewer:
        raise RuntimeError("Failed to fetch authenticated user profile.")
    return viewer


def get_watching_list(token: str, user_id: int) -> list[dict]:
    """Fetch user's Currently Watching anime list from AniList."""
    query = """
    query ($userId: Int) {
        MediaListCollection (userId: $userId, type: ANIME, status: CURRENT) {
            lists {
                entries {
                    id
                    mediaId
                    progress
                    media {
                        id
                        title {
                            romaji
                            english
                        }
                        episodes
                    }
                }
            }
        }
    }
    """
    res = gql_query(query, variables={"userId": user_id}, token=token)
    entries = []
    for lst in res.get("data", {}).get("MediaListCollection", {}).get("lists", []):
        entries.extend(lst.get("entries", []))
    return entries


def update_progress(token: str, media_id: int, progress: int, status: str = "CURRENT") -> dict:
    """Update watch progress and status for a media entry on AniList."""
    mutation = """
    mutation ($mediaId: Int, $progress: Int, $status: MediaListStatus) {
        SaveMediaListEntry (mediaId: $mediaId, progress: $progress, status: $status) {
            id
            mediaId
            progress
            status
        }
    }
    """
    res = gql_query(mutation, variables={"mediaId": media_id, "progress": progress, "status": status}, token=token)
    return res.get("data", {}).get("SaveMediaListEntry", {})


def get_media_list_entry(token: str, user_id: int, media_id: int) -> dict | None:
    """Fetch user's media list entry for a specific anime, if it exists."""
    query = """
    query ($uid: Int, $mid: Int) {
        MediaList (userId: $uid, mediaId: $mid) {
            status
            progress
        }
    }
    """
    try:
        res = gql_query(query, variables={"uid": user_id, "mid": media_id}, token=token)
        return res.get("data", {}).get("MediaList")
    except Exception:  # noqa: BLE001 - a failed progress read must not abort the run
        return None


def find_sequel(media_id: int, token: str | None = None) -> tuple[dict | None, str | None]:
    """Find the unambiguous TV/ONA sequel for a media entry, if released.

    Returns:
        A tuple of (sequel_node, reason_if_none).
    """
    query = """
    query ($id: Int) {
        Media (id: $id, type: ANIME) {
            relations {
                edges {
                    relationType
                    node {
                        id
                        title {
                            romaji
                            english
                        }
                        episodes
                        format
                        status
                    }
                }
            }
        }
    }
    """
    try:
        res = gql_query(query, variables={"id": media_id}, token=token)
    except Exception:  # noqa: BLE001 - an absent sequel is a valid outcome, not a failure
        return None, None

    media = res.get("data", {}).get("Media") if isinstance(res, dict) else None
    if not media:
        return None, None

    edges = media.get("relations", {}).get("edges", []) or []
    sequels = [
        edge.get("node")
        for edge in edges
        if edge.get("relationType") == "SEQUEL"
        and (edge.get("node") or {}).get("format") in ("TV", "ONA")
    ]

    if not sequels:
        return None, None

    if len(sequels) > 1:
        return None, "Multiple sequels found (ambiguous)."

    node = sequels[0]
    title = (node.get("title") or {}).get("english") or (node.get("title") or {}).get("romaji") or "Unknown"
    if node.get("status") == "NOT_YET_RELEASED":
        return None, f"Sequel '{title}' announced, not yet released."

    return node, None


def search_anime(title: str) -> dict | None:
    """Search for an anime on AniList by title."""
    query = """
    query ($search: String) {
        Media (search: $search, type: ANIME) {
            id
            title {
                romaji
                english
            }
            episodes
        }
    }
    """
    try:
        res = gql_query(query, variables={"search": title})
        return res.get("data", {}).get("Media")
    except Exception:  # noqa: BLE001 - "not found" and "lookup failed" both mean no match
        return None


def find_in_watching_list(entries: list[dict], title: str) -> dict | None:
    """Find matching anime media from currently watching list.

    Matches by:
    1. Exact match against english or romaji title (case-insensitive)
    2. Substring match against english or romaji title (case-insensitive)
    Returns the matching media dict, or None if no match.
    """
    if not entries or not title:
        return None
    t_lower = title.strip().lower()

    # 1. Exact match
    for e in entries:
        m = e.get("media", {})
        eng = (m.get("title", {}).get("english") or "").strip().lower()
        rom = (m.get("title", {}).get("romaji") or "").strip().lower()
        if t_lower == eng or t_lower == rom:
            return m

    # 2. Substring match
    matches = []
    for e in entries:
        m = e.get("media", {})
        eng = (m.get("title", {}).get("english") or "").strip().lower()
        rom = (m.get("title", {}).get("romaji") or "").strip().lower()
        if t_lower in eng or t_lower in rom:
            matches.append(m)

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        # Prefer shortest / most specific title
        matches.sort(key=lambda m: len(m.get("title", {}).get("english") or m.get("title", {}).get("romaji") or ""))
        return matches[0]

    return None


def cmd_login() -> None:
    """Interactive AniList OAuth setup."""
    print("=== AniList 1-Minute Setup ===")
    print("1. Open Developer Settings: https://anilist.co/settings/developer")
    print("2. Click 'Create New Client':")
    print("     • Name: ani-cli-sync")
    print("     • Redirect URL: https://anilist.co/api/v2/oauth/pin")
    print("3. Copy your generated Client ID.\n")
    client_id = input("Enter your Client ID (or press Enter if you already have a token): ").strip()
    if client_id:
        auth_url = f"https://anilist.co/api/v2/oauth/authorize?client_id={client_id}&response_type=token"
        print(f"\n▶ Authorize here: {auth_url}")
        try:
            subprocess.run(["xdg-open", auth_url], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:  # noqa: BLE001 - no browser opener is not a failure, the URL is printed above
            logger.debug("xdg-open could not be launched for the AniList authorize URL: %s", exc)

    print("\nAfter clicking 'Authorize', copy the token from the URL fragment (after #access_token=...)")
    token = input("\nEnter AniList Token: ").strip()
    if "#access_token=" in token:
        token = token.split("#access_token=")[1].split("&")[0]
    elif "access_token=" in token:
        token = token.split("access_token=")[1].split("&")[0]

    if not token:
        print("Error: Token cannot be empty.", file=sys.stderr)
        sys.exit(1)

    viewer = get_viewer(token)
    save_token(token)
    print(f"\n✓ Successfully authenticated as '{viewer['name']}' (User ID: {viewer['id']})!")


def cmd_list() -> None:
    """Display user's Currently Watching anime with episode progress."""
    token = get_token()
    if not token:
        print("Not logged in. Run 'ani-cli-sync login' first.", file=sys.stderr)
        sys.exit(1)
    viewer = get_viewer(token)
    entries = get_watching_list(token, viewer["id"])
    if not entries:
        print("Your Currently Watching list is empty on AniList.")
        return
    print(f"=== Currently Watching ({viewer['name']}) ===")
    for e in entries:
        media = e["media"]
        title = media["title"]["english"] or media["title"]["romaji"]
        total = media["episodes"] or "?"
        print(f"  [{e['progress']:02d}/{total}] {title}")


def cmd_set(title: str, episode: int) -> None:
    """Update watch progress for an anime directly."""
    token = get_token()
    if not token:
        print("Not logged in. Run 'ani-cli-sync login' first.", file=sys.stderr)
        sys.exit(1)

    media = None
    try:
        viewer = get_viewer(token)
        entries = get_watching_list(token, viewer["id"])
        media = find_in_watching_list(entries, title)
    except Exception as exc:  # noqa: BLE001 - the watchlist lookup is a shortcut, a failure falls through to global search
        logger.debug("AniList watchlist lookup failed, falling back to global search: %s", exc)

    if not media:
        media = search_anime(title)

    if not media:
        print(f"Error: Anime '{title}' not found on AniList.", file=sys.stderr)
        sys.exit(1)

    media_id = media["id"]
    display_title = media["title"]["english"] or media["title"]["romaji"]
    total_episodes = media.get("episodes")
    total_str = str(total_episodes) if total_episodes else "?"

    if total_episodes and episode > total_episodes:
        print(
            f"Error: episode {episode} exceeds total episode count ({total_episodes}) for "
            f"'{display_title}'. Did you pass an absolute scraper number instead of the "
            f"AniList episode number? Use 'ani-cli-sync set \"{display_title}\" <1..{total_episodes}>'.",
            file=sys.stderr,
        )
        sys.exit(1)

    status = "COMPLETED" if (total_episodes and episode >= total_episodes) else "CURRENT"
    update_progress(token, media_id, episode, status=status)
    print(f"✓ Updated AniList: {display_title} -> Episode {episode}/{total_str} [{status}]")


_NETFLIX_HEADER = ("Title", "Date")
_NETFLIX_EPISODE = re.compile(r"^(?P<release>.+): Episode (?P<episode>[1-9][0-9]*)$")
_NETFLIX_SEARCH_LIMIT = 10
_ANILIST_ENTRY_STATUSES = frozenset(
    {"CURRENT", "PLANNING", "PAUSED", "DROPPED", "REPEATING", "COMPLETED"}
)

_NETFLIX_SEARCH_QUERY = """
query ($search: String, $perPage: Int) {
  Page(page: 1, perPage: $perPage) {
    media(search: $search, type: ANIME) {
      id
      title { english romaji native }
      synonyms
      episodes
      format
    }
  }
}
"""

_NETFLIX_STATE_QUERY = """
query ($mid: Int) {
  MediaList(mediaId: $mid) {
    status
    progress
  }
}
"""

_NETFLIX_SAVE_MUTATION = """
mutation ($mediaId: Int, $progress: Int, $status: MediaListStatus) {
  SaveMediaListEntry(mediaId: $mediaId, progress: $progress, status: $status) {
    id
    mediaId
    progress
    status
  }
}
"""


class _NetflixFailure(Exception):
    """A processing failure that ends the run with exit code 1."""


def _netflix_rows(csv_path: str) -> list[tuple[str, str]]:
    """Read the history strictly: any doubt exits 2 before a single API call."""
    path = Path(csv_path).expanduser()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        print(f"Error: cannot read {path}: {exc}", file=sys.stderr)
        sys.exit(2)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        print(f"Error: {path} is not valid UTF-8", file=sys.stderr)
        sys.exit(2)
    text = text.removeprefix("\ufeff")
    rows: list[tuple[str, str]] = []
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    header: list[str] | None = None
    try:
        for record in reader:
            if header is None:
                header = record
                if tuple(header) != _NETFLIX_HEADER:
                    expected = ",".join(_NETFLIX_HEADER)
                    print(f"Error: expected header {expected}, got {','.join(header)}", file=sys.stderr)
                    sys.exit(2)
                continue
            if len(record) != 2:
                print(f"Error: expected 2 fields per row, got {len(record)}: {record}", file=sys.stderr)
                sys.exit(2)
            title, date = record[0].strip(), record[1].strip()
            if not title or not date:
                print(f"Error: empty title or date in row: {record}", file=sys.stderr)
                sys.exit(2)
            rows.append((title, date))
    except csv.Error as exc:
        print(f"Error: malformed CSV: {exc}", file=sys.stderr)
        sys.exit(2)
    if header is None:
        print("Error: empty file, no header", file=sys.stderr)
        sys.exit(2)
    return rows


def _netflix_identity(title: str) -> tuple[str, int] | None:
    """Split '<release>: Episode <n>' right-anchored; anything else is unresolved."""
    match = _NETFLIX_EPISODE.fullmatch(title)
    if match is None:
        return None
    return match.group("release"), int(match.group("episode"))


def _netflix_search(release: str, token: str) -> list[object]:
    try:
        response = gql_query(
            _NETFLIX_SEARCH_QUERY,
            {"search": release, "perPage": _NETFLIX_SEARCH_LIMIT},
            token=token,
        )
    except Exception as exc:
        raise _NetflixFailure(f"transport error: {exc}") from exc
    if not isinstance(response, dict):
        raise _NetflixFailure("malformed search response")
    if response.get("errors"):
        raise _NetflixFailure(f"GraphQL error: {response['errors']}")
    data = response.get("data")
    if not isinstance(data, dict):
        raise _NetflixFailure("malformed search response: no data")
    page = data.get("Page")
    if not isinstance(page, dict):
        raise _NetflixFailure("malformed search response: no Page")
    media = page.get("media")
    if not isinstance(media, list):
        raise _NetflixFailure("malformed search response: no media list")
    return media


def _netflix_candidate(
    candidate: object,
) -> tuple[int, list[str], int | None, str | None]:
    """Validate one candidate; a field we cannot trust fails the whole read closed."""
    if not isinstance(candidate, dict):
        raise _NetflixFailure("malformed candidate: not an object")
    media_id = candidate.get("id")
    if not isinstance(media_id, int) or isinstance(media_id, bool):
        raise _NetflixFailure("malformed candidate: missing or non-integer id")
    title = candidate.get("title")
    if not isinstance(title, dict):
        raise _NetflixFailure(f"malformed candidate {media_id}: title is not an object")
    names: list[str] = []
    for key in ("english", "romaji", "native"):
        value = title.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            raise _NetflixFailure(f"malformed candidate {media_id}: title.{key} is not a string")
        names.append(value)
    synonyms = candidate.get("synonyms")
    if synonyms is None:
        synonyms = []
    if not isinstance(synonyms, list) or any(not isinstance(name, str) for name in synonyms):
        raise _NetflixFailure(f"malformed candidate {media_id}: synonyms is not a list of strings")
    names.extend(synonyms)
    episodes = candidate.get("episodes")
    if episodes is not None and (not isinstance(episodes, int) or isinstance(episodes, bool)):
        raise _NetflixFailure(f"malformed candidate {media_id}: episodes is not an integer")
    media_format = candidate.get("format")
    if media_format is not None and not isinstance(media_format, str):
        raise _NetflixFailure(f"malformed candidate {media_id}: format is not a string")
    return media_id, names, episodes, media_format


def _netflix_read_state(media_id: int, token: str) -> dict | None:
    """Read the current list entry; absence is None, anything unreadable fails closed."""
    try:
        response = gql_query(_NETFLIX_STATE_QUERY, {"mid": media_id}, token=token)
    except Exception as exc:
        raise _NetflixFailure(f"transport error: {exc}") from exc
    if not isinstance(response, dict):
        raise _NetflixFailure("malformed state response")
    if response.get("errors"):
        raise _NetflixFailure(f"GraphQL error: {response['errors']}")
    data = response.get("data")
    if not isinstance(data, dict) or "MediaList" not in data:
        raise _NetflixFailure("malformed state response: no MediaList")
    entry = data["MediaList"]
    if entry is None:
        return None
    if not isinstance(entry, dict):
        raise _NetflixFailure("malformed state response: MediaList is not an object")
    status = entry.get("status")
    if status not in _ANILIST_ENTRY_STATUSES:
        raise _NetflixFailure(f"malformed state response: unknown status {status!r}")
    progress = entry.get("progress")
    if not isinstance(progress, int) or isinstance(progress, bool) or progress < 0:
        raise _NetflixFailure(f"malformed state response: invalid progress {progress!r}")
    return {"status": status, "progress": progress}


def _netflix_infer(episodes: list[int]) -> int | None:
    """Only a contiguous run starting at 1 supports an inferred progress."""
    if not episodes:
        return None
    if episodes == list(range(1, episodes[-1] + 1)):
        return episodes[-1]
    return None


def _netflix_decide(
    state: dict | None,
    inferred: int,
    total: int | None,
) -> tuple[str, int, str, str]:
    """Decide against a state snapshot; returns (action, progress, status, reason)."""
    if state is None:
        return ("mutate", inferred, "CURRENT", "absent entry")
    if state["status"] != "CURRENT":
        return ("skip", 0, "", f"status policy: {state['status']} is preserved")
    if state["progress"] > inferred:
        return ("skip", 0, "", "unchanged: recorded progress is already ahead")
    if isinstance(total, int) and not isinstance(total, bool) and total > 0 and inferred >= total:
        return ("mutate", total, "COMPLETED", "full coverage")
    if state["progress"] == inferred:
        return ("skip", 0, "", "unchanged: already current")
    return ("mutate", inferred, "CURRENT", "partial coverage")


def _netflix_mutate(media_id: int, progress: int, status: str, token: str) -> None:
    """Write one entry and refuse to call it done unless every field echoes back."""
    try:
        response = gql_query(
            _NETFLIX_SAVE_MUTATION,
            {"mediaId": media_id, "progress": progress, "status": status},
            token=token,
        )
    except Exception as exc:
        raise _NetflixFailure(f"transport error: {exc}") from exc
    if not isinstance(response, dict):
        raise _NetflixFailure("malformed mutation response")
    if response.get("errors"):
        raise _NetflixFailure(f"GraphQL error: {response['errors']}")
    data = response.get("data")
    if not isinstance(data, dict):
        raise _NetflixFailure("malformed mutation response: no data")
    entry = data.get("SaveMediaListEntry")
    if not isinstance(entry, dict):
        raise _NetflixFailure("mutation response has no entry")
    if entry.get("mediaId") != media_id:
        raise _NetflixFailure(f"mutation echoed mediaId {entry.get('mediaId')!r}, expected {media_id}")
    echoed_progress = entry.get("progress")
    if not isinstance(echoed_progress, int) or isinstance(echoed_progress, bool) or echoed_progress < 0:
        raise _NetflixFailure(f"mutation echoed invalid progress {echoed_progress!r}")
    if echoed_progress != progress:
        raise _NetflixFailure(f"mutation echoed progress {echoed_progress}, expected {progress}")
    if entry.get("status") != status:
        raise _NetflixFailure(f"mutation echoed status {entry.get('status')!r}, expected {status}")


def cmd_import_netflix(csv_path: str, *, apply: bool = False) -> None:
    """Preview or apply a Netflix viewing-history CSV against AniList.

    The CSV is read and validated in full before the first API call. Every row is
    accounted for in the summary. Progress is only ever *inferred* from a
    contiguous run of episodes starting at 1, never from a late or sparse set,
    and a completion is only proposed when the inferred progress reaches a known
    episode total. With ``apply`` every planned write is re-read immediately
    before it is sent and verified field by field afterwards.
    """
    token = get_token()
    if not token:
        print("Not logged in. Run 'ani-cli-sync login' first.", file=sys.stderr)
        sys.exit(1)

    rows = _netflix_rows(csv_path)
    if not rows:
        print("input rows: 0 (zero events to import)")
        return

    failures = False
    unresolved: list[tuple[str, str]] = []
    groups: dict[str, list[tuple[int, str]]] = {}
    for title, date in rows:
        identity = _netflix_identity(title)
        if identity is None:
            unresolved.append((title, date))
            continue
        release, episode = identity
        groups.setdefault(release, []).append((episode, date))

    for title, _date in unresolved:
        print(
            f"{title} -> unresolved (unsupported title grammar, "
            "expected '<release>: Episode <n>')"
        )

    plans: dict[int, dict] = {}
    searches: dict[str, object] = {}
    for release, items in groups.items():
        if release not in searches:
            try:
                searches[release] = _netflix_search(release, token)
            except _NetflixFailure as exc:
                searches[release] = exc
        candidates = searches[release]
        if isinstance(candidates, _NetflixFailure):
            failures = True
            print(f"{release} -> error (search failed: {candidates})")
            continue

        matches: dict[int, dict] = {}
        try:
            for candidate in candidates:
                media_id, names, episodes, media_format = _netflix_candidate(candidate)
                if release not in names:
                    continue
                entry = matches.setdefault(media_id, {"episodes": episodes, "formats": set()})
                if media_format:
                    entry["formats"].add(media_format)
        except _NetflixFailure as exc:
            failures = True
            print(f"{release} -> error (malformed candidate: {exc})")
            continue

        if len(matches) > 1 or (matches and len(candidates) >= _NETFLIX_SEARCH_LIMIT):
            ids = ", ".join(str(media_id) for media_id in sorted(matches))
            formats = sorted({fmt for entry in matches.values() for fmt in entry["formats"]})
            format_note = f" formats: {', '.join(formats)}" if formats else ""
            page_note = (
                f" (full page, bounded to {_NETFLIX_SEARCH_LIMIT} results)"
                if len(candidates) >= _NETFLIX_SEARCH_LIMIT
                else ""
            )
            print(f"{release} -> ambiguous: {ids}{format_note}{page_note}")
            continue
        if not matches:
            print(f"{release} -> unmatched")
            continue

        media_id, match = next(iter(matches.items()))
        plan = plans.setdefault(
            media_id,
            {"episodes": set(), "dates": [], "releases": [], "rows": 0, "total": match["episodes"]},
        )
        plan["episodes"].update(episode for episode, _date in items)
        plan["dates"].extend(date for _episode, date in items)
        plan["releases"].append(release)
        plan["rows"] += len(items)
        if plan["total"] is None:
            plan["total"] = match["episodes"]

    for media_id, plan in plans.items():
        label = " + ".join(plan["releases"])
        episodes = sorted(plan["episodes"])
        duplicates = plan["rows"] - len(episodes)
        dedup_note = f" | dedup: {duplicates} duplicate row(s)" if duplicates > 0 else ""
        head = (
            f"{label} -> media {media_id} | recorded episodes: "
            f"{', '.join(str(episode) for episode in episodes)}"
            f" | dates: {', '.join(plan['dates'])}{dedup_note}"
        )

        inferred = _netflix_infer(episodes)
        if inferred is None:
            print(f"{head} | blocked: insufficient coverage (sparse or late-only episodes)")
            continue

        try:
            state = _netflix_read_state(media_id, token)
        except _NetflixFailure as exc:
            failures = True
            print(f"{head} | failed: state read: {exc}")
            continue

        action, progress, status, reason = _netflix_decide(
            state, inferred, plan["total"]
        )
        if action == "skip":
            print(f"{head} | inferred progress: {inferred} | {reason}")
            continue
        if not apply:
            print(f"{head} | inferred progress: {inferred} | target status: {status} | preview")
            continue

        try:
            fresh = _netflix_read_state(media_id, token)
        except _NetflixFailure as exc:
            failures = True
            print(f"{head} | failed: fresh state read: {exc}")
            continue
        action, progress, status, reason = _netflix_decide(
            fresh, inferred, plan["total"]
        )
        if action == "skip":
            print(f"{head} | inferred progress: {inferred} | {reason}")
            continue

        try:
            _netflix_mutate(media_id, progress, status, token)
        except _NetflixFailure as exc:
            failures = True
            print(
                f"{head} | inferred progress: {inferred} | target status: {status}"
                f" | unverified: {exc}"
            )
            continue
        print(f"{head} | inferred progress: {inferred} | target status: {status} | verified")

    print(f"input rows: {len(rows)} (reconciled: {len(rows)})")
    if failures:
        sys.exit(1)


# Episode offset table: (display_fragment, search_override | None, max_anilist_ep, scraper_offset)
#
# When the scraper backend (e.g. gogoanime/AniDB) uses absolute continuous numbering across seasons
# but AniList tracks each season independently (ep 1..N), we must add an offset to translate the
# AniList episode number into the scraper's episode number.
#
# Table format: (fragment_in_display_part, search_override, max_anilist_ep, offset)
#   - fragment_in_display_part: substring matched case-sensitively against the fzf display line
#   - search_override: ani-cli search string to use (None = keep the AniList romaji title)
#   - max_anilist_ep: only apply offset when anilist ep <= this value (safety guard)
#   - offset: added to the AniList ep number to get the scraper ep number
#
# To add a new season: append one tuple. No control-flow changes needed.
_EPISODE_OFFSETS: list[tuple[str, str | None, int, int]] = [
    # Slime S4: AniList 1-24 → hianime 1-24 (provider uses per-season numbering, offset 0 guards against prequel chain)
    ("Slime Season 4", "That Time I Got Reincarnated as a Slime Season 4", 24, 0),
    ("Slime Datta Ken 4th Season", "That Time I Got Reincarnated as a Slime Season 4", 24, 0),
    # Slime S3: AniList 1-24 → hianime 1-24 (provider uses per-season numbering, offset 0 guards against prequel chain)
    ("Slime Season 3", "That Time I Got Reincarnated as a Slime Season 3", 24, 0),
    ("Slime Datta Ken 3rd Season", "That Time I Got Reincarnated as a Slime Season 3", 24, 0),
    # Frieren S2: AniList 1-10 → gogoanime 29-38
    ("Frieren: Beyond Journey's End Season 2", None, 10, 28),
    ("Sousou no Frieren 2nd Season", None, 10, 28),
    # Slime S2 Part 2: AniList 1-12 → hianime 1-12
    ("Slime Season 2 Part 2", "That Time I Got Reincarnated as a Slime Season 2 Part 2", 12, 0),
    ("Slime 2nd Season Part 2", "That Time I Got Reincarnated as a Slime Season 2 Part 2", 12, 0),
    ("Slime Datta Ken 2nd Season Part 2", "That Time I Got Reincarnated as a Slime Season 2 Part 2", 12, 0),
    ("Tensei Shitara Slime Datta Ken 2nd Season Part 2", "That Time I Got Reincarnated as a Slime Season 2 Part 2", 12, 0),
    # Slime S2: AniList 1-12 → hianime 1-12
    ("Slime Season 2", "That Time I Got Reincarnated as a Slime Season 2", 12, 0),
    ("Slime 2nd Season", "That Time I Got Reincarnated as a Slime Season 2", 12, 0),
    ("Tensei Shitara Slime Datta Ken 2nd Season", "That Time I Got Reincarnated as a Slime Season 2", 12, 0),
    # Overlord III & IV: provider uses per-season numbering, offset 0 guards against prequel chain
    ("Overlord III", "Overlord III", 13, 0),
    ("Overlord IV", "Overlord IV", 13, 0),
    # Attack on Titan: The Final Season Part 2: AniList 1-12 → provider "Attack on Titan: Final Season, Part 2" 1-12.
    # Part 2 entries MUST precede the Part 1 entries: the Part 1 fragment is a substring of the
    # Part 2 display title, so a Part 1-first order would swallow every Part 2 episode.
    ("Attack on Titan Final Season Part 2", "Attack on Titan: Final Season, Part 2", 12, 0),
    ("Attack on Titan: The Final Season Part 2", "Attack on Titan: Final Season, Part 2", 12, 0),
    ("Shingeki no Kyojin: The Final Season Part 2", "Attack on Titan: Final Season, Part 2", 12, 0),
    # Attack on Titan: The Final Season Part 1: AniList 1-16 → provider "Attack on Titan: Final Season, Part 1" 1-16.
    ("Attack on Titan Final Season", "Attack on Titan: Final Season, Part 1", 16, 0),
    ("Shingeki no Kyojin: The Final Season", "Attack on Titan: Final Season, Part 1", 16, 0),
]


_PREQUEL_OFFSET_CACHE: dict[int, int | None] = {}


def compute_prequel_offset(
    media_id: int,
    gql_fn: Callable[[str, dict | None], dict],
    max_depth: int = 10,
) -> int | None:
    """Walk PREQUEL edges of TV/ONA entries summing episodes to compute continuous offset.

    Guardrails:
      - Visited set for cycle detection (returns None on cycle)
      - Max depth limit (10) (returns None if exceeded)
      - episodes is None on any prequel node -> returns None
      - Multiple TV/ONA PREQUEL edges at any step -> returns None (ambiguous)
      - Returns None on any GraphQL/network exception (never raises)

    Returns:
      Total prequel episodes (int) if an unambiguous prequel chain exists, or None.
    """
    query = """
    query ($id: Int) {
        Media (id: $id, type: ANIME) {
            relations {
                edges {
                    relationType
                    node {
                        id
                        episodes
                        format
                    }
                }
            }
        }
    }
    """
    visited: set[int] = {media_id}
    current_id = media_id
    total_offset = 0
    depth = 0

    while depth < max_depth:
        try:
            res = gql_fn(query, {"id": current_id})
        except Exception:  # noqa: BLE001 - an unresolvable chain means "no computed offset"
            return None

        media = res.get("data", {}).get("Media") if isinstance(res, dict) else None
        if not media:
            return None

        edges = media.get("relations", {}).get("edges", []) or []
        prequels = [
            edge.get("node")
            for edge in edges
            if edge.get("relationType") == "PREQUEL"
            and (edge.get("node") or {}).get("format") in ("TV", "ONA")
        ]

        if not prequels:
            return total_offset

        if len(prequels) > 1:
            return None

        node = prequels[0]
        node_id = node.get("id")
        episodes = node.get("episodes")

        if node_id is None or episodes is None:
            return None

        if node_id in visited:
            return None

        visited.add(node_id)
        total_offset += episodes
        current_id = node_id
        depth += 1

    return None


def has_table_offset_match(display_part: str, anilist_ep: int) -> bool:
    """Check whether the static _EPISODE_OFFSETS table matches the entry."""
    for fragment, _, max_ep, _ in _EPISODE_OFFSETS:
        if fragment in display_part and anilist_ep <= max_ep:
            return True
    return False


def resolve_episode_offset(
    display_part: str,
    title_search: str,
    anilist_ep: int,
    computed_offset: int | None = None,
) -> tuple[str, int]:
    """Translate an AniList episode number to a scraper episode number using the offset table.

    Precedence order:
      1. Static _EPISODE_OFFSETS table match (always wins, can provide search_override)
      2. Computed PREQUEL-chain offset (if table misses and computed_offset is provided)
      3. Identity (title_search, anilist_ep)

    Args:
        display_part:    The fzf display string for the selected entry (used for fragment matching).
        title_search:    The ani-cli search title (romaji preferred, falls back to english).
        anilist_ep:      The AniList episode number to play (1-based within the season).
        computed_offset: Optional computed PREQUEL-chain offset when table misses.

    Returns:
        A (search_arg, scraper_ep) tuple ready to pass to ani-cli.
    """
    for fragment, search_override, max_ep, offset in _EPISODE_OFFSETS:
        if fragment in display_part and anilist_ep <= max_ep:
            return (search_override or title_search), anilist_ep + offset

    if computed_offset is not None and computed_offset > 0:
        return title_search, anilist_ep + computed_offset

    return title_search, anilist_ep


# A 24-minute episode with OP/ED skipped; used only when the real duration is unknown.
_FALLBACK_COMPLETE_SECONDS = 1150.0
_DEFAULT_WATCHED_RATIO = 0.80
_SKIP_AWARE_WATCHED_RATIO = 0.70


def _calculate_skip_seconds(stream_info) -> float:
    """Calculate total expected seconds skipped via intro and outro markers."""
    if not stream_info:
        return 0.0
    total = 0.0
    intro = getattr(stream_info, "intro_skip", None)
    if intro and len(intro) == 2 and intro[1] > intro[0]:
        total += intro[1] - intro[0]
    outro = getattr(stream_info, "outro_skip", None)
    if outro and len(outro) == 2 and outro[1] > outro[0]:
        total += outro[1] - outro[0]
    return total


def _should_advance(
    returncode: int,
    elapsed: float,
    duration: float | None,
    skip_seconds: float = 0.0,
) -> tuple[bool, str]:
    """Decide whether autoplay may continue to the next episode.

    Only positive evidence that the episode played through allows advancing. Closing the
    player is an explicit stop, and two cases used to get that wrong:

    - A non-zero mpv exit skipped the early-stop branch entirely, because that branch was
      nested inside ``if ret.returncode == 0``. Closing the player window can exit
      non-zero, so the episode looked like it had played successfully.
    - A zero exit at or past 600s counted as "watched", so closing the window 11 minutes
      into a 24-minute episode started the next one.

    ``elapsed`` is wall-clock for the mpv process. When automated intro/outro skips occur
    (e.g. ani-skip), skipping OP (~90s) and ED (~90s) removes ~12.5%-15% of runtime, so
    effective duration (duration - skip_seconds) is used with a 70% completion floor. The
    floor is lower than the no-skip baseline because the tracker knows non-narrative
    content was skipped; the affected releases carry recaps and credits beyond the
    marked OP/ED, which the skip metadata does not cover. Without skip metadata, an 80%
    baseline (matching PlexTraktSync and Trakt standards) allows manual skips without
    false early-stop halts. When duration is unknown, 1150s (~19.2m) serves as the
    fallback floor.
    """
    if returncode != 0:
        return False, f"player exited with code {returncode}"

    if duration:
        if skip_seconds > 0:
            effective_duration = max(0.0, duration - skip_seconds)
            threshold = effective_duration * _SKIP_AWARE_WATCHED_RATIO
        else:
            threshold = duration * _DEFAULT_WATCHED_RATIO
    else:
        threshold = max(0.0, _FALLBACK_COMPLETE_SECONDS - skip_seconds)

    if elapsed >= threshold:
        return True, f"played {elapsed:.0f}s of {threshold:.0f}s"

    return False, f"stopped after {elapsed:.0f}s (needed {threshold:.0f}s to count as watched)"


def _probe_duration(stream_info) -> float | None:
    """Total media duration in seconds, summed from the HLS media playlist.

    Returns ``None`` when it cannot be determined; callers must treat that as unknown
    rather than as zero. Costs one playlist fetch, which ani-cli already makes.
    """
    import re as _re
    import urllib.request as _urllib_request

    # The no-sub-fallback path builds the command without resolving stream info, so
    # stream_info can legitimately be None. Duration is an optimisation, never a
    # precondition for playback, so every failure mode returns None.
    try:
        url = stream_info.video_link
    except AttributeError:
        return None
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return None
    try:
        req = _urllib_request.Request(url, headers={"Referer": stream_info.referrer})
        with _urllib_request.urlopen(req, timeout=15) as resp:  # nosec B310 # nosemgrep
            body = resp.read(400_000).decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - duration is an optimisation, never fatal
        logger.debug("duration probe failed for %s: %s", url, exc)
        return None

    total = 0.0
    found = False
    for match in _re.finditer(r"#EXTINF:\s*([0-9]+(?:\.[0-9]+)?)", body):
        total += float(match.group(1))
        found = True
    return total if found and total > 0 else None


def _should_auto_measure(sub_sync: str, sub_delay: float) -> bool:
    """Whether to measure the subtitle offset for this episode.

    An explicit --sub-delay always wins: a value the operator typed is a deliberate
    correction and must never be overridden by a measurement.
    """
    return sub_sync == "auto" and not sub_delay


def _auto_sub_delay(stream_info, sub_plan) -> float:
    """Measure this episode's subtitle offset. Returns 0.0 to leave timing unchanged.

    Never raises: a measurement failure must not stop playback. A manual --sub-delay is
    applied by the caller before this runs, so an explicit value is never overridden.
    """
    primary = sub_plan.sub_files[0] if sub_plan.sub_files else None
    if not primary:
        print("  ℹ️ sub-sync: no subtitle track selected, leaving timing unchanged.")
        return 0.0

    try:
        from ani_cli_sync.subsync import measure_offset, vad_available
    except ImportError as exc:
        print(f"  ℹ️ sub-sync unavailable: {exc}")
        return 0.0

    if not vad_available():
        print(
            "  ℹ️ sub-sync: the optional VAD is not installed, leaving timing unchanged.\n"
            '     Install it with: uv tool install "ani-cli-sync[subsync]"'
        )
        return 0.0

    try:
        result = measure_offset(stream_info, primary)
    except Exception as exc:  # noqa: BLE001 - playback must not fail on a measurement error
        print(f"  ⚠️ sub-sync failed ({exc}), leaving timing unchanged.")
        return 0.0

    if result is None:
        print("  ⚠️ sub-sync produced no result, leaving timing unchanged.")
        return 0.0

    if not result.confident:
        print(f"  ℹ️ sub-sync: {result.reason}. Leaving timing unchanged.")
        return 0.0

    print(f"  ⟲ sub-sync: {result.describe()}")
    if abs(result.offset) < 0.05:
        print("     Offset is negligible; not applying a shift.")
        return 0.0
    return result.offset


def cmd_watch(
    query: str | None = None,
    skip_intro: bool = True,
    dub: bool = False,
    quality: str | None = None,
    autoplay: bool = False,
    sub_primary: str | None = None,
    sub_secondary: str | None = None,
    no_sub_fallback: bool = False,
    uncensored: bool = True,
    sub_delay: float = 0.0,
    sub_sync: str = "off",
) -> None:
    """Launch ani-cli for an anime, track watch state, and synchronize to AniList."""
    token = get_token()
    if not token:
        print("No AniList token found. Falling back to native ani-cli...")
        args = ["ani-cli"]
        if skip_intro:
            args.append("--skip")
        if dub:
            args.append("--dub")
        if quality:
            args.extend(["-q", quality])
        # check=False: ani-cli's exit code is not the caller's contract here.
        # The watch loop reconciles progress from AniList, not from the player.
        subprocess.run(args, check=False)
        return

    viewer = get_viewer(token)
    entries = get_watching_list(token, viewer["id"])
    if not entries and not query:
        print("Your Currently Watching list on AniList is empty.")
        print("Starting ani-cli search...")
        cmd = ["ani-cli"]
        if skip_intro:
            cmd.append("--skip")
        if dub:
            cmd.append("--dub")
        if quality:
            cmd.extend(["-q", quality])
        subprocess.run(cmd, check=False)
        return

    # Build fzf menu options
    lines = []
    for e in entries:
        media = e["media"]
        romaji = media["title"]["romaji"] or ""
        english = media["title"]["english"] or romaji
        total = media["episodes"] or "?"
        curr = e["progress"]
        lines.append(f"[{curr:02d}/{total}] {english} | {romaji} ###{e['mediaId']}###{curr}###{total}")

    selected_line = None
    if query:
        q_lower = query.lower().strip()
        matched_lines = [line for line in lines if q_lower in line.lower()]
        if len(matched_lines) == 1:
            selected_line = matched_lines[0]
        elif len(matched_lines) > 1:
            # Check for exact title match among matched candidates
            for line in matched_lines:
                disp = line.split("###")[0].strip()
                title_part = disp.split("] ")[1]
                titles = [t.strip().lower() for t in title_part.split(" | ")]
                if q_lower in titles:
                    selected_line = line
                    break
            if not selected_line:
                lines = matched_lines

    # Autoplay + no CURRENT match: fall back to a global AniList search so the
    # caller never needs fzf (avoids 'inappropriate ioctl' when no controlling tty).
    if not selected_line and autoplay and query:
        media = search_anime(query)
        if media:
            romaji = media["title"].get("romaji") or ""
            english = media["title"].get("english") or romaji
            total = media["episodes"] or "?"
            media_id = media["id"]
            update_progress(token, media_id, 1, status="CURRENT")
            selected_line = f"[00/{total}] {english} | {romaji} ###{media_id}###0###{total}"
        else:
            print(f"Anime '{query}' not found on AniList.")
            return

    if not selected_line:
        try:
            fzf_proc = subprocess.Popen(
                ["fzf", "--prompt=Select Anime to Continue > ", "--header=AniList Currently Watching"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
            )
            selected_line, _ = fzf_proc.communicate(input="\n".join(lines))
            if fzf_proc.returncode != 0 or not selected_line.strip():
                return
        except FileNotFoundError:
            print("=== Select Anime to Continue ===")
            for idx, line in enumerate(lines, 1):
                disp = line.split("###")[0].strip()
                print(f"  {idx}) {disp}")
            choice = input("Enter number (or press Enter to cancel): ").strip()
            if not choice.isdigit() or int(choice) < 1 or int(choice) > len(lines):
                return
            selected_line = lines[int(choice) - 1]

    # Parse selected entry
    line_parts = selected_line.strip().split("###")
    display_part = line_parts[0].strip()
    media_id = int(line_parts[1])
    current_ep = int(line_parts[2])
    total_eps_str = line_parts[3] if len(line_parts) > 3 else "?"
    total_eps = int(total_eps_str) if total_eps_str.isdigit() else None
    next_ep = current_ep + 1

    # Extract search query (prefer romaji or english)
    title_search = display_part.split("] ")[1].split(" | ")[0]
    if " | " in display_part:
        romaji = display_part.split(" | ")[1]
        if romaji:
            title_search = romaji

    curr_ep_to_play = next_ep
    while True:
        computed_offset = None
        if not has_table_offset_match(display_part, curr_ep_to_play):
            if media_id not in _PREQUEL_OFFSET_CACHE:
                _PREQUEL_OFFSET_CACHE[media_id] = compute_prequel_offset(
                    media_id,
                    lambda q, v: gql_query(q, v, token=token),
                )
            computed_offset = _PREQUEL_OFFSET_CACHE.get(media_id)

        search_arg, ep_arg = resolve_episode_offset(
            display_part,
            title_search,
            curr_ep_to_play,
            computed_offset=computed_offset,
        )

        stream_info = None
        if not no_sub_fallback and not dub:
            try:
                from ani_cli_sync.subtitles import (
                    build_mpv_command,
                    prefetch_next_episode,
                    prepare_subtitles,
                    resolve_stream_info,
                )

                sec_lang = sub_secondary or os.environ.get("ANI_CLI_SYNC_SUB_SECONDARY", None)
                sub_target_desc = "German" if not sec_lang else f"German + {sec_lang}"
                print(f"🔍 Resolving stream and subtitles for '{search_arg}' Episode {ep_arg}...")
                stream_info = resolve_stream_info(
                    search_arg,
                    ep_arg,
                    quality=quality,
                    dub=dub,
                    uncensored=uncensored,
                )
                if not stream_info and ep_arg != curr_ep_to_play:
                    print(
                        f"ℹ️ Continuous Episode {ep_arg} not found on provider. "
                        f"Falling back to season-relative Episode {curr_ep_to_play}..."
                    )
                    stream_info = resolve_stream_info(
                        search_arg,
                        curr_ep_to_play,
                        quality=quality,
                        dub=dub,
                        uncensored=uncensored,
                    )
                    if stream_info:
                        ep_arg = curr_ep_to_play
                        _PREQUEL_OFFSET_CACHE[media_id] = 0

                if stream_info:
                    print(f"✓ Stream resolved. Preparing subtitles ({sub_target_desc})...")
                    sub_plan = prepare_subtitles(
                        stream_info,
                        search_arg,
                        ep_arg,
                        primary_lang=sub_primary or os.environ.get("ANI_CLI_SYNC_SUB_PRIMARY", "de"),
                        secondary_lang=sec_lang,
                    )
                    # Per-episode: the offset belongs to one subtitle file, never to the
                    # invocation. Writing the result into `sub_delay` would make the guard
                    # reject the next episode and replay this episode's shift on it.
                    episode_delay = sub_delay
                    if _should_auto_measure(sub_sync, sub_delay):
                        episode_delay = _auto_sub_delay(stream_info, sub_plan)
                    cmd = build_mpv_command(stream_info, sub_plan, search_arg, ep_arg, sub_delay=episode_delay)
                    if not skip_intro:
                        cmd = [arg for arg in cmd if not arg.startswith("--script-opts-append=skip-")]

                    # Lookahead: quietly prefetch next episode subtitles in background while current episode plays
                    if total_eps is None or (curr_ep_to_play + 1 <= total_eps):
                        threading.Thread(
                            target=prefetch_next_episode,
                            kwargs={
                                "anime_title": search_arg,
                                "ep_no": curr_ep_to_play + 1,
                                "primary_lang": sub_primary or os.environ.get("ANI_CLI_SYNC_SUB_PRIMARY", "de"),
                                "secondary_lang": sec_lang,
                                "quality": quality,
                                "dub": dub,
                                "uncensored": uncensored,
                            },
                            daemon=True,
                        ).start()
            except Exception as e:  # noqa: BLE001 - subtitle setup must never block playback
                print(f"⚠️ Subtitle fallback setup encountered an issue ({e}). Falling back to native ani-cli.")
                stream_info = None

        if not stream_info:
            print(f"\n▶ Launching ani-cli for '{search_arg}' Episode {ep_arg}...")
            menu_env = prepare_menu_env(target_title=search_arg, uncensored=uncensored)
            cmd = ["ani-cli", "--exit-after-play"]
            if skip_intro:
                cmd.append("--skip")
            if dub:
                cmd.append("--dub")
            if quality:
                cmd.extend(["-q", quality])
            cmd.extend(["-e", str(ep_arg), search_arg])

            t_start = time.time()
            # nosec B603
            # nosemgrep
            ret = subprocess.run(cmd, env=menu_env, check=False)  # nosec B603 # nosemgrep
            elapsed = time.time() - t_start

            if (ret.returncode != 0 or elapsed < 5) and ep_arg != curr_ep_to_play:
                print(
                    f"ℹ️ Continuous Episode {ep_arg} failed. "
                    f"Retrying season-relative Episode {curr_ep_to_play}..."
                )
                retry_cmd = list(cmd)
                if "-e" in retry_cmd:
                    ep_idx = retry_cmd.index("-e") + 1
                    retry_cmd[ep_idx] = str(curr_ep_to_play)
                t_start = time.time()
                # nosec B603
                # nosemgrep
                ret = subprocess.run(retry_cmd, env=menu_env, check=False)  # nosec B603 # nosemgrep
                elapsed = time.time() - t_start
                if ret.returncode == 0 and elapsed >= 5:
                    ep_arg = curr_ep_to_play
                    _PREQUEL_OFFSET_CACHE[media_id] = 0
        else:
            t_start = time.time()
            # nosec B603
            # nosemgrep
            ret = subprocess.run(cmd, check=False)  # nosec B603 # nosemgrep
            elapsed = time.time() - t_start

        # A non-zero exit already means "the user closed the player"; the probe only
        # refines the zero-exit case, so don't pay for a playlist fetch we won't use.
        duration = _probe_duration(stream_info) if ret.returncode == 0 else None
        skip_seconds = _calculate_skip_seconds(stream_info) if ret.returncode == 0 else 0.0
        advance, why = _should_advance(ret.returncode, elapsed, duration, skip_seconds=skip_seconds)
        if not advance:
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            print(f"\n⏹ Playback stopped ({mins}m {secs}s, {why}). AniList progress preserved.")
            break

        status = "COMPLETED" if (total_eps and curr_ep_to_play >= total_eps) else "CURRENT"
        update_progress(token, media_id, curr_ep_to_play, status=status)
        total_display = f"/{total_eps}" if total_eps else ""
        print(f"\n✓ Episode {curr_ep_to_play}{total_display} finished!")
        print(f"✓ AniList synchronized: {title_search} -> Episode {curr_ep_to_play}{total_display} [{status}]")

        if status == "COMPLETED":
            print(f"\n🎉 Completed watching '{title_search}'!")
            sequel_node, reason = find_sequel(media_id, token=token)
            if not sequel_node:
                if reason:
                    print(f"\n{reason}")
                break

            sequel_id = sequel_node["id"]
            sequel_rom = (sequel_node.get("title") or {}).get("romaji") or ""
            sequel_eng = (sequel_node.get("title") or {}).get("english") or sequel_rom
            sequel_title = sequel_eng or sequel_rom
            sequel_total = sequel_node.get("episodes")
            sequel_total_display = str(sequel_total) if sequel_total else "?"

            # Clobber guard: check existing list entry
            existing_entry = get_media_list_entry(token, viewer["id"], sequel_id)
            existing_progress = (existing_entry.get("progress") or 0) if existing_entry else 0
            if existing_entry and existing_entry.get("status") == "COMPLETED":
                print(f"\nSequel '{sequel_title}' already completed — nothing to roll over.")
                break

            if existing_progress > 0:
                start_ep = existing_progress + 1
            else:
                start_ep = 1

            accepted = False
            if autoplay:
                accepted = True
            else:
                prompt_msg = (
                    f"\nFinished '{title_search}'. Sequel '{sequel_title}' found "
                    f"({sequel_total_display} episodes). Add to Watching and continue with Episode {start_ep}? [y/N]: "
                )
                choice = input(prompt_msg).strip().lower()
                if choice in ("y", "yes"):
                    accepted = True

            if not accepted:
                break

            # Enroll or update status
            if existing_entry and existing_progress > 0:
                if existing_entry.get("status") != "CURRENT":
                    update_progress(token, sequel_id, existing_progress, status="CURRENT")
            else:
                update_progress(token, sequel_id, 0, status="CURRENT")

            if autoplay:
                print(f"\n▶ Autoplaying sequel '{sequel_title}' Episode {start_ep} in 3 seconds...")
                time.sleep(3)

            # Switch loop context to the sequel
            media_id = sequel_id
            total_eps = sequel_total
            total_eps_str = sequel_total_display
            title_search = sequel_rom or sequel_eng
            display_part = f"[00/{total_eps_str}] {sequel_eng} | {sequel_rom}"
            curr_ep_to_play = start_ep
            continue

        if autoplay:
            print(f"▶ Autoplaying Episode {curr_ep_to_play + 1} in 3 seconds...")
            time.sleep(3)
            curr_ep_to_play += 1
        else:
            next_choice = (
                input(f"\nPress Enter to play Episode {curr_ep_to_play + 1} (or 'q' to exit): ").strip().lower()
            )
            if next_choice in ("q", "quit", "exit"):
                break
            curr_ep_to_play += 1


def main() -> None:
    subcommands = {"login", "list", "set", "import-netflix", "watch"}

    parser = argparse.ArgumentParser(
        prog="ani-cli-sync",
        description="ani-cli-sync: Automated AniList synchronization wrapper for ani-cli.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # login
    subparsers.add_parser("login", help="Authenticate with AniList")

    # list
    subparsers.add_parser("list", help="List currently watching anime from AniList")

    # set
    set_parser = subparsers.add_parser("set", help="Set episode progress for an anime on AniList")
    set_parser.add_argument("title", help="Anime title")
    set_parser.add_argument("episode", type=int, help="Watched episode number")

    # import-netflix
    import_parser = subparsers.add_parser("import-netflix", help="Import watch history from Netflix CSV")
    import_parser.add_argument("csv_path", help="Path to NetflixViewingHistory.csv")
    import_parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the planned progress to AniList instead of only previewing it",
    )

    # watch
    watch_parser = subparsers.add_parser("watch", help="Watch an anime and sync progress")
    for p in (parser, watch_parser):
        p.add_argument("-q", "--quality", help="Specify video quality (e.g. 1080p, 720p, best)")
        p.add_argument(
            "-a",
            "--autoplay",
            action="store_true",
            help="Automatically play subsequent episodes without prompting",
        )
        p.add_argument("--no-skip", action="store_true", help="Disable ani-skip intro skipping")
        p.add_argument("--dub", action="store_true", help="Play dubbed version")
        p.add_argument(
            "--sub-primary",
            default=os.environ.get("ANI_CLI_SYNC_SUB_PRIMARY", "de"),
            help="Primary subtitle language (default: de)",
        )
        p.add_argument(
            "--sub-secondary",
            default=os.environ.get("ANI_CLI_SYNC_SUB_SECONDARY", None),
            help="Secondary subtitle language on demand (e.g. en, zh-pinyin; default: disabled)",
        )
        p.add_argument(
            "--no-sub-fallback",
            action="store_true",
            help="Disable automated subtitle synthesis/fallback and use native ani-cli tracks",
        )
        p.add_argument(
            "--uncensored",
            dest="uncensored",
            action=argparse.BooleanOptionalAction,
            default=os.environ.get("ANI_CLI_SYNC_UNCENSORED", "1").lower() in ("1", "true", "yes"),
            help="Prefer uncensored/AT-X/Blu-ray releases when available (default: true, disable with --no-uncensored)",
        )
        p.add_argument(
            "--sub-delay",
            type=float,
            default=float(os.environ.get("ANI_CLI_SYNC_SUB_DELAY", "0") or 0),
            help=(
                "Shift subtitle timing in seconds; negative pulls subs earlier (default: 0). "
                "Measure per episode: whether subs are dub-timed varies episode to episode "
                "within one release, so a value tuned on one episode can mis-time the next."
            ),
        )
        p.add_argument(
            "--sub-sync",
            choices=("off", "auto"),
            default=os.environ.get("ANI_CLI_SYNC_SUB_SYNC", "off"),
            help=(
                "Measure this episode's subtitle offset and apply it automatically (default: off). "
                "Requires the optional subsync extra: uv tool install \"ani-cli-sync[subsync]\". "
                "Uses a neural VAD because energy-based detection locks onto the music bed "
                "under an anime narration. Reports instead of shifting when unsure. An explicit "
                "--sub-delay always takes precedence."
            ),
        )
    watch_parser.add_argument("query", nargs="?", default=None, help="Optional anime title to watch directly")

    args_list = sys.argv[1:]
    has_subcommand = any(arg in subcommands for arg in args_list if not arg.startswith("-"))
    if not has_subcommand and not any(arg in ("-h", "--help") for arg in args_list):
        args_list.insert(0, "watch")

    args = parser.parse_args(args_list)

    if args.command == "login":
        cmd_login()
    elif args.command == "list":
        cmd_list()
    elif args.command == "set":
        cmd_set(args.title, args.episode)
    elif args.command == "import-netflix":
        cmd_import_netflix(args.csv_path, apply=args.apply)
    elif args.command == "watch":
        cmd_watch(
            query=args.query,
            skip_intro=not args.no_skip,
            dub=args.dub,
            quality=args.quality,
            autoplay=args.autoplay,
            sub_primary=args.sub_primary,
            sub_secondary=args.sub_secondary,
            no_sub_fallback=args.no_sub_fallback,
            uncensored=args.uncensored,
            sub_delay=args.sub_delay,
            sub_sync=args.sub_sync,
        )
    else:
        cmd_watch(uncensored=args.uncensored, sub_delay=args.sub_delay, sub_sync=args.sub_sync)


if __name__ == "__main__":
    main()
