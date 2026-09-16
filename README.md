# ani-cli-sync

<p align="left">
  <a href="https://github.com/niStee/ani-cli-sync/releases"><img src="https://img.shields.io/github/v/release/niStee/ani-cli-sync?style=flat&logo=github&color=blue" alt="Latest Release"></a>
  <a href="https://github.com/niStee/ani-cli-sync/actions/workflows/ci.yml"><img src="https://github.com/niStee/ani-cli-sync/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI Pipeline"></a>
  <a href="https://scorecard.dev/viewer/?uri=github.com/niStee/ani-cli-sync"><img src="https://api.scorecard.dev/projects/github.com/niStee/ani-cli-sync/badge" alt="OpenSSF Scorecard"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="https://img.shields.io/badge/Dependencies-0%20(Standard%20Library)-success"><img src="https://img.shields.io/badge/Dependencies-0%20(Standard%20Library)-success" alt="Zero Dependencies"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=flat" alt="License: MIT"></a>
</p>

> **Automated AniList synchronization wrapper for [`ani-cli`](https://github.com/pystardust/ani-cli).**

`ani-cli-sync` bridges the gap between your local terminal anime player and your [AniList](https://anilist.co) profile. It provides an interactive `fzf` menu of your active watchlist, automatically launches `ani-cli` at the next unwatched episode, skips intros seamlessly, and updates your progress on AniList upon completion.

---

## ✨ Features

- 📺 **Interactive Watchlist Menu**: Loads your `Currently Watching` list directly from AniList via GraphQL.
- ⚡ **Auto-Resume & Progression**: Automatically calculates `progress + 1` and plays the correct next episode.
- 🔄 **Real-Time AniList Sync**: Updates episode progress and auto-transitions completed shows to `COMPLETED`.
- 🔁 **Continuous Autoplay**: Stream multiple episodes continuously with `--autoplay` / `-a`.
- ⏭️ **Intro Skipping**: Built-in `ani-skip` integration (can be disabled via `--no-skip`).
- 🔞 **Uncensored / AT-X / Blu-ray Preference**: Automatically prioritizes uncensored, AT-X, or Blu-ray cuts over censored TV broadcast releases with zero-prompt menu interception (configurable via `--uncensored` / `--no-uncensored` or `ANI_CLI_SYNC_UNCENSORED`).
- 💬 **Automated Dual-Subtitles & Fallback**: Automatically detects missing or forced-only tracks (e.g. 8-cue signs-only German tracks) and synthesizes synchronized German dialogue (bottom) and Traditional Chinese with Hanyu Pinyin (top) via local LiteLLM proxy with zero-latency disk caching.
- 🎯 **Smart Disambiguation**: Resolves multi-season naming quirks (e.g. AniDB absolute episode offsets) and matches active watchlist entries over global searches.
- 📥 **Netflix Import**: Easily import watch history from a `NetflixViewingHistory.csv` export.
- 📦 **Zero External Python Dependencies**: Built entirely using the Python standard library.

---

## 📋 Prerequisites

- **Python**: `>= 3.10`
- **[`ani-cli`](https://github.com/pystardust/ani-cli)**: Required for streaming and playback.
- **[`mpv`](https://mpv.io)**: Video player (used by `ani-cli`).
- **[`fzf`](https://github.com/junegunn/fzf)**: *(Optional, recommended)* For interactive fuzzy menus.
- **[`ani-skip`](https://github.com/synacktraa/ani-skip)**: *(Optional)* For automatic opening/ending intro skipping.

---

## 🚀 Installation

### Using `uv` (Recommended)

```bash
uv tool install git+https://github.com/niStee/ani-cli-sync.git
```

### Using `pipx`

```bash
pipx install git+https://github.com/niStee/ani-cli-sync.git
```

### Using `pip`

```bash
git clone https://github.com/niStee/ani-cli-sync.git
cd ani-cli-sync
pip install .
```

---

## 🔑 1-Minute AniList Setup

Authenticate `ani-cli-sync` with your AniList account:

```bash
ani-cli-sync login
```

1. Open [AniList Developer Settings](https://anilist.co/settings/developer).
2. Click **Create New Client**:
   - **Name**: `ani-cli-sync`
   - **Redirect URL**: `https://anilist.co/api/v2/oauth/pin`
3. Paste your generated **Client ID** when prompted to open the authorization URL in your browser.
4. Copy the generated access token from the URL fragment and paste it into the CLI.

Token is saved with `0600` permissions at `~/.config/anilist/token`.

---

## 📖 Usage

### Watch Anime (Interactive or Query)

```bash
# Interactive fzf picker of Currently Watching shows
ani-cli-sync

# Watch with continuous autoplay for binge-watching
ani-cli-sync -a

# Jump directly to a show in your watchlist
ani-cli-sync frieren
ani-cli-sync "Cyberpunk: Edgerunners" -q 1080p --dub
```

### View Active Watchlist

```bash
ani-cli-sync list
```

```text
=== Currently Watching (myusername) ===
  [03/10] Cyberpunk: Edgerunners
  [02/12] Dorohedoro
  [01/13] Uncle from Another World
  [04/10] Frieren: Beyond Journey’s End Season 2
```

### Manually Set Progress

```bash
# Updates active watchlist entries first before falling back to global search
ani-cli-sync set "Frieren" 4
```

### Import Netflix History

Export your viewing history from Netflix (`NetflixViewingHistory.csv`) and import:

```bash
ani-cli-sync import-netflix ~/Downloads/NetflixViewingHistory.csv
```

---

## ⚙️ CLI Reference

```text
usage: ani-cli-sync [-h] [-q QUALITY] [-a] [--no-skip] [--dub]
                    [--sub-primary SUB_PRIMARY]
                    [--sub-secondary SUB_SECONDARY] [--no-sub-fallback]
                    {login,list,set,import-netflix,watch} ...

ani-cli-sync: Automated AniList synchronization wrapper for ani-cli.

positional arguments:
  {login,list,set,import-netflix,watch}
    login               Authenticate with AniList
    list                List currently watching anime from AniList
    set                 Set episode progress for an anime on AniList
    import-netflix      Import watch history from Netflix CSV
    watch               Watch an anime and sync progress

options:
  -h, --help            show this help message and exit
  -q, --quality QUALITY
                        Specify video quality (e.g. 1080p, 720p, best)
  -a, --autoplay        Automatically play subsequent episodes without prompting
  --no-skip             Disable ani-skip intro skipping
  --dub                 Play dubbed version
  --sub-primary SUB_PRIMARY
                        Primary subtitle language (default: de, env: ANI_CLI_SYNC_SUB_PRIMARY)
  --sub-secondary SUB_SECONDARY
                        Secondary subtitle language on demand (e.g. zh-pinyin; default: stream English or none, env: ANI_CLI_SYNC_SUB_SECONDARY)
  --no-sub-fallback     Disable automated subtitle synthesis/fallback and use native ani-cli tracks
  --uncensored, --no-uncensored
                        Prefer uncensored/AT-X/Blu-ray releases when available (default: true, disable with --no-uncensored, env: ANI_CLI_SYNC_UNCENSORED)
```

---

## 🔞 Uncensored / AT-X / Blu-ray Release Prioritization

When scrapers (e.g. HiAnime) host multiple cuts of an anime series (e.g. censored TV broadcast vs. uncensored AT-X broadcast or Blu-ray release), standard `ani-cli` prompts interactively via `fzf` or picks the first entry (which is almost always the censored TV cut).

`ani-cli-sync` transparently hooks into `ani-cli`'s menu protocol:
1. **Automated Interception**: When `ani-cli` queries the scraper, `ani-cli-sync` passes an automated menu selector script via `ANI_CLI_MENU`.
2. **Title Normalization & Sibling Grouping**: Normalizes anime titles (stripping season noise and brackets) and isolates sibling cuts matching the exact season/show being watched.
3. **Keyword Matching**: Scans candidates for release tags including `uncensored`, `at-x`, `bd`, `blu-ray`, `bluray`, and `unrated`. If an uncensored release exists, it is selected automatically in **< 1ms** without blocking or waiting for user input.
4. **Transparent Graceful Fallback**: If an anime has no uncensored release (such as standard mainstream shonen shows like *Slime* or *Frieren*), it automatically selects the canonical release without error.
5. **Configurability**: Enabled by default; can be disabled with `--no-uncensored` or `export ANI_CLI_SYNC_UNCENSORED=0`.

---

## 💬 Automated Dual-Subtitles & Fallback Architecture

When watching anime, provider subtitle tracks are frequently incomplete (e.g. German dub tracks containing only 8 "forced" signs cues rather than full dialogue, or CJK tracks completely absent from Western Crunchyroll rips).

`ani-cli-sync` features a battle-tested automated fallback and dual-sub pipeline:

1. **Track Density Validation (Forced vs. Dialogue)**: Inspects candidate stream subtitles. Any track with `< 50` cues is flagged as a forced signs-only track and bypassed for dialogue.
2. **Deterministic Stream Sync**: Uses the stream's full English WebVTT track directly from the HLS manifest as the structural foundation, guaranteeing **0ms timing drift** and matching intro/outro cuts without slow audio-correlation alignment.
3. **Optimized Concurrent Translation**:
   - **Primary Subtitle (`--sid=1`, bottom)**: Natural, localized German dialogue translated via the local LiteLLM proxy (`deepseek-v4-flash`).
   - **Secondary Subtitle (`--secondary-sid=2`, top)**:
     - By default, falls back directly to the stream's English track with **0s translation latency**.
     - **On-demand CJK learning track** (`--sub-secondary zh-pinyin` / `ANI_CLI_SYNC_SUB_SECONDARY=zh-pinyin`): Generates two-line cues with context-accurate Hanyu Pinyin with tone marks (resolving *duōyīnzì* polyphones like 銀行 *háng* vs. 行走 *xíng*) on top and Traditional Chinese (繁體中文) on bottom.
4. **Lookahead Background Prefetching**: When Episode $N$ begins playback, a background daemon thread quietly pre-fetches and prepares subtitles for Episode $N+1$. When you finish the episode, the next episode launches with **0s wait time**.
5. **Local Disk Caching**: Generated files are stored at `~/.cache/ani-cli/subtitles/{anime_slug}_ep{ep}_{lang}.vtt`. Subsequent viewings yield a **0.0003s instant cache hit**.
6. **Clean Player Integration**: Passes all tracks to `mpv` along with the original stream English track, allowing seamless on-the-fly track switching (`k` / `Alt+j`).

---

## 🔄 Sequel Rollover

When you finish the final episode of a season, `ani-cli-sync` automatically queries AniList for the next released TV or ONA sequel:

- **Interactive Mode**: Prompts before enrolling:
  ```text
  Finished 'That Time I Got Reincarnated as a Slime Season 2 Part 2'. Sequel 'That Time I Got Reincarnated as a Slime Season 3' found (24 episodes). Add to Watching and continue with Episode 1? [y/N]:
  ```
- **Autoplay Mode (`-a` / `--autoplay`)**: Automatically enrolls the sequel in `CURRENT` and continues playing seamlessly.
- **Clobber Guard**: If you already have progress on the sequel (e.g. paused at episode 5), `ani-cli-sync` preserves your progress and resumes at episode 6 rather than resetting to episode 1.
- **Safety Rails**: If sequels are unreleased (`NOT_YET_RELEASED`) or ambiguous (multiple TV/ONA sequels), it stops cleanly without making unwanted mutations.

---

## 🔢 Multi-Season Episode Offsets

Some scraper backends (e.g. gogoanime via AniDB) use **absolute continuous episode numbering** across
seasons, while AniList resets to episode 1 for each season entry. `ani-cli-sync` translates AniList
episode numbers to the scraper episode numbers using a strict 3-tier precedence:

1. **Explicit Override Table (`_EPISODE_OFFSETS`)**: Hand-curated overrides always take priority and can specify custom search titles.
2. **Computed PREQUEL-Chain Offsets**: Dynamically queries AniList's relation graph, traversing preceding `TV`/`ONA` seasons and summing episode counts (with cycle detection, depth limits, and ambiguity guards).
3. **Identity Fallback**: Default 1-to-1 numbering when no override exists and the show has no preceding seasons.

| Show / Season | AniList episodes | Scraper episodes | Offset |
|---|---|---|---|
| Frieren: Beyond Journey's End Season 2 | 1–10 | 29–38 | +28 |
| That Time I Got Reincarnated as a Slime Season 2 | 1–12 | 1–12 | +0 |
| That Time I Got Reincarnated as a Slime Season 2 Part 2 | 1–12 | 1–12 | +0 |
| That Time I Got Reincarnated as a Slime Season 3 | 1–24 | 1–24 | +0 |
| That Time I Got Reincarnated as a Slime Season 4 | 1–24 | 1–24 | +0 |

> **Adding a static override**: open `src/ani_cli_sync/cli.py` and append a tuple to `_EPISODE_OFFSETS`.
> Standard multi-season anime are automatically handled via PREQUEL chain computation without requiring table additions.

---

## 🛠️ Troubleshooting

### Show missing from the fzf picker

The anime is not in `CURRENT` status on AniList. Check with:

```bash
ani-sync list
```

Reset it with the **AniList episode number** (not the scraper/AniDB number):

```bash
# Frieren S2: AniList ep 1 = scraper ep 29
ani-sync set "Frieren: Beyond Journey's End Season 2" 1
```

### `set` returns "episode exceeds total"

You passed an absolute scraper episode. Subtract the offset from the table above to get the
correct AniList episode number. Example: scraper ep 29 − offset 28 = AniList ep 1.

### Show accidentally marked COMPLETED

Use `set` with any episode `< total` — this re-opens it as `CURRENT`:

```bash
ani-sync set "Frieren: Beyond Journey's End Season 2" 1
```

---

## 📄 License

Distributed under the [MIT License](LICENSE).
