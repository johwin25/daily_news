import unittest
from news_public_export import export_briefing


class PublicExportTests(unittest.TestCase):
    def test_removes_raw_claims_and_evidence(self):
        result = export_briefing({
            "date_utc": "2026-10-24",
            "pipeline_status": "completed_with_evidence_shortfall",
            "confirmed_count": 0, "items": [],
            "review_queue": [{
                "status": "insufficient_evidence",
                "working_headline": "A test story",
                "draft_summary": "An unverified summary",
                "claims": [{"private": "large raw evidence"}],
                "sources": [{"publisher": "Publisher", "title": "Title", "url": "https://example.org/story",
                             "article": {"text": "RAW ARTICLE TEXT"}}],
            }],
        })
        self.assertEqual(result["items"], [])
        self.assertNotIn("claims", str(result))
        self.assertNotIn("RAW ARTICLE TEXT", str(result))
        self.assertEqual(result["review_queue"][0]["sources"][0]["url"], "https://example.org/story")

    def test_rejects_promotion(self):
        with self.assertRaises(ValueError):
            export_briefing({"date_utc":"2026-10-24","pipeline_status":"completed_with_evidence_shortfall",
                             "confirmed_count":1,"items":[{"headline":"X"}],"review_queue":[]})

    def test_rejects_unknown_status(self):
        with self.assertRaises(ValueError):
            export_briefing({"date_utc":"2026-10-24","pipeline_status":"published","items":[]})

    def test_failure_exports_no_leads(self):
        result = export_briefing({"date_utc":"2026-10-24","pipeline_status":"failed"})
        self.assertEqual(result["review_queue"], [])
