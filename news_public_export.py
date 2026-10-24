"""Export a minimal public-facing reader JSON from a research artifact.

This does NOT verify a claim, and never promotes research leads to confirmed.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


def clean_text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ""


def clean_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return ""
    parsed = urlparse(value)
    return value if parsed.scheme == "https" and parsed.hostname else ""


def export_briefing(data):
    if not isinstance(data, dict):
        raise ValueError("invalid_briefing")
    status = data.get("pipeline_status")
    if status not in ("completed_with_evidence_shortfall", "failed"):
        raise ValueError("unknown_pipeline_status")
    leads = []
    if status == "completed_with_evidence_shortfall":
        if data.get("confirmed_count") != 0 or data.get("items") != []:
            raise ValueError("unexpected_confirmed_news")
        queue = data.get("review_queue")
        if not isinstance(queue, list):
            raise ValueError("invalid_review_queue")
        for entry in queue[:3]:
            if not isinstance(entry, dict) or entry.get("status") != "insufficient_evidence":
                raise ValueError("unexpected_review_status")
            sources = []
            for source in entry.get("sources", [])[:8]:
                if not isinstance(source, dict):
                    continue
                article = source.get("article")
                link = (article.get("retrieved_url") if isinstance(article, dict) else None) or source.get("url")
                url = clean_url(link)
                if url:
                    sources.append({"publisher": clean_text(source.get("publisher"), 120),
                                    "title": clean_text(source.get("title"), 240), "url": url})
            leads.append({
                "status": "insufficient_evidence",
                "category": clean_text(entry.get("category"), 60),
                "working_headline": clean_text(entry.get("working_headline"), 240),
                "draft_summary": clean_text(entry.get("draft_summary"), 1800),
                "why_it_matters_draft": clean_text(entry.get("why_it_matters_draft"), 800),
                "sources": sources,
            })
    date = data.get("date_utc")
    if not isinstance(date, str) or len(date) != 10 or date[4] != "-" or date[7] != "-":
        raise ValueError("invalid_date")
    return {"schema_version": 1, "date_utc": date,
            "pipeline_status": status, "confirmed_count": 0,
            "items": [], "review_queue": leads}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    data = export_briefing(json.loads(args.source.read_text(encoding="utf-8")))
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS: sanitized reader edition; unverified research only; no confirmed news")


if __name__ == "__main__":
    main()
