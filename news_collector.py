"""Normalize public RSS metadata without treating headlines as verification."""
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from news_fetcher import BASE_URL, PARAMS, TOPICS, approved_publisher, fetch_category

MAX_AGE_HOURS = 48
MAX_CANDIDATES = 100
MAX_PER_CATEGORY = 25


def utc_now():
    return datetime.now(timezone.utc)


def canonical_url(url):
    """Remove tracking for identity only; citations retain the fetched URL."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("invalid_article_url")
    query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if not key.lower().startswith("utm_"):
            query.append((key, value))
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(),
                       parsed.path, parsed.params, urlencode(sorted(query)), ""))


def title_fingerprint(title, publisher):
    """Flag copied headlines; matching text does not prove independence."""
    text = title
    suffix = " - " + publisher
    if text.lower().endswith(suffix.lower()):
        text = text[:-len(suffix)]
    words = re.sub(r"[\W_]+", " ", text.casefold()).strip()
    return hashlib.sha256(words.encode()).hexdigest()[:20]


def normalize_article(article, now, feed_url, category):
    """Reject unknown, stale, future, malformed, or unattributed records."""
    publisher = approved_publisher(article.get("publisher_url", ""))
    if not publisher or publisher != article.get("publisher"):
        raise ValueError("invalid_publisher")
    title = article.get("title", "").strip()
    if not title or len(title) > 1000:
        raise ValueError("invalid_title")
    url = article.get("url", "").strip()
    identity_url = canonical_url(url)
    try:
        published = parsedate_to_datetime(article.get("published", ""))
        if published.tzinfo is None:
            raise ValueError
        published = published.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError, AttributeError):
        raise ValueError("invalid_publication_time") from None
    if published > now + timedelta(minutes=15):
        raise ValueError("future_publication_time")
    if now - published > timedelta(hours=MAX_AGE_HOURS):
        raise ValueError("stale_article")
    return {
        "id": "src_" + hashlib.sha256(identity_url.encode()).hexdigest()[:20],
        "title": title,
        "url": url,
        "publisher": publisher,
        "publisher_url": article["publisher_url"],
        "published_at": published.isoformat(),
        "retrieved_at": now.isoformat(),
        "categories": [category],
        "feed_urls": [feed_url],
        "content_scope": "headline_only",
        "attribution_basis": "rss_source_metadata",
        "independence": "unknown",
        "title_fingerprint": title_fingerprint(title, publisher),
    }


def merge_records(records):
    """Deduplicate across categories while preserving collection provenance."""
    by_id = {}
    for record in records:
        previous = by_id.get(record["id"])
        if previous is None:
            by_id[record["id"]] = dict(record)
            continue
        if (canonical_url(previous["url"]) != canonical_url(record["url"])
                or previous["publisher"] != record["publisher"]):
            raise ValueError("conflicting_source_identity")
        for field in ("categories", "feed_urls"):
            previous[field] = sorted(set(previous[field]) | set(record[field]))
    return sorted(by_id.values(), key=lambda r: (r["published_at"], r["id"]),
                  reverse=True)


def collect_candidates(now=None, fetcher=fetch_category):
    now = now or utc_now()
    records = []
    excluded = Counter()
    errors = []
    for category, topic in TOPICS.items():
        feed_url = BASE_URL + topic + PARAMS
        try:
            articles, rejected = fetcher(category, topic)
        except Exception:
            # Never print arbitrary network/XML exception content.
            errors.append({"category": category, "reason": "feed_fetch_failed"})
            continue
        excluded.update(rejected)
        fresh = []
        for article in articles:
            try:
                fresh.append(normalize_article(article, now, feed_url, category))
            except (ValueError, TypeError, AttributeError) as exc:
                reason = str(exc)
                if reason not in {
                    "invalid_publisher", "invalid_title", "invalid_article_url",
                    "invalid_publication_time", "future_publication_time",
                    "stale_article",
                }:
                    reason = "invalid_record"
                excluded[reason] += 1
        fresh = merge_records(fresh)
        excluded["category_limit"] += max(0, len(fresh) - MAX_PER_CATEGORY)
        records.extend(fresh[:MAX_PER_CATEGORY])
    records = merge_records(records)[:MAX_CANDIDATES]
    return {
        "schema_version": 1,
        "collected_at": now.isoformat(),
        "max_age_hours": MAX_AGE_HOURS,
        "feed_count": len(TOPICS) - len(errors),
        "expected_feed_count": len(TOPICS),
        "feed_errors": errors,
        "excluded": dict(excluded),
        "records": records,
    }


def write_json(path, data):
    """Replace outputs atomically; never append duplicate events on reruns."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)
