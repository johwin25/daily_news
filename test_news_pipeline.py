"""Synthetic end-to-end pipeline and conservative evidence-gate tests."""
import copy
import io
import json
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from urllib.parse import parse_qs, urlparse

from news_contracts import ContractError
from news_pipeline import (
    PipelineError, build_briefing, run_pipeline, search_google_news,
)
from test_news_collector import NOW, article
from test_news_editor import assessment, records, shortlist


def candidate_bundle():
    return {"feed_errors": [], "records": records(), "feed_count": 4,
            "expected_feed_count": 4, "collected_at": NOW.isoformat()}


def no_search_results(query):
    return [], Counter(), "https://news.google.com/rss/search"


class PipelineTests(unittest.TestCase):
    def run_synthetic(self, folder, **changes):
        args = {
            "output_root": folder, "now": NOW,
            "collector": Mock(return_value=candidate_bundle()),
            "shortlister": Mock(return_value=shortlist()),
            "searcher": Mock(side_effect=no_search_results),
            "assessor": Mock(return_value=assessment()),
        }
        args.update(changes)
        with redirect_stdout(io.StringIO()):
            result = run_pipeline(**args)
        return result, args

    def test_end_to_end_writes_auditable_outputs_and_never_pads(self):
        with tempfile.TemporaryDirectory() as folder:
            result, args = self.run_synthetic(folder)
            self.assertEqual(result["items"], [])
            self.assertEqual(result["confirmed_count"], 0)
            self.assertEqual(result["shortfall_count"], 3)
            self.assertEqual(len(result["review_queue"]), 1)
            self.assertEqual(result["review_queue"][0]["status"], "insufficient_evidence")
            args["shortlister"].assert_called_once()
            args["assessor"].assert_called_once()
            args["searcher"].assert_called_once()
            destination = Path(folder) / "2026-10-19"
            for name in ("candidates", "shortlist", "evidence", "assessment",
                         "briefing", "run_status", "contracts"):
                self.assertTrue((destination / (name + ".json")).exists())
            report = (destination / "briefing.txt").read_text()
            self.assertIn("UNVERIFIED DRAFT LEADS", report)
            self.assertIn("SYNTHETIC", report)
            self.assertEqual(len(result["review_queue"][0]["sources"]), 2)

    def test_copied_wire_headlines_never_count_as_independent_confirmation(self):
        rows = records()
        report = build_briefing(
            shortlist(rows), assessment(rows), {"records": rows}, NOW
        )
        self.assertEqual(report["items"], [])
        self.assertIn("possible_copied_or_syndicated_headline",
                      report["review_queue"][0]["exclusion_reasons"])
        self.assertIn("reporting_independence_unestablished",
                      report["review_queue"][0]["exclusion_reasons"])

    def test_conflicting_claims_are_flagged_and_not_published(self):
        proposal = assessment()
        claim = proposal["events"][0]["claims"][0]
        claim["proposed_status"] = "disputed"
        claim["evidence"][1]["relationship"] = "contradicts"
        with tempfile.TemporaryDirectory() as folder:
            result, _ = self.run_synthetic(
                folder, assessor=Mock(return_value=proposal)
            )
            self.assertEqual(result["items"], [])
            self.assertIn("model_reports_conflicting_headlines",
                          result["review_queue"][0]["exclusion_reasons"])

    def test_model_cannot_claim_a_new_evidence_type_into_confirmation(self):
        rows = records()
        rows[0]["content_scope"] = "invented_full_article"
        rows[0]["independence"] = "independent"
        result = build_briefing(shortlist(rows), assessment(rows), {"records": rows}, NOW)
        self.assertEqual(result["items"], [])
        self.assertIn("unsupported_evidence_type",
                      result["review_queue"][0]["exclusion_reasons"])

    def test_partial_or_empty_collection_fails_before_any_model_call(self):
        bundles = [
            {"feed_errors": [{"category": "World"}], "records": records()},
            {"feed_errors": [], "records": []},
        ]
        for bundle in bundles:
            with tempfile.TemporaryDirectory() as folder:
                model = Mock()
                with self.assertRaises(PipelineError):
                    self.run_synthetic(
                        folder, collector=Mock(return_value=bundle), shortlister=model
                    )
                model.assert_not_called()
                output = json.loads(
                    (Path(folder) / "2026-10-19" / "briefing.json").read_text()
                )
                self.assertEqual(output["items"], [])

    def test_invalid_citations_fail_closed_and_retain_safe_status(self):
        bad = shortlist()
        bad["events"][0]["source_ids"] = ["src_fabricated"]
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(PipelineError):
                self.run_synthetic(folder, shortlister=Mock(return_value=bad))
            status = json.loads(
                (Path(folder) / "2026-10-19" / "run_status.json").read_text()
            )
            self.assertEqual(status["stage"], "shortlisting")
            self.assertEqual(status["error"], "unknown_or_duplicate_source_id")

    def test_failed_search_stays_visible_without_blocking_a_draft(self):
        with tempfile.TemporaryDirectory() as folder:
            result, _ = self.run_synthetic(
                folder, searcher=Mock(side_effect=TimeoutError("private exception"))
            )
            self.assertEqual(result["items"], [])
            data = json.loads(
                (Path(folder) / "2026-10-19" / "evidence.json").read_text()
            )
            self.assertEqual(data["searches"][0]["status"], "search_failed")
            self.assertNotIn("private exception", json.dumps(data))

    def test_failed_rerun_removes_stale_success_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            self.run_synthetic(folder)
            with self.assertRaises(PipelineError):
                self.run_synthetic(
                    folder, collector=Mock(side_effect=RuntimeError("private detail"))
                )
            destination = Path(folder) / "2026-10-19"
            self.assertFalse((destination / "briefing.txt").exists())
            self.assertFalse((destination / "assessment.json").exists())
            status = json.loads((destination / "run_status.json").read_text())
            self.assertEqual(status["error"], "unexpected_pipeline_failure")
            self.assertNotIn("private detail", json.dumps(status))

    def test_empty_shortlist_skips_second_model_call(self):
        with tempfile.TemporaryDirectory() as folder:
            assessor = Mock()
            result, args = self.run_synthetic(
                folder, shortlister=Mock(return_value={"events": []}),
                assessor=assessor,
            )
            assessor.assert_not_called()
            args["searcher"].assert_not_called()
            self.assertEqual(result["review_queue"], [])
            self.assertEqual(result["items"], [])

    def test_followup_sources_are_fresh_filtered_and_cited_from_registry(self):
        extra = article(
            url="https://news.google.com/follow-up", publisher="Associated Press",
            publisher_url="https://apnews.com",
            title="SYNTHETIC: New material researchers report further findings",
        )
        with tempfile.TemporaryDirectory() as folder:
            result, _ = self.run_synthetic(
                folder,
                searcher=Mock(return_value=([extra], Counter(), "https://news.google.com/rss/search")),
            )
            data = json.loads(
                (Path(folder) / "2026-10-19" / "evidence.json").read_text()
            )
            self.assertEqual(len(data["records"]), 3)
            self.assertEqual(len(data["event_sources"]["event_1"]), 3)
            self.assertEqual(result["items"], [])

    def test_search_text_cannot_change_host_or_execute_commands(self):
        query = 'https://evil.example/ $(secret) &q=override'
        response = MagicMock(status=200)
        response.read.return_value = b"<rss><channel/></rss>"
        with patch("news_pipeline.urlopen") as opener:
            opener.return_value.__enter__.return_value = response
            search_google_news(query)
        url = urlparse(opener.call_args.args[0].full_url)
        self.assertEqual(url.hostname, "news.google.com")
        self.assertEqual(parse_qs(url.query)["q"], [query + " when:2d"])


if __name__ == "__main__":
    unittest.main()
