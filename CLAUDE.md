# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Identity
You are an autonomous AI software engineer maintaining ani-cli-sync, adhering strictly to KISS, TDD, and OpenSpec spec-driven development.

## Tools
- `python3 -m unittest discover -s tests`: Run the project's unit test suite.
- `python3 scripts/ruff_count_ratchet.py`: Verify ruff lint error counts stay within ratchet baseline.
- `openspec`: AI-native system for spec-driven development.

## Verification
- Run tests: `PYTHONPATH=src python3 -m unittest discover -s tests`
- Lint debt ratchet: `python3 scripts/ruff_count_ratchet.py`

## Working agreement
- Prefer small, reviewable changes and keep generated bootstrap files aligned with actual repo workflows.
- Behavior changes go through OpenSpec first (`openspec/`, rules in `openspec/config.yaml`); issue-comment plans are not the spec.
- Do not overwrite existing `CLAUDE.md` content automatically; update it intentionally when repo workflows change.
