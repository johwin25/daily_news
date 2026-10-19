"""Synthetic tests for freshness, stable identity, and provenance."""
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

from news_collector import (
    collect_candidates, merge_records, normalize_article, write_json,
)

NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)


def article(url="https://news.google.com/rss/articles/example", **changes):
    result = {
        "title": "SYNTHETIC: Research team publishes new material - Reuters",
        "url": url,
        "publisher": "Reuters",
        "publisher_url": "https://www.reuters.com",
        "published": format_datetime(NOW - timedelta(hours=1)),
    }
    result.update(changes)
    return result


class CollectorTests(unittest.TestCase):
    def normalize(self, value, category="World"):
        return normalize_article(value, NOW, "https://news.google.com/rss/test",
                                 category)

    def test_stable_identity_across_tracking_and_categories(self):
        first = self.normalize(article(url="https://news.google.com/a?utm_source=x"))
        second = self.normalize(article(url="https://news.google.com/a"), "Science")
        self.assertEqual(first["id"], second["id"])
        records = merge_records([first, second])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["categories"], ["Science", "World"])
        self.assertEqual(records[0]["content_scope"], "headline_only")
        self.assertEqual(records[0]["independence"], "unknown")
        self.assertIn("utm_source", records[0]["url"])

    def test_invalid_stale_and_future_times_are_rejected(self):
        values = [
            "", "not-a-date", "Mon, 19 Oct 2026 11:00:00",
            format_datetime(NOW - timedelta(hours=49)),
            format_datetime(NOW + timedelta(hours=1)),
        ]
        for published in values:
            with self.subTest(published=published):
                with self.assertRaises(ValueError):
                    self.normalize(article(published=published))

    def test_spoofed_publishers_and_invalid_links_are_rejected(self):
        for changes in (
            {"publisher_url": "https://reuters.com.evil.example"},
            {"publisher": "BBC News"},
            {"url": "https://"},
            {"url": "javascript:alert(1)"},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    self.normalize(article(**changes))

    def test_conflicting_publisher_for_same_article_fails(self):
        first = self.normalize(article())
        second = dict(first, publisher="BBC News")
        with self.assertRaisesRegex(ValueError, "conflicting_source_identity"):
            merge_records([first, second])

    def test_partial_feed_failure_is_recorded(self):
        def fetch(category, topic):
            if category == "World":
                raise TimeoutError("untrusted exception text")
            return [article(url="https://news.google.com/" + topic)], Counter()
        data = collect_candidates(NOW, fetch)
        self.assertEqual(data["feed_count"], 3)
        self.assertEqual(data["feed_errors"],
                         [{"category": "World", "reason": "feed_fetch_failed"}])
        self.assertEqual(len(data["records"]), 3)

    def test_atomic_json_replaces_instead_of_appending(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "nested" / "candidates.json"
            write_json(target, {"records": [1]})
            write_json(target, {"records": [2]})
            self.assertIn("2", target.read_text())
            self.assertNotIn("1", target.read_text())
            self.assertFalse(target.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
