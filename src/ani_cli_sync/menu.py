"""ani_cli_sync.menu: Automated menu selector for ani-cli prioritizing uncensored / AT-X / Blu-ray cuts."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

UNCENSORED_PATTERN = re.compile(
    r"\b(uncensored|at-x|atx|blu-ray|bluray|bd|unrated)\b",
    re.IGNORECASE,
)


def clean_title(title: str) -> str:
    """Strip tags, parentheticals, and normalize whitespace for title comparison."""
    cleaned = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", "", title)
    cleaned = re.sub(r"[^\w\s-]", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def select_candidate(
    lines: list[str],
    target_title: str | None = None,
    uncensored: bool = True,
) -> str | None:
    """Select the best candidate line from an ani-cli menu listing.

    Args:
        lines: List of candidate lines output by ani-cli menu (e.g. "1 High School DxD").
        target_title: Optional title of the anime to match against.
        uncensored: Whether to prioritize uncensored/AT-X/Blu-ray cuts.

    Returns:
        The full selected line or None if lines is empty.
    """
    non_empty = [l.strip() for l in lines if l.strip()]
    if not non_empty:
        return None

    # Parse candidate lines into tuples: (num_str, title_str, full_line)
    candidates: list[tuple[str, str, str]] = []
    for line in non_empty:
        parts = line.split(maxsplit=1)
        if len(parts) == 2 and parts[0].isdigit():
            candidates.append((parts[0], parts[1].strip(), line))
        else:
            candidates.append(("", line, line))

    if not candidates:
        return None

    matched = candidates
    if target_title:
        clean_target = clean_title(target_title)
        # 1. Exact match on normalized title
        exact = [c for c in candidates if clean_title(c[1]) == clean_target]
        if exact:
            matched = exact
        else:
            # 2. Substring match on normalized title
            sub = [c for c in candidates if clean_target in clean_title(c[1])]
            if sub:
                matched = sub
            else:
                # 3. Target might be romaji while candidates are English (or vice versa).
                # Group candidates matching the base title of candidate 0.
                c0_clean = clean_title(candidates[0][1])
                siblings = [c for c in candidates if clean_title(c[1]) == c0_clean]
                if siblings:
                    matched = siblings
    else:
        c0_clean = clean_title(candidates[0][1])
        siblings = [c for c in candidates if clean_title(c[1]) == c0_clean]
        if siblings:
            matched = siblings

    if uncensored:
        for c in matched:
            if UNCENSORED_PATTERN.search(c[1]):
                return c[2]
    else:
        for c in matched:
            if not UNCENSORED_PATTERN.search(c[1]):
                return c[2]

    # Fallback to the first matched candidate
    return matched[0][2]


_HELPER_SCRIPT_CODE = """#!/usr/bin/env python3
import os
import re
import sys

UNCENSORED_PATTERN = re.compile(
    r"\\b(uncensored|at-x|atx|blu-ray|bluray|bd|unrated)\\b",
    re.IGNORECASE,
)

def clean_title(title: str) -> str:
    cleaned = re.sub(r"[\\(\\[\\{][^\\)\\]\\}]*[\\)\\]\\}]", "", title)
    cleaned = re.sub(r"[^\\w\\s-]", "", cleaned)
    return re.sub(r"\\s+", " ", cleaned).strip().lower()

def select_candidate(lines, target_title=None, uncensored=True):
    non_empty = [l.strip() for l in lines if l.strip()]
    if not non_empty:
        return None

    candidates = []
    for line in non_empty:
        parts = line.split(maxsplit=1)
        if len(parts) == 2 and parts[0].isdigit():
            candidates.append((parts[0], parts[1].strip(), line))
        else:
            candidates.append(("", line, line))

    if not candidates:
        return None

    matched = candidates
    if target_title:
        clean_target = clean_title(target_title)
        exact = [c for c in candidates if clean_title(c[1]) == clean_target]
        if exact:
            matched = exact
        else:
            sub = [c for c in candidates if clean_target in clean_title(c[1])]
            if sub:
                matched = sub
            else:
                c0_clean = clean_title(candidates[0][1])
                siblings = [c for c in candidates if clean_title(c[1]) == c0_clean]
                if siblings:
                    matched = siblings
    else:
        c0_clean = clean_title(candidates[0][1])
        siblings = [c for c in candidates if clean_title(c[1]) == c0_clean]
        if siblings:
            matched = siblings

    if uncensored:
        for c in matched:
            if UNCENSORED_PATTERN.search(c[1]):
                return c[2]
    else:
        for c in matched:
            if not UNCENSORED_PATTERN.search(c[1]):
                return c[2]

    return matched[0][2]

def main():
    target = os.environ.get("ANI_CLI_SYNC_TARGET_TITLE")
    uncensored = os.environ.get("ANI_CLI_SYNC_UNCENSORED", "1").lower() in ("1", "true", "yes")
    lines = sys.stdin.read().splitlines()
    selected = select_candidate(lines, target_title=target, uncensored=uncensored)
    if selected:
        print(selected)

if __name__ == "__main__":
    main()
"""


def ensure_menu_helper(cache_dir: Path | None = None) -> tuple[Path, Path]:
    """Ensure the automated ani-cli menu selector and compatibility symlinks exist."""
    if cache_dir is None:
        cache_base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        bin_dir = cache_base / "ani-cli" / "menu_bin"
    else:
        bin_dir = cache_dir

    bin_dir.mkdir(parents=True, exist_ok=True)
    script_path = bin_dir / "ani-cli-menu"

    if not script_path.exists() or script_path.read_text(encoding="utf-8") != _HELPER_SCRIPT_CODE:
        script_path.write_text(_HELPER_SCRIPT_CODE, encoding="utf-8")
        script_path.chmod(0o755)

    # Ensure compatibility symlinks so ani-cli never stalls if it looks for fzf, rofi, or dmenu
    for alias in ("fzf", "rofi", "dmenu"):
        alias_path = bin_dir / alias
        if not alias_path.exists() and not alias_path.is_symlink():
            try:
                alias_path.symlink_to("ani-cli-menu")
            except OSError:
                pass

    return script_path, bin_dir


def prepare_menu_env(
    target_title: str | None = None,
    uncensored: bool = True,
    base_env: dict[str, str] | None = None,
    cache_dir: Path | None = None,
) -> dict[str, str]:
    """Prepare environment variables for running ani-cli with automated menu selection."""
    env = dict(base_env or os.environ)
    script_path, bin_dir = ensure_menu_helper(cache_dir=cache_dir)

    env["ANI_CLI_MENU"] = str(script_path)
    env["ANI_CLI_SYNC_UNCENSORED"] = "1" if uncensored else "0"
    if target_title:
        env["ANI_CLI_SYNC_TARGET_TITLE"] = target_title

    current_path = env.get("PATH", "")
    bin_dir_str = str(bin_dir)
    if bin_dir_str not in current_path.split(os.pathsep):
        env["PATH"] = f"{bin_dir_str}{os.pathsep}{current_path}" if current_path else bin_dir_str

    return env


def main() -> None:
    """CLI entrypoint when invoked as a standalone menu selector."""
    target = os.environ.get("ANI_CLI_SYNC_TARGET_TITLE")
    uncensored = os.environ.get("ANI_CLI_SYNC_UNCENSORED", "1").lower() in ("1", "true", "yes")
    lines = sys.stdin.read().splitlines()
    selected = select_candidate(lines, target_title=target, uncensored=uncensored)
    if selected:
        print(selected)


if __name__ == "__main__":
    main()
