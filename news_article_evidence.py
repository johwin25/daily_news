"""Resolve BBC originals from publisher RSS and retain bounded text evidence.

No Google token decoding or arbitrary redirect service is used. A missing,
ambiguous, stale or inaccessible original remains explicit missing evidence.
"""
import copy
import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from news_article_reader import ArticleReadError, read_article, validate_article_url
from news_collector import title_fingerprint

BBC_FEEDS = (
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
)
MAX_ARTICLES = 6
MAX_TEXT_CHARS = 5000


def headline_key(title):
    title = re.sub(r"\s+[-|]\s+(?:BBC(?: News)?|BBC\.com)$", "", title, flags=re.I)
    return re.sub(r"[\W_]+", " ", unescape(title).casefold()).strip()


class NoFeedRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ArticleReadError("publisher_feed_redirect_refused")


def fetch_publisher_feed(url):
    if url not in BBC_FEEDS:
        raise ArticleReadError("unsupported_publisher_feed")
    request = Request(url, headers={"User-Agent": "daily_news/0.5 (personal RSS reader)"})
    with build_opener(NoFeedRedirects()).open(request, timeout=15) as response:
        if response.status != 200:
            raise ArticleReadError("publisher_feed_http_failure")
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ArticleReadError("publisher_feed_size_limit")
    return raw


def index_bbc_feeds(now, fetcher=fetch_publisher_feed):
    index = {}
    diagnostics = []
    for feed in BBC_FEEDS:
        try:
            root = ET.fromstring(fetcher(feed))
            for item in root.findall("./channel/item"):
                try:
                    title = (item.findtext("title") or "").strip()
                    key = headline_key(title)
                    parts = urlsplit((item.findtext("link") or "").strip())
                    # Feed tracking parameters do not identify another article.
                    url = validate_article_url(urlunsplit((
                        parts.scheme, parts.netloc, parts.path, "", ""
                    )))
                    published = parsedate_to_datetime(item.findtext("pubDate") or "")
                    if (not key or published.tzinfo is None
                            or now - published > timedelta(hours=48)
                            or published - now > timedelta(minutes=15)):
                        continue
                    value = {"url": url, "title": title, "feed_url": feed,
                             "published_at": published.isoformat()}
                    index.setdefault(key, {})[urlsplit(url).path] = value
                except (ValueError, TypeError, AttributeError, OverflowError):
                    continue
            diagnostics.append({"feed_url": feed, "status": "completed"})
        except Exception:
            diagnostics.append({"feed_url": feed, "status": "feed_unavailable"})
    return index, diagnostics


def resolve_bbc_record(record, index):
    if record["publisher"] != "BBC News":
        raise ArticleReadError("publisher_reader_not_implemented")
    # A direct URL may already exist in later source collectors.
    try:
        url = validate_article_url(record["url"])
        return {"url": url, "basis": "direct_collected_url"}
    except ArticleReadError:
        pass
    matches = index.get(headline_key(record["title"]), {})
    if len(matches) != 1:
        reason = "ambiguous_original_article" if matches else "original_article_not_in_feeds"
        raise ArticleReadError(reason)
    match = next(iter(matches.values()))
    return {**match, "basis": "exact_publisher_headline_match"}


def provenance_signals(text):
    """Wire mentions are warning signals, never proof of independent reporting."""
    patterns = {
        "Reuters": r"\breuters\b",
        "Associated Press": r"\bassociated press\b|\(AP\)",
        "Agence France-Presse": r"\bagence france.presse\b|\bAFP\b",
        "PA Media": r"\bPA Media\b|\bPress Association\b",
    }
    return [name for name, pattern in patterns.items() if re.search(pattern, text, re.I)]


def retrieve_article_evidence(shortlist, evidence, now, reader=read_article,
                              feed_fetcher=fetch_publisher_feed):
    result = copy.deepcopy(evidence)
    records = {record["id"]: record for record in result["records"]}
    wanted = []
    # Round-robin keeps one event from consuming the whole retrieval budget.
    groups = []
    for event in sorted(shortlist["events"], key=lambda e: -e["priority"]):
        ids = result["event_sources"][event["event_id"]]
        selected = list(event["source_ids"]) + [sid for sid in ids if sid not in event["source_ids"]]
        groups.append([sid for sid in selected if records[sid]["publisher"] == "BBC News"])
    for position in range(max((len(group) for group in groups), default=0)):
        for group in groups:
            if position < len(group) and group[position] not in wanted:
                wanted.append(group[position])
    index, feed_status = index_bbc_feeds(now, feed_fetcher) if wanted else ({}, [])
    reads = []
    for source_id in wanted[:MAX_ARTICLES]:
        record = records[source_id]
        try:
            original = resolve_bbc_record(record, index)
            article = reader(original["url"])
            if (article.get("status") != "retrieved"
                    or headline_key(article.get("title", "")) != headline_key(record["title"])):
                raise ArticleReadError("retrieved_article_title_mismatch")
            if (not isinstance(article.get("text"), str)
                    or len(article["text"].split()) < 100):
                raise ArticleReadError("article_text_missing_or_too_short")
            validate_article_url(article["retrieved_url"])
            if urlsplit(article["retrieved_url"]).path != urlsplit(original["url"]).path:
                raise ArticleReadError("redirect_changed_article")
            text = article["text"][:MAX_TEXT_CHARS]
            record["article"] = {
                "source_id": source_id, "status": "retrieved",
                "original_url": original["url"], "retrieved_url": article["retrieved_url"],
                "resolution_basis": original["basis"],
                "publisher_feed_url": original.get("feed_url"),
                "retrieved_at": article["retrieved_at"],
                "title": article["title"], "text": text,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "text_truncated": len(text) < len(article["text"]),
                "wire_mentions": provenance_signals(article["text"]),
                "independence": "unknown", "completeness": "not_established",
                "article_publication_date": "not_established",
            }
            record["content_scope"] = "article_text"
            # Title fingerprints stay available for duplicate headline checks.
            record["title_fingerprint"] = title_fingerprint(record["title"], record["publisher"])
            reads.append({"source_id": source_id, "status": "retrieved"})
        except ArticleReadError as error:
            reads.append({"source_id": source_id, "status": "unavailable", "reason": str(error)})
        except Exception:
            reads.append({"source_id": source_id, "status": "unavailable", "reason": "article_retrieval_failure"})
    result["article_retrieval"] = {
        "attempts": reads, "publisher_feeds": feed_status,
        "budget_skipped_count": max(0, len(wanted) - MAX_ARTICLES),
        "supported_publishers": ["BBC News"],
        "retrieved_count": sum(item["status"] == "retrieved" for item in reads),
        "max_articles": MAX_ARTICLES, "max_text_chars": MAX_TEXT_CHARS,
    }
    result["content_scope"] = "mixed_article_and_headline_evidence"
    return result
