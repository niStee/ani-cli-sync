# Proposal: VTT Cue Ingestion Sanitizer

## Why

Streaming provider WebVTT subtitle tracks frequently contain non-standard markup, styling tags (e.g., `<c.color>`, `<ruby>`, `<rt>`, `<v Speaker>`), HTML entities (`&amp;`, `&nbsp;`), and invisible unicode artifacts (zero-width spaces `\u200b`, directional marks `\u200e`).

When passed to LLM translation backends, these tags cause severe anti-patterns codified in ADR-001 (Decision 1): models attempt to translate CSS class names (e.g., translating `<c.yellow>` to `<c.gelb>`), drop tags unpredictably, or fracture multi-line cue alignment. Furthermore, unhandled tags render as literal visual artifacts in `mpv`.

## What

Implement automated ingestion sanitization for WebVTT subtitle tracks:
- Strip WebVTT formatting and class tags (`<c.*>`, `</c>`, `<v.*>`, `</v>`, `<ruby>`, `<rt>`, `<b>`, `<i>`, `<u>`) while preserving inner dialogue text.
- Decode HTML entities (`&amp;`, `&quot;`, `&lt;`, `&gt;`, `&nbsp;`, `&#39;`).
- Strip zero-width and directional control characters (`\u200b`, `\u200c`, `\u200d`, `\u200e`, `\u200f`, `\ufeff`).
- Omit cues that become completely empty after sanitization.
- Integrate into the subtitle ingestion pipeline so both translation and final output render clean dialogue.

## Out of Scope

- Rewriting or altering subtitle timestamps (`00:01:23.456 --> 00:01:25.789`).
- ASS/SSA styling conversions or complex karaoke animation preservation.
- Modifying audio extraction or VAD synchronization logic.
