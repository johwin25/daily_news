"""Fetch sample headlines from Google News RSS feeds.

Stage 2: collection only. Articles are NOT verified or AI-ranked.
"""
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET

BASE_URL = "https://news.google.com/rss/headlines/section/topic/"
PARAMS = "?hl=en-US&gl=US&ceid=US:en"
TOPICS = {
    "World": "WORLD",
    "Economy": "BUSINESS",
    "Technology": "TECHNOLOGY",
    "Science": "SCIENCE",
}


def fetch_category(category, topic):
    """Return article metadata from one RSS topic feed."""
    url = f"{BASE_URL}{topic}{PARAMS}"
    request = Request(url, headers={"User-Agent": "daily_news/0.1 (personal RSS reader)"})
    with urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP status {response.status}")
        xml_bytes = response.read(2_000_000)

    root = ET.fromstring(xml_bytes)
    articles = []
    for item in root.findall("./channel/item"):
        articles.append({
            "category": category,
            "title": (item.findtext("title") or "").strip(),
            "url": (item.findtext("link") or "").strip(),
            "published": (item.findtext("pubDate") or "").strip(),
            "publisher": (item.findtext("source") or "").strip(),
        })
    return [article for article in articles if article["title"] and article["url"]]


def main():
    print("Daily News — RSS collection test")
    print("Collection time (UTC):", datetime.now(timezone.utc).isoformat())

    seen_urls = set()
    total = 0
    successful_feeds = 0

    for category, topic in TOPICS.items():
        try:
            articles = fetch_category(category, topic)
        except (HTTPError, URLError, TimeoutError, ET.ParseError, RuntimeError, ValueError) as exc:
            print(f"\n[{category}] Feed error: {exc}")
            continue

        successful_feeds += 1
        new_articles = []
        for article in articles:
            if article["url"] in seen_urls:
                continue
            seen_urls.add(article["url"])
            new_articles.append(article)

        total += len(new_articles)
        print(f"\n[{category}] {len(new_articles)} unique articles")
        for article in new_articles[:5]:
            print(" -", article["title"])
            print("   Source:", article["publisher"] or "Unknown")
            print("   Published:", article["published"] or "Unknown")
            print("   Link:", article["url"])

    print(f"\nSummary: {successful_feeds}/{len(TOPICS)} feeds retrieved; {total} unique articles.")
    if successful_feeds != len(TOPICS) or total == 0:
        raise SystemExit("RSS collection incomplete — see errors above.")
    print("PASS: RSS collection complete. No story verification performed.")


if __name__ == "__main__":
    main()
