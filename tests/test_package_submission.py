import unittest

from package_submission import derive_submission_name, resolve_submission_name


class SubmissionNameTests(unittest.TestCase):
    def manifest(self, model, effort, mcp_version):
        return {
            "run_meta": {
                "model": model,
                "reasoning_effort": effort,
                "mcp_version": mcp_version,
            }
        }

    def test_fable_mcp_name_is_automatic(self):
        manifest = self.manifest("claude-fable-5-1", "medium", "0.3.83")
        self.assertEqual(
            derive_submission_name(manifest),
            "build123d-mcp-0.3.83-fable-5.1-medium",
        )

    def test_agy_effort_suffix_is_not_repeated(self):
        manifest = self.manifest("gemini-3.7-flash-high", "high", "0.3.83")
        self.assertEqual(
            derive_submission_name(manifest),
            "build123d-mcp-0.3.83-gemini-3.7-flash-high",
        )

    def test_no_mcp_run_is_labeled_direct(self):
        manifest = self.manifest("claude-opus-5", "xhigh", "none")
        self.assertEqual(
            derive_submission_name(manifest),
            "build123d-direct-opus-5-xhigh",
        )

    def test_manual_suffix_may_follow_full_identity(self):
        manifest = self.manifest("claude-fable-5-1", "medium", "0.3.83")
        requested = "build123d-mcp-0.3.83-fable-5.1-medium-smoke6"
        self.assertEqual(resolve_submission_name(manifest, requested), requested)

    def test_manual_name_cannot_hide_stack(self):
        manifest = self.manifest("claude-fable-5-1", "medium", "0.3.83")
        with self.assertRaisesRegex(ValueError, "invalid --name"):
            resolve_submission_name(manifest, "pzfreo")

    def test_manual_suffix_must_be_filename_safe(self):
        manifest = self.manifest("claude-fable-5-1", "medium", "0.3.83")
        with self.assertRaisesRegex(ValueError, "lowercase letters"):
            resolve_submission_name(
                manifest,
                "build123d-mcp-0.3.83-fable-5.1-medium/other",
            )

    def test_missing_provenance_cannot_be_packaged(self):
        with self.assertRaisesRegex(ValueError, "run_meta.json"):
            derive_submission_name({})


if __name__ == "__main__":
    unittest.main()
