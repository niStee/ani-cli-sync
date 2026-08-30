# Changelog

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
