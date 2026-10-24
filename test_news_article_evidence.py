"""Synthetic publisher feeds and article responses; no live requests or key."""
import copy
import hashlib
import unittest
from email.utils import format_datetime
from unittest.mock import Mock

from news_article_evidence import (
    BBC_FEEDS, MAX_ARTICLES, MAX_TEXT_CHARS, headline_key, index_bbc_feeds,
    provenance_signals, resolve_bbc_record, retrieve_article_evidence,
    same_article_headline,
    collect_candidates_with_originals, GUARDIAN_FEEDS,
)
from news_article_reader import ArticleReadError
from news_contracts import ContractError
from news_editor import compare_claims, validate_assessment
from test_news_collector import NOW
from test_news_editor import assessment, records, shortlist

URL = "https://www.bbc.com/news/articles/abcdefgh1234"
BODY = "SYNTHETIC: Scientists published test results after observing the sample. " * 150


def feed(title="SYNTHETIC: Research team publishes new material", url=URL, date=None):
    return ("<rss><channel><item><title>" + title + "</title><link>" + url
            + "</link><pubDate>" + (date or format_datetime(NOW))
            + "</pubDate></item></channel></rss>").encode()


def fake_article(url=URL, title="SYNTHETIC: Research team publishes new material - BBC News"):
    return {"status": "retrieved", "retrieved_url": url, "title": title,
            "text": BODY, "retrieved_at": NOW.isoformat()}


def bundle(rows=None):
    rows = rows or records()
    return {"records": rows, "event_sources": {"event_1": [r["id"] for r in rows]},
            "searches": [], "content_scope": "headline_only"}


def enriched():
    return retrieve_article_evidence(shortlist(), bundle(), NOW,
                                    reader=Mock(return_value=fake_article()),
                                    feed_fetcher=Mock(return_value=feed()))


class ArticleEvidenceTests(unittest.TestCase):
    def test_publisher_originals_are_fresh_bounded_and_replace_duplicate_google_links(self):
        from news_collector import collect_candidates
        base = {"records": records(), "feed_errors": []}
        def fetch(url):
            if url in BBC_FEEDS:
                return feed()
            return feed(title="SYNTHETIC Guardian sample",
                        url="https://www.theguardian.com/science/2026/oct/19/sample")
        result = collect_candidates_with_originals(NOW, collector=Mock(return_value=base),
                                                   feed_fetcher=fetch)
        bbc = [r for r in result["records"] if r["publisher"] == "BBC News"]
        self.assertEqual(len(bbc), 1)
        self.assertEqual(bbc[0]["url"], URL)
        self.assertIn(records()[1]["url"], bbc[0]["collected_alias_urls"])
        self.assertTrue(any(r["publisher"] == "The Guardian" for r in result["records"]))
        self.assertEqual(len(result["publisher_original_feed_status"]), len(BBC_FEEDS)+len(GUARDIAN_FEEDS))

    def test_optional_publisher_feed_failures_keep_original_collection(self):
        base = {"records": records(), "feed_errors": []}
        result = collect_candidates_with_originals(NOW, collector=Mock(return_value=base),
            feed_fetcher=Mock(side_effect=TimeoutError("PRIVATE")))
        self.assertEqual(len(result["records"]), 2)
        self.assertNotIn("PRIVATE", str(result))

    def test_minor_title_edits_are_allowed_but_numbers_and_negation_are_not(self):
        self.assertTrue(same_article_headline(
            "Australian MP's condition improves after alleged car attack",
            "Australian MP Helen Haines' condition improves after alleged car attack"))
        self.assertFalse(same_article_headline(
            "Researchers report 10 positive results in new test",
            "Researchers report 100 positive results in new test"))
        self.assertFalse(same_article_headline(
            "Researchers report positive results in new test",
            "Researchers report no positive results in new test"))

    def test_regional_feed_link_keeps_original_and_same_article_path(self):
        index, _ = index_bbc_feeds(NOW, Mock(return_value=feed(
            url=URL.replace("bbc.com", "bbc.co.uk"))))
        match = next(iter(next(iter(index.values())).values()))
        self.assertEqual(match["url"], URL)
        self.assertEqual(match["feed_article_url"], URL.replace("bbc.com", "bbc.co.uk"))

    def test_google_link_resolves_by_exact_publisher_headline_and_text_is_bounded(self):
        original = bundle()
        reader = Mock(return_value=fake_article())
        result = retrieve_article_evidence(shortlist(), original, NOW,
                                          reader=reader, feed_fetcher=Mock(return_value=feed()))
        self.assertNotIn("article", original["records"][1])
        reader.assert_called_once_with(URL)
        row = result["records"][1]
        article = row["article"]
        self.assertEqual(row["content_scope"], "article_text")
        self.assertEqual(article["source_id"], row["id"])
        self.assertEqual(article["resolution_basis"], "exact_publisher_headline_match")
        self.assertEqual(article["independence"], "unknown")
        self.assertEqual(article["completeness"], "not_established")
        self.assertEqual(article["text_sha256"], hashlib.sha256(article["text"].encode()).hexdigest())
        self.assertLessEqual(len(article["text"]), MAX_TEXT_CHARS)
        self.assertTrue(article["text_truncated"])

    def test_unavailable_feeds_do_not_invent_or_guess_original_links(self):
        reader = Mock()
        result = retrieve_article_evidence(shortlist(), bundle(), NOW,
                                          reader=reader,
                                          feed_fetcher=Mock(side_effect=TimeoutError("PRIVATE")))
        reader.assert_not_called()
        attempt = result["article_retrieval"]["attempts"][0]
        self.assertEqual(attempt["reason"], "original_article_not_in_feeds")
        self.assertNotIn("PRIVATE", str(result))

    def test_ambiguous_titles_are_not_resolved(self):
        row = records()[1]
        key = headline_key(row["title"])
        with self.assertRaisesRegex(ArticleReadError, "ambiguous_original_article"):
            resolve_bbc_record(row, {key: {"/one": {"url": URL}, "/two": {"url": URL}}})

    def test_direct_bbc_link_is_supported_but_other_publishers_are_not(self):
        row = records()[1]
        row["url"] = URL
        self.assertEqual(resolve_bbc_record(row, {})["url"], URL)
        with self.assertRaisesRegex(ArticleReadError, "publisher_reader_not_implemented"):
            resolve_bbc_record(records()[0], {})

    def test_feed_dates_and_original_domains_are_checked(self):
        for raw in (feed(date="Mon, 01 Jan 2024 10:00:00 GMT"),
                    feed(url="https://evil.example/news/articles/abcdefgh"),
                    feed(date="invalid")):
            index, diagnostics = index_bbc_feeds(NOW, Mock(return_value=raw))
            self.assertEqual(index, {})
            self.assertEqual(len(diagnostics), len(BBC_FEEDS))

    def test_changed_title_short_body_and_wrong_final_article_are_rejected(self):
        for change in ({"title": "Different event"}, {"text": "Too short"},
                       {"retrieved_url": URL.replace("abcdefgh1234", "different1234")}):
            article = fake_article()
            article.update(change)
            result = retrieve_article_evidence(shortlist(), bundle(), NOW,
                                              reader=Mock(return_value=article),
                                              feed_fetcher=Mock(return_value=feed()))
            self.assertEqual(result["article_retrieval"]["retrieved_count"], 0)
            self.assertNotIn("article", result["records"][1])

    def test_failed_article_remains_headline_only_without_exception_leak(self):
        result = retrieve_article_evidence(shortlist(), bundle(), NOW,
                                          reader=Mock(side_effect=OSError("PRIVATE")),
                                          feed_fetcher=Mock(return_value=feed()))
        self.assertEqual(result["records"][1]["content_scope"], "headline_only")
        self.assertNotIn("PRIVATE", str(result))

    def test_retrieval_budget_is_enforced(self):
        rows = []
        for i in range(MAX_ARTICLES + 3):
            row = copy.deepcopy(records()[1])
            row["id"] = "src_" + str(i)
            row["url"] = URL
            rows.append(row)
        proposal = shortlist()
        proposal["events"][0]["source_ids"] = [r["id"] for r in rows]
        reader = Mock(return_value=fake_article())
        result = retrieve_article_evidence(proposal, bundle(rows), NOW,
                                          reader=reader, feed_fetcher=Mock(return_value=feed()))
        self.assertEqual(reader.call_count, MAX_ARTICLES)
        self.assertEqual(result["article_retrieval"]["budget_skipped_count"], 3)

    def test_wire_mentions_remain_warning_signals(self):
        self.assertEqual(provenance_signals("Text attributed to Reuters and Associated Press."),
                         ["Reuters", "Associated Press"])
        self.assertEqual(provenance_signals("A BBC reporter spoke with researchers."), [])

    def test_real_body_quote_is_accepted_and_fabricated_quote_rejected(self):
        result = enriched()
        value = assessment()
        citation = value["events"][0]["claims"][0]["evidence"][1]
        citation["scope"] = "article_text"
        citation["quote"] = "Scientists published test results after observing the sample."
        validate_assessment(value, shortlist(), result["records"], result["event_sources"])
        citation["quote"] = "Invented statistics appear nowhere in the retrieved document."
        with self.assertRaisesRegex(ContractError, "invented_or_too_short_quote"):
            validate_assessment(value, shortlist(), result["records"], result["event_sources"])

    def test_headline_cannot_be_labeled_as_unretrieved_article_text(self):
        value = assessment()
        value["events"][0]["claims"][0]["evidence"][0]["scope"] = "article_text"
        with self.assertRaisesRegex(ContractError, "article_evidence_not_retrieved"):
            validate_assessment(value, shortlist(), records(), bundle()["event_sources"])

    def test_second_model_call_receives_retrieved_text_and_only_relevant_sources(self):
        result = enriched()
        unrelated = copy.deepcopy(records()[0])
        unrelated["id"] = "src_unrelated"
        result["records"].append(unrelated)
        caller = Mock(return_value=assessment())
        compare_claims(shortlist(), result["records"], result["event_sources"], caller=caller)
        sent = caller.call_args.args[1]["records"]
        self.assertEqual(len(sent), 2)
        self.assertIn("article", sent[1])
        self.assertEqual(sent[1]["article"]["text"], BODY[:MAX_TEXT_CHARS])


if __name__ == "__main__":
    unittest.main()
