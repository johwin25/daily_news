"""Offline tests for the publisher allowlist."""
import unittest
from news_fetcher import approved_publisher, parse_rss


class PublisherFilterTests(unittest.TestCase):
    def test_approved_domains(self):
        self.assertEqual(approved_publisher("https://www.reuters.com"), "Reuters")
        self.assertEqual(approved_publisher("https://feeds.bbci.co.uk/news"), "BBC News")
        self.assertEqual(approved_publisher("https://apnews.com"), "Associated Press")

    def test_unapproved_and_spoofed_domains(self):
        self.assertIsNone(approved_publisher("https://unknown.example"))
        self.assertIsNone(approved_publisher("https://reuters.com.evil.example"))
        self.assertIsNone(approved_publisher("https://fake-reuters.com"))
        self.assertIsNone(approved_publisher(""))

    def test_rss_filter(self):
        sample = b"""<rss><channel>
          <item><title>Sample A</title><link>https://news.google.com/a</link>
          <source url="https://www.reuters.com">Reuters</source></item>
          <item><title>Sample B</title><link>https://news.google.com/b</link>
          <source url="https://rumors.example">Reuters</source></item>
          <item><title>Sample C</title><link>https://news.google.com/c</link></item>
        </channel></rss>"""
        articles, excluded = parse_rss(sample, "World")
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["publisher"], "Reuters")
        self.assertEqual(excluded["unapproved or unknown source"], 2)


if __name__ == "__main__":
    unittest.main()
