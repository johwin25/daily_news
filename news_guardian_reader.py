"""Read visible paragraphs from a direct, freely accessible Guardian article."""
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from news_article_reader import ArticleReadError, MAX_BYTES, VOID_TAGS
from news_provenance import page_metadata


def validate_guardian_url(url):
    try:
        p = urlsplit(url)
        valid = (p.scheme == "https" and p.hostname in {"www.theguardian.com", "theguardian.com"}
                 and p.port in (None, 443) and not p.username and not p.password
                 and not p.query and not p.fragment and len(url) <= 2048
                 and re.fullmatch(r"/[a-z0-9/-]+/20\d{2}/[a-z]{3}/\d{2}/[a-z0-9-]+", p.path))
    except (ValueError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise ArticleReadError("unsupported_guardian_article_url")
    return url


class SameArticleRedirects(HTTPRedirectHandler):
    max_redirections = 3

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_guardian_url(newurl)
        if urlsplit(newurl).path != urlsplit(req.full_url).path:
            raise ArticleReadError("redirect_changed_article")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class GuardianTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.parts = None
        self.paragraphs = []
        self.title = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("property") == "og:title":
            self.title = attrs.get("content", "").strip()
        if tag in VOID_TAGS:
            if self.parts is not None:
                self.parts.append(" ")
            return
        self.stack.append(tag)
        if tag == "p" and "article" in self.stack and not set(self.stack) & {"nav", "aside", "footer"}:
            self.parts = []

    def handle_data(self, text):
        if self.parts is not None and not set(self.stack) & {"script", "style", "noscript"}:
            self.parts.append(text)

    def handle_endtag(self, tag):
        if tag == "p" and self.parts is not None:
            text = " ".join("".join(self.parts).split())
            if text:
                self.paragraphs.append(text)
            self.parts = None
        if tag in self.stack:
            index = len(self.stack) - 1 - self.stack[::-1].index(tag)
            del self.stack[index:]


def extract_guardian_article(html):
    parser = GuardianTextParser()
    parser.feed(html)
    metadata = page_metadata(html)
    if metadata["accessible_for_free"] is not True:
        raise ArticleReadError("guardian_free_article_not_established")
    text = "\n\n".join(parser.paragraphs)
    if not parser.title or len(text.split()) < 100:
        raise ArticleReadError("article_text_missing_or_too_short")
    return parser.title, text, metadata


def read_guardian_article(url, opener=None):
    validate_guardian_url(url)
    opener = opener or build_opener(SameArticleRedirects())
    try:
        with opener.open(Request(url, headers={"User-Agent": "daily_news/0.6 (personal article reader)",
                                               "Accept-Encoding": "identity"}), timeout=25) as response:
            final_url = validate_guardian_url(response.geturl())
            if response.status != 200 or urlsplit(url).path != urlsplit(final_url).path:
                raise ArticleReadError("article_http_or_redirect_failure")
            if response.headers.get_content_type() != "text/html":
                raise ArticleReadError("article_not_html")
            if response.headers.get("Content-Encoding", "identity") != "identity":
                raise ArticleReadError("unsupported_content_encoding")
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ArticleReadError("article_response_too_large")
        title, text, metadata = extract_guardian_article(raw.decode("utf-8"))
    except HTTPError as error:
        error.close()
        raise ArticleReadError("article_access_or_http_failure") from None
    except (URLError, OSError, UnicodeError):
        raise ArticleReadError("article_network_or_encoding_failure") from None
    return {"status": "retrieved", "title": title, "text": text, "metadata": metadata,
            "retrieved_url": final_url, "retrieved_at": datetime.now(timezone.utc).isoformat()}
