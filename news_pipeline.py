"""Collect -> shortlist -> search -> compare -> conservative publication gate.

This first pipeline retrieves headline metadata only. It produces useful draft
leads, but deliberately publishes zero confirmed items until fuller evidence
and reporting-chain provenance can be retrieved.
"""
import argparse
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from news_analyzer import MODEL, GeminiConnectionError
from news_collector import (
    collect_candidates, merge_records, normalize_article, utc_now, write_json,
)
from news_contracts import (
    ASSESSMENT_SCHEMA, SHORTLIST_SCHEMA, ContractError,
)
from news_editor import (
    compare_claims, shortlist_events, validate_assessment, validate_shortlist,
)
from news_fetcher import parse_rss

ARTIFACT_FILES = (
    "candidates.json", "shortlist.json", "evidence.json", "assessment.json",
    "briefing.json", "briefing.txt", "run_status.json", "contracts.json",
)


class PipelineError(ValueError):
    """Fixed, inspectable operational failure."""


def search_google_news(query):
    """Model text is URL-encoded data; it never selects the host or runs code."""
    params = urlencode({
        "q": query + " when:2d", "hl": "en-US", "gl": "US", "ceid": "US:en",
    })
    url = "https://news.google.com/rss/search?" + params
    request = Request(url, headers={"User-Agent": "daily_news/0.3 (personal RSS reader)"})
    with urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise PipelineError("followup_http_failure")
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise PipelineError("followup_response_size_limit")
    articles, rejected = parse_rss(raw, "Follow-up")
    return articles, rejected, url


def gather_evidence(shortlist, candidates, now, searcher=search_google_news):
    records = list(candidates)
    event_sources = {}
    searches = []
    for event in shortlist["events"]:
        source_ids = set(event["source_ids"])
        rejected = Counter()
        status = "completed"
        try:
            articles, excluded, url = searcher(event["search_query"])
            rejected.update(excluded)
            fresh = []
            for article in articles:
                try:
                    fresh.append(normalize_article(
                        article, now, url, event["category"]
                    ))
                except (ValueError, TypeError, AttributeError):
                    rejected["invalid_or_stale_followup"] += 1
            fresh = merge_records(fresh)
            rejected["followup_limit"] += max(0, len(fresh) - 8)
            for record in fresh[:8]:
                records.append(record)
                source_ids.add(record["id"])
        except Exception:
            status = "search_failed"
        event_sources[event["event_id"]] = sorted(source_ids)
        searches.append({
            "event_id": event["event_id"],
            "query": event["search_query"],
            "status": status,
            "excluded": dict(rejected),
            "source_ids": sorted(source_ids),
        })
    return {
        "records": merge_records(records),
        "event_sources": event_sources,
        "searches": searches,
        "content_scope": "headline_only",
        "independence_policy": "Unknown; outlet diversity is not independence.",
    }


def build_briefing(shortlist, assessment, evidence, now):
    """Model assessments cannot override the evidence actually retrieved."""
    records = {record["id"]: record for record in evidence["records"]}
    assessed = {event["event_id"]: event for event in assessment["events"]}
    ordered = sorted(shortlist["events"],
                     key=lambda event: (-event["priority"], event["event_id"]))
    review_queue = []
    exclusions = []
    for event in ordered:
        evaluation = assessed[event["event_id"]]
        sources = []
        seen = set()
        for claim in evaluation["claims"]:
            for citation in claim["evidence"]:
                source_id = citation["source_id"]
                if source_id not in seen:
                    sources.append(records[source_id])
                    seen.add(source_id)
        reasons = ["full_article_evidence_missing", "reporting_independence_unestablished"]
        if any(record["content_scope"] == "headline_only" for record in sources):
            reasons.append("headline_only_evidence")
        # No branch can promote a new/unknown evidence type to confirmed.
        if any(record["content_scope"] != "headline_only" for record in sources):
            reasons.append("unsupported_evidence_type")
        fingerprints = [record["title_fingerprint"] for record in sources]
        if len(set(fingerprints)) != len(fingerprints):
            reasons.append("possible_copied_or_syndicated_headline")
        if any(
            claim["proposed_status"] == "disputed"
            or any(item["relationship"] == "contradicts" for item in claim["evidence"])
            for claim in evaluation["claims"]
        ):
            reasons.append("model_reports_conflicting_headlines")
        exclusions.append({"event_id": event["event_id"], "reasons": reasons})
        if len(review_queue) < 3:
            review_queue.append({
                "event_id": event["event_id"],
                "working_headline": event["working_headline"],
                "category": event["category"],
                "editorial_priority": event["priority"],
                "status": "insufficient_evidence",
                "verification_level": "headline_only",
                "draft_summary": evaluation["draft_summary"],
                "why_it_matters_draft": evaluation["why_it_matters"],
                "draft_origin": "unverified_model_output",
                "claims": evaluation["claims"],
                "sources": sources,
                "unresolved_issues": evaluation["unresolved_issues"],
                "exclusion_reasons": reasons,
            })
    return {
        "schema_version": 1,
        "date_utc": now.date().isoformat(),
        "generated_at": now.isoformat(),
        "model": MODEL,
        "pipeline_status": "completed_with_evidence_shortfall",
        "requested_count": 3,
        "confirmed_count": 0,
        "shortfall_count": 3,
        "shortfall_reason": (
            "Only RSS headlines were retrieved. Full-article or primary evidence "
            "and independent reporting provenance are not established."
        ),
        "items": [],
        "review_queue": review_queue,
        "exclusions": exclusions,
    }


def render_report(briefing):
    """Plain text keeps untrusted model/headline formatting inert."""
    lines = [
        "DAILY NEWS — RESEARCH REVIEW",
        "UTC date: " + briefing["date_utc"],
        "Confirmed stories: 0/3",
        briefing["shortfall_reason"],
        "",
        "UNVERIFIED DRAFT LEADS — NOT A CONFIRMED NEWS BRIEFING",
    ]
    for index, event in enumerate(briefing.get("review_queue", []), 1):
        lines.extend([
            "", f"{index}. {event['working_headline']}",
            "Status: insufficient_evidence (headlines only)",
            "Draft summary: " + event["draft_summary"],
            "Draft significance: " + event["why_it_matters_draft"],
            "Held because: " + ", ".join(event["exclusion_reasons"]),
        ])
        for source in event["sources"]:
            lines.append(f"Source [{source['id']}]: {source['publisher']}")
            lines.append("  Retrieved headline: " + source["title"])
            lines.append("  Collected link: " + source["url"])
    return "\n".join(lines) + "\n"


def run_pipeline(output_root="output", now=None, collector=collect_candidates,
                 shortlister=shortlist_events, searcher=search_google_news,
                 assessor=compare_claims):
    now = now or utc_now()
    folder = Path(output_root) / now.date().isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    # Clear only our own generated files, so a failed rerun cannot expose a
    # stale successful briefing beside its new error status.
    for name in ARTIFACT_FILES:
        (folder / name).unlink(missing_ok=True)
    stage = "collection"
    write_json(folder / "contracts.json", {
        "shortlist": SHORTLIST_SCHEMA, "assessment": ASSESSMENT_SCHEMA,
    })
    try:
        candidates = collector(now)
        write_json(folder / "candidates.json", candidates)
        if candidates["feed_errors"]:
            raise PipelineError("incomplete_source_collection")
        if not candidates["records"]:
            raise PipelineError("no_fresh_approved_candidates")
        stage = "shortlisting"
        shortlist = shortlister(candidates["records"])
        validate_shortlist(shortlist, candidates["records"])
        write_json(folder / "shortlist.json", {
            "origin": "unverified_model_output", **shortlist,
        })
        stage = "followup_search"
        evidence = gather_evidence(shortlist, candidates["records"], now, searcher)
        write_json(folder / "evidence.json", evidence)
        stage = "claim_comparison"
        if shortlist["events"]:
            assessment = assessor(
                shortlist, evidence["records"], evidence["event_sources"]
            )
        else:
            assessment = {"events": []}
        validate_assessment(
            assessment, shortlist, evidence["records"], evidence["event_sources"]
        )
        write_json(folder / "assessment.json", {
            "origin": "unverified_model_output",
            "content_scope": "headline_only", **assessment,
        })
        stage = "evidence_gate"
        briefing = build_briefing(shortlist, assessment, evidence, now)
        write_json(folder / "briefing.json", briefing)
        (folder / "briefing.txt").write_text(render_report(briefing), encoding="utf-8")
        write_json(folder / "run_status.json", {
            "status": "completed_with_evidence_shortfall",
            "model": MODEL, "generated_at": now.isoformat(),
            "candidate_count": len(candidates["records"]),
            "review_lead_count": len(briefing["review_queue"]),
            "confirmed_count": 0,
            "search_failure_count": sum(
                item["status"] != "completed" for item in evidence["searches"]
            ),
        })
        print(f"PASS: research pipeline completed; {len(candidates['records'])} "
              f"candidates, {len(briefing['review_queue'])} draft leads, 0 confirmed.")
        print(f"Evidence shortfall: headline-only sources. Outputs: {folder}")
        return briefing
    except Exception as error:
        # Only fixed messages produced by our own exception types may be saved.
        message = str(error) if isinstance(
            error, (PipelineError, ContractError, GeminiConnectionError)
        ) else "unexpected_pipeline_failure"
        failure = {
            "status": "failed", "stage": stage, "error": message,
            "model": MODEL, "generated_at": now.isoformat(),
        }
        write_json(folder / "run_status.json", failure)
        write_json(folder / "briefing.json", {
            "date_utc": now.date().isoformat(), "pipeline_status": "failed",
            "items": [], "review_queue": [], "confirmed_count": 0,
            "shortfall_count": 3, "failure_stage": stage,
        })
        raise PipelineError(f"{stage}: {message}") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()
    try:
        run_pipeline(args.output_dir)
    except PipelineError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
