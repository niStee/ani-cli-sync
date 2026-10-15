# Design: WebVTT Cue Sanitization

## Architecture

Sanitization is executed during VTT parsing (`parse_vtt`) in `src/ani_cli_sync/subtitles.py`.
This guarantees that:
1. Downstream translation (`translate_cues_llm`) receives clean plain text strings without markup.
2. Formatted VTT output (`format_vtt`) and local cached subtitles (`~/.cache/ani-cli/subtitles/`) render without visual markup artifacts in `mpv`.
3. Upstream cue timestamps (`VTTCue.timing`) remain strictly untouched.

## Component Design

### 1. Tag Stripping RegEx

We define regex patterns targeting:
- Ruby annotations: `<rt>.*?</rt>` removed entirely first (since ruby reading aids shouldn't merge into text), then `<ruby>` and `</ruby>` stripped.
- General WebVTT/HTML tags: `</?(?:c(?:\.[a-zA-Z0-9_-]+)*|v(?:\s+[^>]+)?|[biu]|span|div|p)(?:\s+[^>]*)?>` or `<[^>]+>`.
  To avoid corrupting mathematical expressions like `1 < 2` or `<3`, we match recognized HTML/WebVTT tag names or bounded closing tags.

### 2. Entity Decoding

Standard library `html.unescape` is used to convert `&amp;`, `&quot;`, `&lt;`, `&gt;`, `&nbsp;`, `&#39;`, etc. into proper Unicode.

### 3. Unicode Control Character Cleaning

Regex translation table or pattern:
`[\u200B-\u200D\u200E\u200F\uFEFF]` removed.

### 4. Integration into `parse_vtt`

In `parse_vtt`, each raw cue line is processed through `sanitize_cue_text(line)`.
Lines that are empty after stripping are pruned; if all lines of a cue are empty, the cue is omitted from the parsed result.
