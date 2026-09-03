import unittest

from package_submission import (
    derive_submission_name,
    describe_task_sources,
    resolve_submission_name,
)


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

    def test_fixture_overrides_are_included_in_source_notes(self):
        notes = describe_task_sources(
            {
                "editing": {
                    "fixture_count": 32,
                    "reused": True,
                    "mcp_version": "0.3.84.dev0",
                    "harness_commit": "e7a4cd2c045325091b938e00e2b809f1e30f4c31",
                    "fixture_overrides": [
                        {
                            "fixture_ids": ["202", "240"],
                            "mcp_version": "0.3.84.dev0",
                            "harness_commit": "9276fef1368ecdb869e7ec693298a73803d5aacf",
                            "recognition_policy": "repair-first-then-strict-recognition",
                        }
                    ],
                }
            }
        )
        self.assertEqual(len(notes), 2)
        self.assertIn("Editing fixtures 202,240 overridden", notes[1])
        self.assertIn("repair-first-then-strict-recognition", notes[1])


if __name__ == "__main__":
    unittest.main()
