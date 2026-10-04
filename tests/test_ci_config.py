from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestAgenticReviewGateConfig(unittest.TestCase):
    """The `Require Approvals` ruleset asks for 1 approving review, and GitHub forbids
    self-approval, so CodeRabbit is the only actor that can satisfy it. That only works
    while `request_changes_workflow` is enabled, so its removal must fail CI."""

    def setUp(self):
        self.config = REPO_ROOT / ".coderabbit.yaml"

    def test_coderabbit_config_exists(self):
        self.assertTrue(
            self.config.is_file(),
            ".coderabbit.yaml is missing; CodeRabbit cannot approve and the "
            "Require Approvals ruleset becomes unsatisfiable",
        )

    def test_request_changes_workflow_is_enabled(self):
        content = self.config.read_text(encoding="utf-8")
        match = re.search(r"^\s*request_changes_workflow:\s*(\S+)\s*$", content, re.MULTILINE)
        self.assertIsNotNone(
            match,
            "reviews.request_changes_workflow is absent, so CodeRabbit only comments "
            "and never approves",
        )
        self.assertEqual(
            match.group(1),
            "true",
            "reviews.request_changes_workflow must be true for CodeRabbit to approve",
        )

    def test_request_changes_workflow_is_under_reviews_key(self):
        content = self.config.read_text(encoding="utf-8")
        self.assertRegex(
            content,
            r"(?m)^reviews:\s*$",
            "request_changes_workflow must be nested under the top-level 'reviews' key",
        )


if __name__ == "__main__":
    unittest.main()