# vtt-cue-sanitization Specification

## Purpose
Streaming anime subtitle tracks from free CDNs often contain unrendered HTML/VTT styling markup, voice identifiers, ruby annotations, HTML character entities, and zero-width unicode control artifacts that corrupt translation pipelines and visual playback.

## Requirements

### Requirement: Strip Formatting and Styling Tags

The subtitle ingestion pipeline SHALL remove WebVTT styling, class, voice, ruby, and HTML formatting tags from cue dialogue lines while preserving the enclosed readable textual content.

#### Scenario: Stripping class and voice tags
- WHEN a WebVTT cue contains `<c.yellow>Wait for me!</c>` and `<v Eren>Attack!</v>`
- THEN the sanitized cue lines contain `Wait for me!` and `Attack!` without opening or closing markup tags.

#### Scenario: Stripping ruby annotations
- WHEN a cue contains `<ruby>超大型巨人<rt>ちょうおおがたきょじん</rt></ruby>`
- THEN the ruby annotation tags and phonetics are stripped leaving only the base textual content `超大型巨人`.

### Requirement: Unescape HTML Entities

The subtitle parser SHALL decode standard HTML character entities into their corresponding Unicode characters before feeding dialogue to translation or display.

#### Scenario: Unescaping named and numeric entities
- WHEN a cue contains `Attack &amp; Defense &quot;Wall Maria&quot; &lt;Safe&gt;`
- THEN the cue is decoded to `Attack & Defense "Wall Maria" <Safe>`.

### Requirement: Strip Invisible Control Characters

The parser SHALL remove zero-width spaces, directional marks, and byte-order markers embedded within cue dialogue lines.

#### Scenario: Removing zero-width artifacts
- WHEN a cue contains `\u200bSecret\u200e \u200fMessage`
- THEN the resulting cue dialogue is cleaned to `Secret Message`.

### Requirement: Prune Empty Cues After Sanitization

The parser SHALL drop cues whose dialogue lines become completely empty or whitespace-only after sanitization tags are stripped.

#### Scenario: Dropping empty tag-only cue
- WHEN a WebVTT block consists only of `<c.invisible></c>` or blank lines
- THEN the resulting cue list does not include this empty cue.

#### Scenario: Preserving legitimate punctuation
- WHEN a cue contains legitimate math or emoji punctuation like `<3` or `x < y`
- THEN the text is preserved without being treated as an HTML tag.
