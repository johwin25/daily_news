"""Claim-level publication gate based on retrieved, attributed reporting.

Corroborated means the explicit evidence policy passed. It is not a guarantee
of truth. Unknown origin, shared attribution and unsupported details stay held.
"""
import hashlib
import re
from itertools import combinations

from news_provenance import reporting_provenance


def text_shingles(text):
    words = re.findall(r"\w+", text.casefold())
    return {tuple(words[i:i + 5]) for i in range(max(0, len(words) - 4))}


def copied_text(left, right):
    if left.strip() == right.strip():
        return True
    a, b = text_shingles(left), text_shingles(right)
    if min(len(a), len(b)) < 20:
        return True  # Too little distinct text to establish separate reporting.
    return len(a & b) / min(len(a), len(b)) >= 0.65


def citation_origin(citation, record, now):
    from news_fetcher import approved_publisher
    article = record.get("article", {})
    text = article.get("text", "")
    quote = citation.get("quote", "")
    if (citation.get("scope") != "article_text" or citation.get("relationship") != "supports"
            or article.get("status") != "retrieved" or record.get("content_scope") != "article_text"
            or article.get("source_id") != record["id"] or not quote or quote not in text
            or hashlib.sha256(text.encode()).hexdigest() != article.get("text_sha256")
            or article.get("wire_mentions")
            or approved_publisher(article.get("retrieved_url", "")) != record["publisher"]):
        return None
    # The quoted support itself must identify this outlet's own reporting.
    origin = reporting_provenance({"text": quote, "metadata": article.get("metadata", {})},
                                  record["publisher"], now)
    if origin["origin"] != "publisher_self_attributed_reporting":
        return None
    return origin


def check_event(event, records, now):
    reasons, proofs = [], []
    if not event.get("claims"):
        return {"passed": False, "reasons": ["no_material_claims"], "claim_proofs": []}
    for claim in event["claims"]:
        if (claim["proposed_status"] != "corroborated"
                or any(c["relationship"] == "contradicts" for c in claim["evidence"])):
            reasons.append("claim_disputed_or_not_corroborated")
            continue
        eligible = []
        for citation in claim["evidence"]:
            record = records.get(citation["source_id"])
            if record is None:
                continue
            origin = citation_origin(citation, record, now)
            if origin:
                eligible.append((record, origin, citation))
        pair = None
        for left, right in combinations(eligible, 2):
            if left[1]["reporting_chain"] == right[1]["reporting_chain"]:
                continue
            if set(name.casefold() for name in left[1]["authors"]) & set(
                    name.casefold() for name in right[1]["authors"]):
                continue
            if copied_text(left[0]["article"]["text"], right[0]["article"]["text"]):
                continue
            pair = (left, right)
            break
        if pair is None:
            reasons.append("two_attributed_reporting_chains_missing")
        else:
            proofs.append({"claim": claim["text"], "support": [
                {"source_id": item[0]["id"], "publisher": item[0]["publisher"],
                 "reporting_chain": item[1]["reporting_chain"],
                 "authors": item[1]["authors"], "page_published_at": item[1]["page_published_at"],
                 "quote": item[2]["quote"], "url": item[0]["article"]["retrieved_url"]}
                for item in pair]})
    return {"passed": not reasons and len(proofs) == len(event["claims"]),
            "reasons": sorted(set(reasons)), "claim_proofs": proofs}


def confirmed_item(event, decision, shortlist_event):
    # Publish only checked claim text; free-form draft summaries cannot add facts.
    claims = [proof["claim"] for proof in decision["claim_proofs"]]
    links = {}
    for proof in decision["claim_proofs"]:
        for support in proof["support"]:
            links[support["source_id"]] = {key: support[key] for key in ("source_id", "publisher", "url")}
    return {"event_id": event["event_id"], "status": "corroborated",
            "headline": claims[0], "summary": " ".join(claims),
            "category": shortlist_event["category"],
            "why_it_matters_analysis": event["why_it_matters"],
            "claims": decision["claim_proofs"], "sources": list(links.values()),
            "evidence_policy": "two_attributed_reporting_chains_v1",
            "limitations": ["Automated comparison of retrieved excerpts; not a guarantee of truth."]}
