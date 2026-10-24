import json
import unittest
from news_article_reader import ArticleReadError
from news_guardian_reader import extract_guardian_article, validate_guardian_url
from news_provenance import page_metadata, reporting_provenance
from test_news_collector import NOW


class GuardianTests(unittest.TestCase):
    def html(self, free=True):
        metadata = {"@type": "NewsArticle", "datePublished": NOW.isoformat(),
                    "author": [{"@type": "Person", "name": "Jane Reporter"}], "isAccessibleForFree": free}
        return ('<meta property="og:title" content="Synthetic news">'
                '<script type="application/ld+json">' + json.dumps(metadata)
                + '</script><nav><p>HIDDEN NAV</p></nav><article><p>A witness told the Guardian what happened. '
                + "reported " * 110 + '</p><aside><p>HIDDEN ASIDE</p></aside></article>')

    def test_only_visible_article_paragraphs_and_metadata_are_extracted(self):
        title, text, metadata = extract_guardian_article(self.html())
        self.assertEqual(title, "Synthetic news")
        self.assertNotIn("HIDDEN", text)
        self.assertEqual(metadata["authors"], ["Jane Reporter"])
        origin = reporting_provenance({"text": text, "metadata": metadata}, "The Guardian", NOW)
        self.assertEqual(origin["origin"], "publisher_self_attributed_reporting")

    def test_paywall_or_unknown_free_status_is_not_bypassed(self):
        for free in (False, None):
            with self.assertRaisesRegex(ArticleReadError, "guardian_free_article_not_established"):
                extract_guardian_article(self.html(free))

    def test_only_direct_guardian_article_urls_are_allowed(self):
        self.assertTrue(validate_guardian_url("https://www.theguardian.com/world/2026/oct/24/story"))
        for url in ("https://theguardian.com.evil.example/world/2026/oct/24/story",
                    "https://www.theguardian.com/world/rss", "http://www.theguardian.com/world/2026/oct/24/story"):
            with self.assertRaises(ArticleReadError):
                validate_guardian_url(url)

    def test_bylines_alone_do_not_establish_original_reporting(self):
        metadata = page_metadata(self.html())
        result = reporting_provenance({"text": "Officials issued a press release.", "metadata": metadata},
                                      "The Guardian", NOW)
        self.assertEqual(result["origin"], "unknown")

    def test_organization_byline_is_not_promoted_to_a_named_journalist(self):
        html = self.html().replace('"@type": "Person"', '"@type": "Organization"')
        metadata = page_metadata(html)
        result = reporting_provenance({"text": "A witness told the Guardian what happened.",
                                       "metadata": metadata}, "The Guardian", NOW)
        self.assertEqual(metadata["person_authors"], [])
        self.assertEqual(result["origin"], "unknown")

    def test_wire_mentions_override_original_reporting_signal(self):
        metadata = page_metadata(self.html())
        result = reporting_provenance({"text": "A witness told the Guardian. Additional reporting by Reuters.",
                                       "metadata": metadata}, "The Guardian", NOW)
        self.assertEqual(result["origin"], "unknown")


if __name__ == "__main__":
    unittest.main()
