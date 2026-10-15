# Design: Series Context Anchoring and Dynamic Batch Glossary Injection

## Architecture

Terminology harmonization is realized through a lightweight, zero-dependency 3-step pipeline within `src/ani_cli_sync/subtitles.py`:

```
prepare_subtitles(anime_title)
   │
   ▼
translate_cues_llm(cues, target_lang, anime_title=anime_title)
   │
   ├── 1. Resolve Series Glossary:
   │      get_series_glossary(anime_title, target_lang)
   │      - Built-in canonical mappings (e.g., Attack on Titan, Frieren)
   │      - Merged with ~/.config/ani-cli/glossary.json (user overrides take precedence)
   │
   └── 2. For each batch (50 cues):
          extract_active_glossary(batch, glossary)
          - Case-insensitive substring/word-boundary check
          - Selects only the 1-5 terms actually present in batch
          - Injects "Active Glossary: {term: translation}" into system prompt
          - Adds inflection rule: "Inflect terms naturally for German grammar"
```

## Component Design

### 1. `get_series_glossary(anime_title: str | None, target_lang: str) -> dict[str, str]`
- Returns a normalized dictionary mapping source phrases (e.g. `"ODM gear"`, `"Survey Corps"`) to target canonical translations (e.g. `"3D-Manöver-Apparat"`, `"Aufklärungstrupp"`).
- Uses case-folded keys for matching while preserving canonical target casing.
- Reads `Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ani-cli" / "glossary.json"` if present and merges show entries.

### 2. `extract_active_glossary(batch: list[VTTCue], glossary: dict[str, str]) -> dict[str, str]`
- Joins all lines in the batch into a single search string.
- Scans glossary terms with word-boundary or regex matching (`re.search(r"\b" + re.escape(term) + r"\b", text, re.IGNORECASE)`).
- Returns only matching pairs.

### 3. Prompt Builder Updates
- In `_build_translation_payload` / system prompt construction:
  - If `anime_title` is provided: `Anime series: "{anime_title}".`
  - If `active_glossary`:
    `Active Terminology Glossary:\n` + JSON or formatted list +
    `\nStrictly adhere to this glossary, inflecting grammatically as required for natural German dialogue (e.g., case declension).`
