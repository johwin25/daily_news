import unittest
from news_public_export import export_briefing

class ExtendedEditionTests(unittest.TestCase):
    def test_seven_short_unverified_headlines(self):
        source={"date_utc":"2026-10-24","pipeline_status":"completed_with_evidence_shortfall",
                "confirmed_count":0,"items":[],"review_queue":[]}
        candidates={"records":[{"title":f"Article {i}","url":f"https://news.example/{i}",
                                "publisher":"Example","categories":["World"],
                                "title_fingerprint":str(i)} for i in range(15)]}
        result=export_briefing(source,candidates)
        self.assertEqual(len(result["additional_headlines"]),7)
        self.assertTrue(all(x["status"]=="unverified_headline" for x in result["additional_headlines"]))
        self.assertEqual(result["items"],[])

    def test_no_duplicate_primary_source(self):
        source={"date_utc":"2026-10-24","pipeline_status":"completed_with_evidence_shortfall",
                "confirmed_count":0,"items":[],"review_queue":[
                {"status":"insufficient_evidence","working_headline":"Primary",
                 "sources":[{"url":"https://news.example/0","publisher":"Example","title":"Primary"}]}]}
        candidates={"records":[{"title":"Primary","url":"https://news.example/0","publisher":"Example"},
                               {"title":"Secondary","url":"https://news.example/1","publisher":"Example"}]}
        result=export_briefing(source,candidates)
        self.assertEqual(len(result["additional_headlines"]),1)
        self.assertEqual(result["additional_headlines"][0]["headline"],"Secondary")

    def test_no_headlines_on_failed_run(self):
        result=export_briefing({"date_utc":"2026-10-24","pipeline_status":"failed"},
                              {"records":[{"title":"X","url":"https://example.org/x"}]})
        self.assertEqual(result["additional_headlines"],[])
