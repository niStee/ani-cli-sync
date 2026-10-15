# Proposal: Series Context Anchoring and Dynamic Batch Glossary Injection

## Why

Currently, `translate_cues_llm` translates subtitle cues with a static, series-blind system prompt. Because the model has no awareness of which anime it is translating, and because batches are processed independently, character names, franchise-specific acronyms, and military branches drift unpredictably across episodes and batches (e.g., in Attack on Titan, "ODM gear" alternating between "ODM-Ausrüstung", "3D-Manöver-Apparat", and untranslated text; "Survey Corps" alternating between "Aufklärungstrupp" and "Erkundungskorps").

Codifying ADR-001 (Decision 7), this change introduces series context anchoring and dynamic glossary injection to eliminate cross-episode terminology drift without incurring token bloat or latency stalls.

## What Changes

- Thread `anime_title` from `prepare_subtitles` into `translate_cues_llm` and `_translate_single_batch`.
- Anchor the LLM system prompt with the series title (`Anime series: "<anime_title>"`).
- Provide a built-in canonical glossary for prominent anime (starting with Attack on Titan canonical terms like ODM gear $\to$ 3D-Manöver-Apparat, Survey Corps $\to$ Aufklärungstrupp, Garrison $\to$ Mauergarnison, Military Police $\to$ Militärpolizei), with support for user overrides in `~/.config/ani-cli/glossary.json`.
- Implement dynamic batch filtering (`extract_active_glossary`) to inject only the terms that appear in the current cue batch into the active prompt.
- Instruct the model to inflect target terms naturally according to German grammatical cases rather than inserting rigid strings verbatim.

## Out of Scope

- Offline full-script multi-agent RAG vector databases.
- Automated extraction of new terminology via external search engines.
- Modifying subtitle timings or VTT cue parsing rules.
