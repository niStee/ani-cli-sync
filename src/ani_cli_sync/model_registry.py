"""Offline registry of LiteLLM model handles that are safe to use as translation
candidates.

The local LiteLLM gateway validates every requested handle against ai-infra's
``home/dot_config/litellm/model-governance.json`` and fails closed on an
undeclared model. A handle that is not registered there never reaches a
provider; it answers HTTP 400 and burns a retry in the failover cascade.

This module vendors the subset of that registry that matters for subtitle
translation, so CI can assert the property without a running proxy. The
gateway remains the runtime authority: a handle listed here can still be
removed from the gateway, and a handle absent here must not enter a cascade.

Keep this list in sync with ai-infra's registry; the live cross-check is::

    curl -s http://localhost:4000/v1/models

See ``AGENTS.md`` -> "Model Governance Contract" for the full rule.
"""

from __future__ import annotations

# Model handles that are registered in ai-infra's model-governance.json at tier
# T2 and have answered the translation workload (50-cue anime dialogue batch).
#
# Entries carry the measurement that qualified them:
#   "seconds"  -- measured wall time for one 50-cue batch (2026-10-24)
#   "backup"   -- True when the gateway holds a same-model fallback deployment
#                 under ADR-006's strict same-model fallback boundary
TRANSLATION_MODELS: dict[str, dict[str, object]] = {
    "minimax-m3": {
        "tier": "T2",
        "seconds": 7.6,
        "backup": True,
        "note": "primary default; Token Plan; ADR-001 non-reasoning model",
    },
    "minimax-m3.1-flash": {
        "tier": "T2",
        "seconds": 15.9,
        "backup": True,
        "note": "secondary fallback; Token Plan",
    },
    "gemini-3.1-flash-lite": {
        "tier": "T2",
        "seconds": 2.9,
        "backup": False,
        "note": "tertiary fallback; fastest; covers shared Token Plan exhaustion",
    },
    "qwen-3.8-flash": {
        "tier": "T2",
        "seconds": 39.6,
        "backup": True,
        "note": "qualified but too slow to sit in front of playback",
    },
    "minimax-m2.7": {
        "tier": "T2",
        "seconds": 31.8,
        "backup": True,
        "note": "qualified but superseded by the M3 generation",
    },
    "minimax-m2.7-highspeed": {
        "tier": "T2",
        "seconds": 29.9,
        "backup": False,
        "note": "qualified but superseded by the M3 generation",
    },
    "gemini-3.6-flash": {
        "tier": "T2",
        "seconds": None,
        "backup": False,
        "note": "HTTP 400 on the translation workload",
    },
    "gemini-3.8-flash": {
        "tier": "T2",
        "seconds": None,
        "backup": False,
        "note": "HTTP 429 quota exhausted on the measurement run",
    },
    "glm-5.3-flash": {
        "tier": "T2",
        "seconds": None,
        "backup": True,
        "note": "exceeded the 45s per-batch socket timeout",
    },
    "deepseek-v4-flash": {
        "tier": "T2",
        "seconds": None,
        "backup": True,
        "note": "reasoning model; stalls a 50-cue batch",
    },
}

# Handles that were used as cascade members and are now dead. They are kept
# as a tombstone so a future change that reintroduces one is caught by the
# guard test rather than shipped again.
RETIRED_MODELS: dict[str, str] = {
    "gemini-2.5-flash": (
        "pruned from the LiteLLM gateway on 2026-07-21 (ai-infra 1f26d7a); "
        "answers HTTP 400"
    ),
    "llm-tower": (
        "never a gateway model handle in the current configuration; the tower's "
        "inference ports do not answer"
    ),
}


def is_registered(model: str) -> bool:
    """Return True when the handle is a registered translation model."""
    return model in TRANSLATION_MODELS


def is_retired(model: str) -> bool:
    """Return True when the handle is a known-dead cascade member."""
    return model in RETIRED_MODELS
