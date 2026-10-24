"""Export a successful research briefing as a bounded, unverified web edition.

This exporter does not promote evidence or invent longer article bodies.
"""
import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


class WebExportError(ValueError):
    pass


def source_url(value):
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == 'https' and parsed.hostname
                 and not parsed.username and not parsed.password)
    except (ValueError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise WebExportError('invalid_source_url')
    return value


def export_edition(briefing, evidence, run_url):
    if (briefing.get('pipeline_status') != 'completed_with_evidence_shortfall'
            or briefing.get('confirmed_count') != 0 or briefing.get('items') != []):
        raise WebExportError('unsupported_or_failed_briefing')
    if not re.fullmatch(r'https://github.com/johwin25/daily_news/actions/runs/[0-9]+', run_url):
        raise WebExportError('invalid_run_url')
    edition_date = date.fromisoformat(briefing['date_utc']).isoformat()
    generated = datetime.fromisoformat(briefing['generated_at'])
    if generated.tzinfo is None:
        raise WebExportError('missing_generation_timezone')
    known = {r['id']: r for r in evidence['records']}
    events = evidence['event_sources']
    stories = []
    seen_events = set()
    for lead in briefing['review_queue']:
        if len(stories) >= 3:
            raise WebExportError('too_many_stories')
        event_id = lead['event_id']
        if event_id in seen_events or event_id not in events:
            raise WebExportError('invalid_event')
        seen_events.add(event_id)
        if lead['status'] != 'insufficient_evidence':
            raise WebExportError('unsupported_verification_status')
        citations = []
        claims = []
        for claim in lead['claims']:
            claim_ids = []
            for citation in claim['evidence']:
                sid = citation['source_id']
                if sid not in known or sid not in events[event_id]:
                    raise WebExportError('invalid_source_reference')
                record = known[sid]
                scope = citation['scope']
                if scope == 'headline':
                    corpus = record['title']
                elif scope == 'article_text' and record.get('article', {}).get('status') == 'retrieved':
                    corpus = record['article']['text']
                else:
                    raise WebExportError('unretrieved_evidence_scope')
                if len(citation['quote'].strip()) < 8 or citation['quote'] not in corpus:
                    raise WebExportError('invented_source_quote')
                claim_ids.append(sid)
                if sid not in citations:
                    citations.append(sid)
            if not claim_ids:
                raise WebExportError('claim_without_sources')
            claims.append({'text': claim['text'], 'source_ids': claim_ids})
        if not claims:
            raise WebExportError('story_without_claims')
        sources = []
        for sid in citations:
            record = known[sid]
            article = record.get('article', {})
            original = article.get('original_url') if article.get('status') == 'retrieved' else None
            sources.append({
                'id': sid, 'publisher': record['publisher'], 'title': record['title'],
                'url': source_url(original or record['url']),
                'published_at': record['published_at'],
                'content_scope': record['content_scope'],
            })
        stories.append({
            'id': event_id, 'category': lead['category'], 'title': lead['working_headline'],
            # Only the explicitly cited claims appear as the preview; the broader
            # model draft can contain details not backed by these selected sources.
            'summary': ' '.join(c['text'] for c in claims),
            'significance': lead['why_it_matters_draft'],
            'verification_status': 'insufficient_evidence',
            'verification_level': lead['verification_level'], 'claims': claims,
            'sources': sources, 'limitations': lead['exclusion_reasons'],
            'unresolved_issues': lead['unresolved_issues'],
        })
    result = {
        'schema_version': 1, 'date_utc': edition_date,
        'generated_at': generated.isoformat(), 'source_run_url': run_url,
        'content_kind': 'research_briefing', 'confirmed_count': 0,
        'requested_count': 3, 'stories': stories,
        'notice': 'Unverified research leads. Source links do not establish independent corroboration.',
    }
    raw = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if len(raw.encode('utf-8')) > 150_000:
        raise WebExportError('edition_size_limit')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', default='output')
    parser.add_argument('--date', default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument('--run-url', required=True)
    args = parser.parse_args(argv)
    root = Path(args.output_root)
    destination = root / 'web' / 'edition.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    try:
        folder = root / date.fromisoformat(args.date).isoformat()
        briefing = json.loads((folder / 'briefing.json').read_text())
        evidence = json.loads((folder / 'evidence.json').read_text())
        result = export_edition(briefing, evidence, args.run_url)
        temporary = destination.with_suffix('.tmp')
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(destination)
    except (OSError, ValueError, KeyError, TypeError):
        print('FAIL: web edition validation or export failed.', file=sys.stderr)
        return 1
    print(f"PASS: exported {len(result['stories'])} unverified leads; 0 confirmed.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
