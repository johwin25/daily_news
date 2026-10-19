"""Check the visible report and diagnostic paths without network access."""
import json
import tempfile
import unittest
from pathlib import Path

from news_report import render_summary


class ReportTests(unittest.TestCase):
    def test_untrusted_report_is_escaped_and_still_marked_as_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "run_status.json").write_text(json.dumps({
                "status": "completed_with_evidence_shortfall",
            }))
            (folder / "briefing.txt").write_text(
                'UNVERIFIED DRAFT LEADS\n</pre><script>alert("test")</script>'
            )
            summary = render_summary(folder)
            self.assertIn("UNVERIFIED DRAFT LEADS", summary)
            self.assertNotIn("<script>", summary)
            self.assertIn("&lt;/pre&gt;", summary)

    def test_failure_and_missing_status_are_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.assertIn("No run status", render_summary(folder))
            (folder / "run_status.json").write_text(json.dumps({
                "status": "failed", "stage": "shortlisting",
                "error": "invalid_or_incomplete_model_json",
            }))
            summary = render_summary(folder)
            self.assertIn("Pipeline failed", summary)
            self.assertIn("shortlisting", summary)
            self.assertIn("invalid_or_incomplete_model_json", summary)


if __name__ == "__main__":
    unittest.main()
