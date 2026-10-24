# Changelog

## [0.9.1](https://github.com/niStee/ani-cli-sync/compare/ani-cli-sync-v0.9.0...ani-cli-sync-v0.9.1) (2026-10-24)


### Bug Fixes

* **subtitles:** replace dead model handles in the translation cascade ([#93](https://github.com/niStee/ani-cli-sync/issues/93)) ([d457ed3](https://github.com/niStee/ani-cli-sync/commit/d457ed391ffa2004ae1c41f9ea8006fb11006697))
* **sync:** anchor Slime Season 2 Part 2 offset table entries to franchise titles ([#83](https://github.com/niStee/ani-cli-sync/issues/83)) ([341461a](https://github.com/niStee/ani-cli-sync/commit/341461a55ad168ab1f54658d3a5f0de7cd426bd7))

## [0.9.0](https://github.com/niStee/ani-cli-sync/compare/ani-cli-sync-v0.8.0...ani-cli-sync-v0.9.0) (2026-10-16)


### Features

* **subtitles:** add dynamic character metadata and active entity extraction (RAL) ([#79](https://github.com/niStee/ani-cli-sync/issues/79)) ([40c459f](https://github.com/niStee/ani-cli-sync/commit/40c459fdd54a1d5031a322184aadc36b1cab45f8))
* **subtitles:** add generic masculine convention and morphological glossary articles ([#80](https://github.com/niStee/ani-cli-sync/issues/80)) ([90f92b7](https://github.com/niStee/ani-cli-sync/commit/90f92b7a52d27d09d40885ec0f446c2ee73f0056))
* **subtitles:** add Romaji series aliasing, character profiles, and cleft avoidance ([#78](https://github.com/niStee/ani-cli-sync/issues/78)) ([b394189](https://github.com/niStee/ani-cli-sync/commit/b3941891fc87e44163c0b54038cd09997e1a51d8))
* **subtitles:** add series context anchoring and dynamic batch glossary injection ([#75](https://github.com/niStee/ani-cli-sync/issues/75)) ([38163e3](https://github.com/niStee/ani-cli-sync/commit/38163e3588ec739ae16251e1b504b38b33772577))
* **subtitles:** add WebVTT cue ingestion sanitizer and tag stripper ([#73](https://github.com/niStee/ani-cli-sync/issues/73)) ([080c716](https://github.com/niStee/ani-cli-sync/commit/080c716de328fffda8af08e04d859a35ebd221b9))


### Bug Fixes

* **subtitles:** keep timings client-side, bisect on batch count mismatch ([#65](https://github.com/niStee/ani-cli-sync/issues/65)) ([08df017](https://github.com/niStee/ani-cli-sync/commit/08df0177f40312ace600b3fb69ae3ac026daac5e)), closes [#64](https://github.com/niStee/ani-cli-sync/issues/64)
* **subtitles:** normalize &lt;br&gt; tags to prevent libass bold rendering bug ([#77](https://github.com/niStee/ani-cli-sync/issues/77)) ([4e772dc](https://github.com/niStee/ani-cli-sync/commit/4e772dc54af4627b7fd5b6bbc35188c9b9a2b8f7))
* **subtitles:** unblock German translation (non-reasoning model + real abort) ([#61](https://github.com/niStee/ani-cli-sync/issues/61)) ([76690b2](https://github.com/niStee/ani-cli-sync/commit/76690b20a023729b8b9f66a9859ce3c0330bde44))


### Documentation

* **openspec:** archive series-context-and-glossary to canonical specs ([#76](https://github.com/niStee/ani-cli-sync/issues/76)) ([39c8876](https://github.com/niStee/ani-cli-sync/commit/39c887656eac11c32d142ba97f75a767070154c8))
* **subtitles:** record the translation model default and its measurements ([#63](https://github.com/niStee/ani-cli-sync/issues/63)) ([c06bbf7](https://github.com/niStee/ani-cli-sync/commit/c06bbf7042a780e59a4c1ec530f6141f92c413d1))

## [0.8.0](https://github.com/niStee/ani-cli-sync/compare/ani-cli-sync-v0.7.0...ani-cli-sync-v0.8.0) (2026-10-05)


### Features

* **sub-sync:** opt-in per-episode subtitle offset measurement + autoplay stop fix ([#59](https://github.com/niStee/ani-cli-sync/issues/59)) ([bff13d1](https://github.com/niStee/ani-cli-sync/commit/bff13d19691ac781054c84676e61ce51b90d8375))
* **subtitles:** add --sub-delay to shift subs for dub-timed tracks on JP audio ([#49](https://github.com/niStee/ani-cli-sync/issues/49)) ([7de8679](https://github.com/niStee/ani-cli-sync/commit/7de867967da533ba4a99b4f4fb27de95d6f9089c))


### Bug Fixes

* **subtitles:** select subtitle tracks by label, not by the provider's uniform lang ([#50](https://github.com/niStee/ani-cli-sync/issues/50)) ([cdffa39](https://github.com/niStee/ani-cli-sync/commit/cdffa394521cc4db5c6de79b64dafc2472113b56))
* **watch:** autoplay + query falls back to global AniList search instead of dying on non-tty fzf ([#48](https://github.com/niStee/ani-cli-sync/issues/48)) ([8661256](https://github.com/niStee/ani-cli-sync/commit/866125654d56201b8c1421fa05ecb7a27a0b58ed))


### Documentation

* **subtitles:** correct --sub-delay guidance -- the offset is per-episode, not per-show ([#57](https://github.com/niStee/ani-cli-sync/issues/57)) ([05d1561](https://github.com/niStee/ani-cli-sync/commit/05d156194ae718acf61afcba943349e93031f382))
* **subtitles:** mark the ep2 offset playback-verified at 0 ([#58](https://github.com/niStee/ani-cli-sync/issues/58)) ([d19069a](https://github.com/niStee/ani-cli-sync/commit/d19069a4dcab72bdce677442cb80230ee68cfc71))

## [0.7.0](https://github.com/niStee/ani-cli-sync/compare/ani-cli-sync-v0.6.0...ani-cli-sync-v0.7.0) (2026-09-16)


### Features

* **stream:** add automated two-pass probe fallback for episode offsets ([#46](https://github.com/niStee/ani-cli-sync/issues/46)) ([bacb35d](https://github.com/niStee/ani-cli-sync/commit/bacb35dca22593f7480a7c1e6e2635b92c84efca))
* **stream:** prioritize uncensored/AT-X/Blu-ray cuts with automated menu selector ([#43](https://github.com/niStee/ani-cli-sync/issues/43)) ([3a3ffd3](https://github.com/niStee/ani-cli-sync/commit/3a3ffd38fe5ef38d186fcb8fc2409b99b7a99a48))

## [0.6.0](https://github.com/niStee/ani-cli-sync/compare/ani-cli-sync-v0.5.0...ani-cli-sync-v0.6.0) (2026-09-14)


### Features

* **subtitles:** make secondary subtitles on demand and add background prefetching ([#42](https://github.com/niStee/ani-cli-sync/issues/42)) ([ab99b7e](https://github.com/niStee/ani-cli-sync/commit/ab99b7e0499f0d796083877cbf9702513e46242e))


### Bug Fixes

* **subtitles:** handle null skip metadata and separate mpv script-opts-append flags ([#40](https://github.com/niStee/ani-cli-sync/issues/40)) ([a878d5f](https://github.com/niStee/ani-cli-sync/commit/a878d5f826feb8a9cbf048e8155461a15e53df12))

## [0.5.0](https://github.com/niStee/ani-cli-sync/compare/ani-cli-sync-v0.4.2...ani-cli-sync-v0.5.0) (2026-09-14)


### Features

* **subtitles:** add automated fallback and dual-subtitles pipeline ([#39](https://github.com/niStee/ani-cli-sync/issues/39)) ([51d0994](https://github.com/niStee/ani-cli-sync/commit/51d099457696895f7b224c901ea0d80a1c8ca9f3))


### Bug Fixes

* **offsets:** add Slime Season 4 table entry with 0 offset ([#35](https://github.com/niStee/ani-cli-sync/issues/35)) ([30845a6](https://github.com/niStee/ani-cli-sync/commit/30845a6f03c5c77707fef0cc0efb592c8bd7212f))


### Documentation

* pointer to fleet auto-merge policy (ai-infra AUTOMERGE.md) ([#37](https://github.com/niStee/ani-cli-sync/issues/37)) ([da0fb1f](https://github.com/niStee/ani-cli-sync/commit/da0fb1fde4d69e0b3412495de98c7b9d8260cae4))

## [0.4.2](https://github.com/niStee/ani-cli-sync/compare/ani-cli-sync-v0.4.1...ani-cli-sync-v0.4.2) (2026-09-13)


### Bug Fixes

* **offsets:** update Slime offsets to 0 for ani-cli 5.1.0 hianime provider ([#33](https://github.com/niStee/ani-cli-sync/issues/33)) ([8b736a6](https://github.com/niStee/ani-cli-sync/commit/8b736a6fc7301413792195140cea6b72a65a04cd))

## [0.4.1](https://github.com/niStee/ani-cli-sync/compare/ani-cli-sync-v0.4.0...ani-cli-sync-v0.4.1) (2026-09-09)


### Documentation

* align AGENTS.md topology with fleet canonical standard ([#30](https://github.com/niStee/ani-cli-sync/issues/30)) ([22d500b](https://github.com/niStee/ani-cli-sync/commit/22d500b843395d7ae4f1016db50aa910037434e9))

## [0.4.0](https://github.com/niStee/ani-cli-sync/compare/ani-cli-sync-v0.3.2...ani-cli-sync-v0.4.0) (2026-08-30)


### Features

* **sync:** sequel rollover on completion + PREQUEL-chain computed episode offsets ([0fb7d96](https://github.com/niStee/ani-cli-sync/commit/0fb7d96fa447f7039ebf963c1e293f34b7e8e103))

## [0.3.2](https://github.com/niStee/ani-cli-sync/compare/ani-cli-sync-v0.3.1...ani-cli-sync-v0.3.2) (2026-08-28)


### Bug Fixes

* **sync:** add Slime Season 3 continuous episode offsets ([#23](https://github.com/niStee/ani-cli-sync/issues/23)) ([b99f0f2](https://github.com/niStee/ani-cli-sync/commit/b99f0f2759e4655156e2f53555723a4ac793f7c4))

## [0.3.1](https://github.com/niStee/ani-cli-sync/compare/ani-cli-sync-v0.3.0...ani-cli-sync-v0.3.1) (2026-08-26)


### Bug Fixes

* **hardening:** guard cmd_set clobber, data-driven offset table, fix gql_query exception chain ([#16](https://github.com/niStee/ani-cli-sync/issues/16)) ([6b1e72c](https://github.com/niStee/ani-cli-sync/commit/6b1e72c))


### Documentation

* add multi-season episode offset table and AniList troubleshooting guide ([#16](https://github.com/niStee/ani-cli-sync/issues/16)) ([6b1e72c](https://github.com/niStee/ani-cli-sync/commit/6b1e72c))

## [0.3.0](https://github.com/niStee/ani-cli-sync/compare/ani-cli-sync-v0.2.0...ani-cli-sync-v0.3.0) (2026-08-20)


### Features

* **playback:** detect early quit to preserve AniList progress and stop autoplay loop ([#15](https://github.com/niStee/ani-cli-sync/issues/15)) ([dc44ad9](https://github.com/niStee/ani-cli-sync/commit/dc44ad99102660d0fb2f546971e6c63e46cd2e60))
* **sync:** add continuous episode offset mapping for Slime Season 2 ([#14](https://github.com/niStee/ani-cli-sync/issues/14)) ([3d738b1](https://github.com/niStee/ani-cli-sync/commit/3d738b1a8d3e2b8b3df9269acf6facdeb13175ee))


### Documentation

* align README badge ribbon with project standards ([#11](https://github.com/niStee/ani-cli-sync/issues/11)) ([acb42ee](https://github.com/niStee/ani-cli-sync/commit/acb42eeec48aef5bea5eeb3db98aaa2f009c708e))
* remove private mirror badge from public README ([#13](https://github.com/niStee/ani-cli-sync/issues/13)) ([153f893](https://github.com/niStee/ani-cli-sync/commit/153f89385deb43d6754cad7a0390016ffefc7c75))

## [0.2.0](https://github.com/niStee/ani-cli-sync/compare/ani-cli-sync-v0.1.0...ani-cli-sync-v0.2.0) (2026-08-19)


### Features

* initial commit for ani-cli-sync ([6894c9b](https://github.com/niStee/ani-cli-sync/commit/6894c9bd1d1581efdb72613a90ff03d3d6b66326))


### Bug Fixes

* **ci:** fix release-please, gitleaks, scorecard, and semgrep workflows ([#6](https://github.com/niStee/ani-cli-sync/issues/6)) ([8d0af3c](https://github.com/niStee/ani-cli-sync/commit/8d0af3c6edaa70e31a55a0812d81f9ddced71725))
* **security:** move nosemgrep annotation inline on urlopen call ([#8](https://github.com/niStee/ani-cli-sync/issues/8)) ([44e5923](https://github.com/niStee/ani-cli-sync/commit/44e5923f933d38f5a07a83eb3166d4d324cdf92d))
* **security:** use nosemgrep suppression on gql urlopen call ([#9](https://github.com/niStee/ani-cli-sync/issues/9)) ([669b8f1](https://github.com/niStee/ani-cli-sync/commit/669b8f1ec4c999cb832e4b1226ffb40f29a79134))


### Documentation

* add AGENTS.md ([#1](https://github.com/niStee/ani-cli-sync/issues/1)) ([1fa36d6](https://github.com/niStee/ani-cli-sync/commit/1fa36d67e3e2ac7b0db64be01a5b17fcd31ce272))
* add CONTRIBUTING.md guidelines ([#5](https://github.com/niStee/ani-cli-sync/issues/5)) ([e281f64](https://github.com/niStee/ani-cli-sync/commit/e281f64b86784dd1d2df43b0cc5241cda354bdcb))
