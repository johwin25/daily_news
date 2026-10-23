"""Offline checks for extraction, access failures, and URL restrictions."""
import io
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

from news_article_reader import (
    ArticleReadError, BBCOnlyRedirects, MAX_BYTES, extract_article,
    main, read_article, validate_article_url,
)

URL = "https://www.bbc.com/news/articles/cq0ld9g9e913o"
WORDS = " ".join(["reported"] * 110)
HTML = ('<html><head><meta property="og:title" content="Vaccine trial &amp; results">'
        '</head><body><nav>Navigation</nav><div data-component="text-block">'
        '<p>First <b>visible</b> paragraph &amp; evidence.<br>Second sentence.</p>'
        '<script>INJECTED_SCRIPT</script></div><div data-component="text-block">'
        '<p>' + WORDS + '</p></div><footer>Footer text</footer></body></html>')


def fake_opener(body=HTML, content_type="text/html", final_url=URL):
    response = Mock()
    response.status = 200
    response.geturl.return_value = final_url
    response.headers = Message()
    response.headers["Content-Type"] = content_type
    response.read.return_value = body.encode("utf-8")
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    opener = Mock()
    opener.open.return_value = response
    return opener


class ArticleReaderTests(unittest.TestCase):
    def test_extract_visible_blocks_and_entities(self):
        title, paragraphs, text = extract_article(HTML)
        self.assertEqual(title, "Vaccine trial & results")
        self.assertEqual(len(paragraphs), 2)
        self.assertIn("First visible paragraph & evidence. Second sentence.", text)
        for unwanted in ("Navigation", "Footer text", "INJECTED_SCRIPT"):
            self.assertNotIn(unwanted, text)

    def test_missing_title_or_body_fails(self):
        for html in ("<p>Blocked</p>", HTML.replace(WORDS, "Too short"),
                     HTML.replace('property="og:title"', 'property="other"')):
            with self.subTest(html=html[:30]), self.assertRaises(ArticleReadError):
                extract_article(html)

    def test_invalid_urls_never_start_network_request(self):
        for url in (
            "http://www.bbc.com/news/articles/abcdefgh",
            "https://bbc.com.evil.example/news/articles/abcdefgh",
            "https://evil.bbc.com/news/articles/abcdefgh",
            "https://user@www.bbc.com/news/articles/abcdefgh",
            "https://www.bbc.com:8080/news/articles/abcdefgh",
            "https://www.bbc.com/news/articles/abcdefgh?redirect=elsewhere",
            "https://news.google.com/rss/articles/abcdefgh",
            "https://www.bbc.com/", "https://[invalid",
        ):
            with self.subTest(url=url):
                opener = Mock()
                with self.assertRaises(ArticleReadError):
                    read_article(url, opener)
                opener.open.assert_not_called()

    def test_bbc_domains_allowed(self):
        for host in ("bbc.com", "www.bbc.com", "bbc.co.uk", "www.bbc.co.uk"):
            self.assertTrue(validate_article_url(f"https://{host}/news/articles/abcdefgh"))

    def test_redirect_checked_before_following(self):
        handler = BBCOnlyRedirects()
        for url in ("https://example.com/news/articles/abcdefgh",
                    "https://www.bbc.com/news/articles/different123"):
            with self.subTest(url=url), self.assertRaises(ArticleReadError):
                handler.redirect_request(Request(URL), None, 302, "Found", {}, url)
        request = handler.redirect_request(
            Request(URL), None, 302, "Found", {}, URL.replace("bbc.com", "bbc.co.uk"))
        self.assertIn("bbc.co.uk", request.full_url)

    def test_success_keeps_provenance_and_unverified_label(self):
        opener = fake_opener()
        result = read_article(URL, opener)
        self.assertEqual(result["status"], "retrieved")
        self.assertEqual(result["requested_url"], URL)
        self.assertEqual(result["retrieved_url"], URL)
        self.assertEqual(result["verification_status"], "unverified")
        self.assertEqual(result["word_count"], len(result["text"].split()))
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 25)

    def test_non_html_oversize_and_wrong_article_rejected(self):
        cases = (
            fake_opener(content_type="application/pdf"),
            fake_opener(body="x" * (MAX_BYTES + 1)),
            fake_opener(final_url="https://www.bbc.com/news/articles/different123"),
        )
        for opener in cases:
            with self.assertRaises(ArticleReadError):
                read_article(URL, opener)

    def test_access_and_network_failures_have_fixed_diagnostics(self):
        for error, expected in (
            (HTTPError(URL, 403, "private details", {}, io.BytesIO()),
             "article_access_denied_or_rate_limited"),
            (HTTPError(URL, 404, "private details", {}, io.BytesIO()),
             "article_http_failure"),
            (URLError("private details"), "article_network_failure"),
            (TimeoutError("private details"), "article_network_failure"),
        ):
            opener = Mock()
            opener.open.side_effect = error
            with self.assertRaisesRegex(ArticleReadError, "^" + expected + "$"):
                read_article(URL, opener)

    def test_failed_cli_replaces_stale_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            path.write_text('{"status":"retrieved","text":"stale"}')
            with patch("news_article_reader.read_article", side_effect=ArticleReadError("article_network_failure")):
                self.assertEqual(main([URL, "--output", str(path)]), 1)
            result = json.loads(path.read_text())
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["text"], "")
            self.assertEqual(result["paragraphs"], [])


if __name__ == "__main__":
    unittest.main()
