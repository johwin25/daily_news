"""Extract publisher metadata and conservative reporting-origin signals."""
import json
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_json = False
        self.parts = []
        self.documents = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type") == "application/ld+json":
            self.in_json = True
            self.parts = []

    def handle_data(self, data):
        if self.in_json:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.in_json:
            try:
                self.documents.append(json.loads("".join(self.parts)))
            except (ValueError, RecursionError):
                pass
            self.in_json = False


def page_metadata(html):
    parser = MetadataParser()
    parser.feed(html)
    articles = []

    def walk(value, depth=0):
        if depth > 20:
            return
        if isinstance(value, dict):
            kinds = value.get("@type", [])
            if isinstance(kinds, str):
                kinds = [kinds]
            if any(kind in ("NewsArticle", "Article", "ReportageNewsArticle") for kind in kinds):
                articles.append(value)
            for child in value.values():
                walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                walk(child, depth + 1)

    for document in parser.documents:
        walk(document)
    if not articles:
        return {"authors": [], "person_authors": [], "published_at": None, "accessible_for_free": None}
    article = articles[0]
    authors = article.get("author", [])
    if not isinstance(authors, list):
        authors = [authors]
    names = []
    persons = []
    for author in authors:
        name = author.get("name", "") if isinstance(author, dict) else author
        if isinstance(name, str) and 1 <= len(name.strip()) <= 160:
            names.append(name.strip())
            if isinstance(author, dict) and author.get("@type") == "Person":
                persons.append(name.strip())
    return {"authors": sorted(set(names)), "person_authors": sorted(set(persons)),
            "published_at": article.get("datePublished"),
            "accessible_for_free": article.get("isAccessibleForFree")}


def reporting_provenance(article, publisher, now):
    """Require explicit self-attribution, a named byline, and a fresh page date.

    This is a conservative operational signal, not proof that every sentence
    was independently investigated. Cross-claim citations and copy checks are
    required separately. Wire mentions always keep origin unresolved.
    """
    metadata = article.get("metadata", {})
    authors = metadata.get("authors", [])
    named = [name for name in metadata.get("person_authors", []) if len(name.split()) >= 2
             and name.casefold() not in {"bbc news", "the guardian", "guardian staff"}]
    fresh = False
    published = metadata.get("published_at")
    try:
        date = datetime.fromisoformat(published.replace("Z", "+00:00"))
        fresh = date.tzinfo is not None and -timedelta(minutes=15) <= now - date <= timedelta(hours=48)
    except (ValueError, TypeError, AttributeError, OverflowError):
        pass
    name = {"BBC News": r"(?:the\s+)?BBC", "The Guardian": r"the\s+Guardian"}.get(publisher)
    quote = ""
    if name:
        patterns = [
            rf"\btold\s+{name}\b", rf"\bspeaking\s+to\s+{name}\b",
            rf"\b{name}\s+(?:has\s+seen|has\s+learned|understands|observed)\b",
            rf"\b(?:seen|obtained|reviewed)\s+by\s+{name}\b",
        ]
        text = article.get("text", "")
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                quote = text[max(0, match.start() - 80):min(len(text), match.end() + 100)]
                break
    from news_article_evidence import provenance_signals
    wires = provenance_signals(article.get("text", ""))
    eligible = bool(quote and named and fresh and not wires)
    return {"origin": "publisher_self_attributed_reporting" if eligible else "unknown",
            "reporting_chain": "publisher:" + publisher if eligible else None,
            "origin_excerpt": quote, "authors": authors, "page_published_at": published,
            "page_date_fresh": fresh, "wire_mentions": wires}
