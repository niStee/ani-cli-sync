# Specification: Series Context Anchoring and Dynamic Glossary Injection

## Purpose

Unanchored subtitle translation pipelines suffer from terminology drift across episodes and batches, causing proper nouns, franchise acronyms, and character titles to alternate between competing translations.

## ADDED Requirements

### Requirement: Series Context Anchoring in Translation Prompt

The subtitle translation engine SHALL inject the anime series title into the system prompt when an anime title is provided.

#### Scenario: Show name present in system prompt
- WHEN translating subtitles for `Attack on Titan`
- THEN the system prompt includes the exact series context `Anime series: "Attack on Titan"`.

#### Scenario: Generic translation when title is absent
- WHEN translating subtitles without an anime title (or when title is None)
- THEN the system prompt falls back to generic anime subtitle instructions without empty title markers.

### Requirement: Dynamic Batch Glossary Injection

The translation pipeline SHALL match series glossary terms against the text of the current cue batch and inject only the matched active terms into the batch prompt.

#### Scenario: Injecting matched terms only
- WHEN translating a batch containing `Equip your ODM gear and follow the Survey Corps!` with an Attack on Titan glossary
- THEN the system prompt includes an active glossary block mapping `ODM gear` to `3D-Manöver-Apparat` and `Survey Corps` to `Aufklärungstrupp`.

#### Scenario: Omitting inactive glossary terms
- WHEN translating a batch that does not contain any glossary terms
- THEN the active glossary block is omitted from the batch prompt to prevent token bloat and hallucinated term insertions.

### Requirement: Grammatical Inflection Compliance

The prompt SHALL explicitly instruct the model to inflect target glossary terms according to the grammar and case of the target language sentence.

#### Scenario: Declension instruction in prompt
- WHEN an active glossary block is present in the prompt
- THEN the prompt specifies that glossary terms MUST be inflected naturally according to German grammatical cases (nominative, accusative, dative, genitive).

### Requirement: Configurable User Glossary Overrides

The glossary resolver SHALL allow users to define or override series-specific term mappings via a local JSON configuration file.

#### Scenario: User glossary override takes precedence
- WHEN a user configures `Survey Corps: Erkundungstrupp` in `~/.config/ani-cli/glossary.json`
- THEN the active glossary uses the user-defined translation `Erkundungstrupp` instead of the built-in default.
