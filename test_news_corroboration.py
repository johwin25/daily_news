"""Publication must require independent attributed support for every claim."""
import copy
import hashlib
import unittest

from news_corroboration import check_event
from news_editor import validate_assessment
from news_pipeline import build_briefing
from test_news_collector import NOW
from test_news_editor import assessment, records, shortlist


def corroborated_fixture():
    rows = records()
    rows[0]["publisher"] = "The Guardian"
    quotes = [
        "Engineer Beta told the Guardian that the specimen withstands 120 cycles.",
        "Dr Alpha told the BBC that the specimen withstands 120 cycles.",
    ]
    for index, row in enumerate(rows):
        text = quotes[index] + " " + " ".join(f"distinct{index}word{n}" for n in range(150))
        row["content_scope"] = "article_text"
        row["article"] = {
            "status": "retrieved", "source_id": row["id"], "text": text,
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "wire_mentions": [],
            "retrieved_url": "https://www.theguardian.com/science/2026/oct/19/sample" if index == 0
                             else "https://www.bbc.com/news/articles/abcdefgh1234",
            "metadata": {"authors": ["Guardian Reporter" if index == 0 else "BBC Journalist"],
                         "person_authors": ["Guardian Reporter" if index == 0 else "BBC Journalist"],
                         "published_at": NOW.isoformat()},
        }
    proposal = assessment(rows)
    proposal["events"][0]["draft_summary"] = "MODEL INVENTION: unsupported extra details."
    for index, citation in enumerate(proposal["events"][0]["claims"][0]["evidence"]):
        citation["scope"] = "article_text"
        citation["quote"] = quotes[index]
    return rows, proposal, shortlist(rows)


class CorroborationTests(unittest.TestCase):
    def decision(self, change=None):
        rows, proposal, selected = corroborated_fixture()
        if change:
            change(rows, proposal)
        return check_event(proposal["events"][0], {r["id"]: r for r in rows}, NOW)

    def test_two_attributed_claims_pass_and_only_checked_claims_are_published(self):
        rows, proposal, selected = corroborated_fixture()
        validate_assessment(proposal, selected, rows, {"event_1": [r["id"] for r in rows]})
        self.assertTrue(self.decision()["passed"])
        result = build_briefing(selected, proposal, {"records": rows}, NOW)
        self.assertEqual(result["confirmed_count"], 1)
        self.assertEqual(result["shortfall_count"], 2)
        self.assertEqual(result["review_queue"], [])
        self.assertNotIn("MODEL INVENTION", result["items"][0]["summary"])
        self.assertEqual(len(result["items"][0]["claims"][0]["support"]), 2)

    def test_one_article_or_headlines_cannot_pass(self):
        def change(rows, proposal):
            proposal["events"][0]["claims"][0]["evidence"].pop()
        self.assertFalse(self.decision(change)["passed"])
        def headline(rows, proposal):
            for citation in proposal["events"][0]["claims"][0]["evidence"]:
                citation["scope"] = "headline"
        self.assertFalse(self.decision(headline)["passed"])

    def test_disputed_claim_blocks_publication(self):
        def change(rows, proposal):
            proposal["events"][0]["claims"][0]["evidence"][0]["relationship"] = "contradicts"
        self.assertFalse(self.decision(change)["passed"])

    def test_shared_authors_wire_attribution_stale_dates_and_corrupt_hashes_block(self):
        def shared(rows, proposal):
            for row in rows:
                row["article"]["metadata"]["authors"] = ["Same Journalist"]
        def wire(rows, proposal):
            rows[0]["article"]["wire_mentions"] = ["Reuters"]
        def stale(rows, proposal):
            rows[0]["article"]["metadata"]["published_at"] = "2020-01-01T00:00:00+00:00"
        def corrupt(rows, proposal):
            rows[0]["article"]["text_sha256"] = "fake"
        for change in (shared, wire, stale, corrupt):
            with self.subTest(change=change.__name__):
                self.assertFalse(self.decision(change)["passed"])

    def test_reporting_attribution_must_be_in_the_actual_claim_quote(self):
        def change(rows, proposal):
            for citation in proposal["events"][0]["claims"][0]["evidence"]:
                citation["quote"] = "the specimen withstands 120 cycles."
        self.assertFalse(self.decision(change)["passed"])

    def test_copied_articles_do_not_count_twice(self):
        def change(rows, proposal):
            text = " ".join(row["article"]["text"] for row in rows)
            for row in rows:
                row["article"]["text"] = text
                row["article"]["text_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        self.assertFalse(self.decision(change)["passed"])

    def test_wrong_publisher_article_url_cannot_pass(self):
        def change(rows, proposal):
            rows[0]["article"]["retrieved_url"] = "https://evil.example/article"
        self.assertFalse(self.decision(change)["passed"])

    def test_second_unsupported_material_claim_holds_the_entire_event(self):
        def change(rows, proposal):
            second = copy.deepcopy(proposal["events"][0]["claims"][0])
            second["proposed_status"] = "insufficient_evidence"
            proposal["events"][0]["claims"].append(second)
        self.assertFalse(self.decision(change)["passed"])


if __name__ == "__main__":
    unittest.main()
