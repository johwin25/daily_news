"""Read visible text from a direct BBC News article; no verification claim.

Run: python news_article_reader.py https://www.bbc.com/news/articles/ARTICLE_ID
Google News redirects are deliberately unsupported in this first reader.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_BYTES = 2_000_000
MIN_WORDS = 100
BBC_HOSTS = {"bbc.com", "www.bbc.com", "bbc.co.uk", "www.bbc.co.uk"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}


class ArticleReadError(ValueError):
    """A fixed diagnostic safe to save in an output file."""


def validate_article_url(url):
    """Only direct HTTPS BBC article paths may initiate a request."""
    try:
        parts = urlsplit(url)
        valid = (
            parts.scheme == "https" and parts.hostname in BBC_HOSTS
            and parts.port in (None, 443) and not parts.username
            and not parts.password and not parts.query and not parts.fragment
            and re.fullmatch(r"/news/articles/[a-z0-9]{8,32}", parts.path)
        )
    except (ValueError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise ArticleReadError("unsupported_article_url")
    return url


class BBCOnlyRedirects(HTTPRedirectHandler):
    max_redirections = 3

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Validate BEFORE following, including redirects off BBC or to login.
        validate_article_url(newurl)
        if urlsplit(newurl).path != urlsplit(req.full_url).path:
            raise ArticleReadError("redirect_changed_article")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class BBCTextParser(HTMLParser):
    """Extract BBC text-block components, excluding scripts and page chrome."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.block_depth = None
        self.parts = []
        self.paragraphs = []
        self.title = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("property") == "og:title":
            self.title = " ".join(attrs.get("content", "").split())
        if tag in VOID_TAGS:
            if self.block_depth is not None:
                self.parts.append(" ")
            return
        self.stack.append(tag)
        if (self.block_depth is None
                and attrs.get("data-component") == "text-block"
                and not any(t in self.stack for t in ("script", "style", "nav", "footer"))):
            self.block_depth = len(self.stack)
            self.parts = []

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if (self.block_depth is not None
                and not any(t in self.stack for t in ("script", "style", "noscript"))):
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag not in self.stack:
            return
        index = len(self.stack) - 1 - self.stack[::-1].index(tag)
        if self.block_depth is not None and index < self.block_depth:
            paragraph = " ".join("".join(self.parts).split())
            if paragraph:
                self.paragraphs.append(paragraph)
            self.block_depth = None
        del self.stack[index:]


def extract_article(html):
    parser = BBCTextParser()
    parser.feed(html)
    parser.close()
    text = "\n\n".join(parser.paragraphs)
    if not parser.title or len(text.split()) < MIN_WORDS:
        raise ArticleReadError("article_text_missing_or_too_short")
    return parser.title, parser.paragraphs, text


def read_article(url, opener=None):
    validate_article_url(url)
    opener = opener or build_opener(BBCOnlyRedirects())
    request = Request(url, headers={
        "User-Agent": "daily_news/0.4 (personal article reader)",
        "Accept": "text/html", "Accept-Encoding": "identity",
    })
    try:
        with opener.open(request, timeout=25) as response:
            if response.status != 200:
                raise ArticleReadError("article_http_failure")
            final_url = validate_article_url(response.geturl())
            if urlsplit(final_url).path != urlsplit(url).path:
                raise ArticleReadError("redirect_changed_article")
            if response.headers.get_content_type() != "text/html":
                raise ArticleReadError("article_not_html")
            if response.headers.get("Content-Encoding", "identity") != "identity":
                raise ArticleReadError("unsupported_content_encoding")
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ArticleReadError("article_response_too_large")
            html = raw.decode("utf-8")
        title, paragraphs, text = extract_article(html)
        from news_provenance import page_metadata
        metadata = page_metadata(html)
    except HTTPError as error:
        error.close()
        if error.code in (401, 403, 429):
            raise ArticleReadError("article_access_denied_or_rate_limited") from None
        raise ArticleReadError("article_http_failure") from None
    except (URLError, TimeoutError, OSError):
        raise ArticleReadError("article_network_failure") from None
    except UnicodeError:
        raise ArticleReadError("article_encoding_failure") from None
    return {
        "schema_version": 1, "status": "retrieved",
        "requested_url": url, "retrieved_url": final_url, "publisher": "BBC News",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "title": title, "paragraphs": paragraphs, "text": text,
        "metadata": metadata,
        "word_count": len(text.split()), "content_scope": "article_text",
        "verification_status": "unverified",
        "limitations": ["Completeness and publication date are not established.",
                        "Reporting independence and claims have not been checked."],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Direct HTTPS BBC News article URL")
    parser.add_argument("--output", default="output/article-reader/latest.json")
    args = parser.parse_args(argv)
    try:
        result = read_article(args.url)
        exit_code = 0
    except ArticleReadError as error:
        # Replace any earlier success so failed reruns cannot expose stale text.
        result = {"schema_version": 1, "status": "failed", "error": str(error),
                  "verification_status": "unverified", "text": "", "paragraphs": []}
        exit_code = 1
    path = Path(args.output)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    except OSError:
        print("FAIL: article_output_write_failure", file=sys.stderr)
        return 1
    if exit_code:
        print("FAIL: " + result["error"], file=sys.stderr)
    else:
        print(f"PASS: BBC article text retrieved; {result['word_count']} words, "
              f"{len(result['paragraphs'])} text blocks. Claims remain unverified.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

