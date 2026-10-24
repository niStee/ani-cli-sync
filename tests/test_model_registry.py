"""Guard: every default translation cascade member is a registered model handle.

The local LiteLLM gateway fails closed on a handle that is not declared in
ai-infra's ``home/dot_config/litellm/model-governance.json``. A dead handle in
the cascade is invisible until the cascade is exercised, which only happens on
a quota exhaustion of the primary model.

These tests pin the property offline, against the vendored registry, so CI
needs no running proxy.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ani_cli_sync.model_registry import (
    RETIRED_MODELS,
    TRANSLATION_MODELS,
    is_registered,
    is_retired,
)
from ani_cli_sync.subtitles import DEFAULT_FALLBACK_MODELS, get_candidate_models


class TestDefaultCascadeMembersAreRegistered(unittest.TestCase):
    """The default cascade may only contain registered handles."""

    def test_every_default_member_is_registered(self):
        for model in DEFAULT_FALLBACK_MODELS:
            with self.subTest(model=model):
                self.assertTrue(
                    is_registered(model),
                    f"{model!r} is not in the vendored model registry; the gateway "
                    f"fails closed on an undeclared handle",
                )

    def test_no_retired_handle_reappears_in_the_cascade(self):
        for model in DEFAULT_FALLBACK_MODELS:
            with self.subTest(model=model):
                self.assertFalse(
                    is_retired(model),
                    f"{model!r} is a retired handle: {RETIRED_MODELS.get(model, '')}",
                )

    def test_default_cascade_has_no_duplicates(self):
        self.assertEqual(
            len(DEFAULT_FALLBACK_MODELS),
            len(set(DEFAULT_FALLBACK_MODELS)),
            "a duplicated cascade member wastes a failover attempt",
        )

    def test_default_cascade_is_not_empty(self):
        """An empty cascade would skip translation entirely."""
        self.assertGreater(len(DEFAULT_FALLBACK_MODELS), 0)


class TestRegistryDetectionHasANegativeCase(unittest.TestCase):
    """Pin the guard's own detection.

    A guard that cannot fail is not a guard (ai-infra ADR-012). These cases
    prove the registry actually rejects a handle it does not know, so a
    vacuous pass is impossible.
    """

    def test_unknown_handle_is_detected_as_unregistered(self):
        self.assertFalse(is_registered("not-a-real-model-handle"))

    def test_unknown_handle_is_not_detected_as_retired(self):
        self.assertFalse(is_retired("not-a-real-model-handle"))

    def test_known_handle_is_detected_as_registered(self):
        self.assertTrue(is_registered("minimax-m3"))

    def test_removed_handle_would_be_caught(self):
        """Inject a retired handle into the cascade and prove it is caught.

        This is the sensitivity probe for the guard, expressed as a test: if
        the detection were removed, this case would no longer fail.
        """
        broken = ("minimax-m3", "gemini-2.5-flash")
        caught = [m for m in broken if not is_registered(m) or is_retired(m)]
        self.assertEqual(
            caught,
            ["gemini-2.5-flash"],
            "the guard must flag a retired handle",
        )


class TestRegistryCascadeResolution(unittest.TestCase):
    """The resolved cascade and the declared constant must agree."""

    def test_resolved_default_matches_the_declared_constant(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(tuple(get_candidate_models()), DEFAULT_FALLBACK_MODELS)

    def test_every_registered_translation_model_has_a_note(self):
        for model, meta in TRANSLATION_MODELS.items():
            with self.subTest(model=model):
                self.assertTrue(meta.get("note"), f"{model!r} has no recorded note")

    def test_retired_models_carry_a_reason(self):
        for model, reason in RETIRED_MODELS.items():
            with self.subTest(model=model):
                self.assertTrue(reason.strip(), f"{model!r} has no retirement reason")


if __name__ == "__main__":
    unittest.main()
