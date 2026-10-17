"""Collect Google News RSS headlines from ten approved publishers.

Stage 2: publisher filtering only, NOT fact verification or AI ranking.
"""
from collections import Counter
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

BASE_URL = "https://news.google.com/rss/headlines/section/topic/"
PARAMS = "?hl=en-US&gl=US&ceid=US:en"
TOPICS = {
    "World": "WORLD",
    "Economy": "BUSINESS",
    "Technology": "TECHNOLOGY",
    "Science": "SCIENCE",
}

# Curated editorial allowlist, NOT an objective ranking or accuracy guarantee.
# We match the RSS <source url="..."> hostname, not headline text.
TRUSTED_PUBLISHERS = {
    "Reuters": ("reuters.com",),
    "Associated Press": ("apnews.com",),
    "BBC News": ("bbc.com", "bbc.co.uk"),
    "The Guardian": ("theguardian.com",),
    "The New York Times": ("nytimes.com",),
    "The Wall Street Journal": ("wsj.com",),
    "Financial Times": ("ft.com",),
    "Bloomberg": ("bloomberg.com",),
    "NPR": ("npr.org",),
    "Agence France-Presse": ("afp.com",),
}


def approved_publisher(source_url):
    """Return canonical publisher name if the source URL is on the allowlist."""
    parsed = urlparse(source_url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        return None

    hostname = parsed.hostname.lower().rstrip(".")
    for publisher, domains in TRUSTED_PUBLISHERS.items():
        if any(hostname == domain or hostname.endswith("." + domain)
               for domain in domains):
            return publisher
    return None


def parse_rss(xml_bytes, category):
    """Parse feed and keep only entries attributed to approved source domains."""
    root = ET.fromstring(xml_bytes)
    kept = []
    rejected = Counter()

    for item in root.findall("./channel/item"):
        source = item.find("source")
        source_url = source.get("url", "").strip() if source is not None else ""
        publisher = approved_publisher(source_url)
        if not publisher:
            rejected["unapproved or unknown source"] += 1
            continue

        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link or urlparse(link).scheme not in ("https", "http"):
            rejected["invalid title or article URL"] += 1
            continue

        kept.append({
            "category": category,
            "title": title,
            "url": link,
            "published": (item.findtext("pubDate") or "").strip(),
            "publisher": publisher,
            "publisher_url": source_url,
        })
    return kept, rejected


def fetch_category(category, topic):
    """Fetch a topic RSS feed; return approved articles and exclusion counts."""
    url = f"{BASE_URL}{topic}{PARAMS}"
    request = Request(
        url, headers={"User-Agent": "daily_news/0.2 (personal RSS reader)"}
    )
    with urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP status {response.status}")
        xml_bytes = response.read(2_000_000)
    return parse_rss(xml_bytes, category)


def main():
    print("Daily News — approved-publisher RSS collection test")
    print("Collection time (UTC):", datetime.now(timezone.utc).isoformat())
    print("Allowlisted publishers:", ", ".join(TRUSTED_PUBLISHERS))

    seen_urls = set()
    total = 0
    rejected_total = Counter()
    successful_feeds = 0

    for category, topic in TOPICS.items():
        try:
            articles, rejected = fetch_category(category, topic)
        except (HTTPError, URLError, TimeoutError, ET.ParseError,
                RuntimeError, ValueError) as exc:
            print(f"\n[{category}] Feed error: {exc}")
            continue

        successful_feeds += 1
        rejected_total.update(rejected)
        unique_articles = []
        for article in articles:
            if article["url"] in seen_urls:
                continue
            seen_urls.add(article["url"])
            unique_articles.append(article)

        total += len(unique_articles)
        print(f"\n[{category}] {len(unique_articles)} approved, unique articles")
        for article in unique_articles[:5]:
            print(" -", article["title"])
            print("   Source:", article["publisher"])
            print("   Published:", article["published"] or "Unknown")
            print("   Link:", article["url"])

    print(f"\nExcluded: {dict(rejected_total)}")
    print(f"Summary: {successful_feeds}/{len(TOPICS)} feeds retrieved; "
          f"{total} approved unique articles.")
    if successful_feeds != len(TOPICS):
        raise SystemExit("RSS collection incomplete — check feed errors.")
    if total == 0:
        raise SystemExit("No approved articles found — review the allowlist or feeds.")
    print("PASS: publisher filter applied. Stories are NOT independently verified.")


if __name__ == "__main__":
    main()
