#!/usr/bin/env python3
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
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

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
                raise RuntimeError(f"AniList API error: {'; '.join(messages)}")
            except Exception:
                raise RuntimeError(f"AniList HTTP {e.code}: {err_body}")


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
    except Exception:
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
        except Exception:
            pass

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
    except Exception:
        pass

    if not media:
        media = search_anime(title)

    if not media:
        print(f"Error: Anime '{title}' not found on AniList.", file=sys.stderr)
        sys.exit(1)

    media_id = media["id"]
    display_title = media["title"]["english"] or media["title"]["romaji"]
    total_episodes = media.get("episodes")
    status = "COMPLETED" if (total_episodes and episode >= total_episodes) else "CURRENT"
    update_progress(token, media_id, episode, status=status)
    total_str = str(total_episodes) if total_episodes else "?"
    print(f"✓ Updated AniList: {display_title} -> Episode {episode}/{total_str} [{status}]")


def cmd_import_netflix(csv_path: str) -> None:
    """Import viewing history from a Netflix CSV file into AniList."""
    import csv

    token = get_token()
    if not token:
        print("Not logged in. Run 'ani-cli-sync login' first.", file=sys.stderr)
        sys.exit(1)

    path = Path(csv_path).expanduser().resolve()
    if not path.is_file():
        print(f"Error: File not found at {path}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning Netflix viewing history from {path}...")
    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        entries_by_show: dict[str, list[tuple[str, str]]] = {}
        for row in reader:
            if not row:
                continue
            title, date = row[0], row[1]
            parts = [p.strip() for p in title.split(":")]
            show_name = parts[0]
            entries_by_show.setdefault(show_name, []).append((title, date))

    # Curated anime list mapping from Netflix names to AniList search
    anime_whitelist = [
        "Sousou no Frieren",
        "Dungeon Meshi",
        "Jujutsu Kaisen",
        "PLUTO",
        "Cyberpunk: Edgerunners",
        "Dorohedoro",
        "KonoSuba: God's Blessing on This Wonderful World!",
        "Mushoku Tensei: Jobless Reincarnation",
        "VINLAND SAGA",
        "Castlevania",
        "Blue Eye Samurai",
        "Uncle from Another World",
    ]

    for anime_name in anime_whitelist:
        matching_key = None
        for key in entries_by_show:
            if key.lower() in anime_name.lower() or anime_name.lower() in key.lower():
                matching_key = key
                break

        if not matching_key:
            continue

        items = entries_by_show[matching_key]
        media = search_anime(anime_name)
        if not media:
            continue

        display_name = media["title"]["english"] or media["title"]["romaji"]
        total_episodes = media["episodes"]
        watched_count = len(items)
        if total_episodes and watched_count >= total_episodes:
            status = "COMPLETED"
            progress = total_episodes
        else:
            status = "CURRENT"
            progress = watched_count

        update_progress(token, media["id"], progress, status=status)
        total_str = str(total_episodes) if total_episodes else "?"
        print(f"  ✓ {display_name}: {progress}/{total_str} [{status}]")
        time.sleep(1.0)

    print("\n✓ Netflix viewing history successfully imported to AniList!")


def cmd_watch(
    query: str | None = None,
    skip_intro: bool = True,
    dub: bool = False,
    quality: str | None = None,
    autoplay: bool = False,
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
        subprocess.run(args)
        return

    viewer = get_viewer(token)
    entries = get_watching_list(token, viewer["id"])
    if not entries:
        print("Your Currently Watching list on AniList is empty.")
        print("Starting ani-cli search...")
        cmd = ["ani-cli"]
        if skip_intro:
            cmd.append("--skip")
        if dub:
            cmd.append("--dub")
        if quality:
            cmd.extend(["-q", quality])
        subprocess.run(cmd)
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
        # Check if season offset is needed (e.g. Frieren Season 2 numbered 29-38 on AniDB)
        search_arg = title_search
        ep_arg = curr_ep_to_play
        if "Season 2" in display_part and "Frieren" in display_part and ep_arg <= 10:
            ep_arg = ep_arg + 28  # Map 1 -> 29

        print(f"\n▶ Launching ani-cli for '{search_arg}' Episode {ep_arg}...")
        cmd = ["ani-cli", "--exit-after-play"]
        if skip_intro:
            cmd.append("--skip")
        if dub:
            cmd.append("--dub")
        if quality:
            cmd.extend(["-q", quality])
        cmd.extend(["-e", str(ep_arg), search_arg])

        ret = subprocess.run(cmd)

        if ret.returncode == 0:
            status = "COMPLETED" if (total_eps and curr_ep_to_play >= total_eps) else "CURRENT"
            update_progress(token, media_id, curr_ep_to_play, status=status)
            total_display = f"/{total_eps}" if total_eps else ""
            print(f"\n✓ Episode {curr_ep_to_play}{total_display} finished!")
            print(f"✓ AniList synchronized: {title_search} -> Episode {curr_ep_to_play}{total_display} [{status}]")

            if status == "COMPLETED":
                print(f"\n🎉 Completed watching '{title_search}'!")
                break

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
        else:
            break


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
        cmd_import_netflix(args.csv_path)
    elif args.command == "watch":
        cmd_watch(
            query=args.query,
            skip_intro=not args.no_skip,
            dub=args.dub,
            quality=args.quality,
            autoplay=args.autoplay,
        )
    else:
        cmd_watch()


if __name__ == "__main__":
    main()
