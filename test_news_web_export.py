import copy
import unittest
from news_web_export import WebExportError, export_edition

RUN = 'https://github.com/johwin25/daily_news/actions/runs/12345'


def fixture():
    record = {'id': 'source_1', 'publisher': 'BBC News',
              'title': 'Researchers announce a new materials study',
              'url': 'https://www.bbc.com/news/articles/abcdefgh',
              'published_at': '2026-10-24T01:00:00+00:00', 'content_scope': 'headline_only'}
    lead = {'event_id': 'event_1', 'category': 'Science', 'working_headline': 'A materials study',
            'status': 'insufficient_evidence', 'verification_level': 'headline_only',
            'draft_summary': 'An uncited draft detail must not enter the preview.',
            'why_it_matters_draft': 'Potential relevance remains uncertain.',
            'claims': [{'text': 'Researchers announced a study.', 'evidence': [{
                'source_id': 'source_1', 'scope': 'headline', 'quote': 'Researchers announce'}]}],
            'exclusion_reasons': ['reporting_independence_unestablished'], 'unresolved_issues': []}
    return ({'pipeline_status': 'completed_with_evidence_shortfall', 'confirmed_count': 0,
             'items': [], 'date_utc': '2026-10-24', 'generated_at': '2026-10-24T03:00:00+00:00',
             'review_queue': [lead]},
            {'records': [record], 'event_sources': {'event_1': ['source_1']}})


class WebExportTests(unittest.TestCase):
    def test_exports_cited_claims_without_padding_or_promotion(self):
        b, e = fixture()
        d = export_edition(b, e, RUN)
        self.assertEqual(len(d['stories']), 1)
        self.assertEqual(d['confirmed_count'], 0)
        self.assertEqual(d['stories'][0]['summary'], 'Researchers announced a study.')
        self.assertNotIn('uncited', str(d))
        self.assertEqual(d['source_run_url'], RUN)

    def test_failed_or_promoted_briefing_is_rejected(self):
        for change in ({'pipeline_status': 'failed'}, {'confirmed_count': 1}, {'items': [{}]}):
            b, e = fixture(); b.update(change)
            with self.assertRaises(WebExportError): export_edition(b, e, RUN)

    def test_wrong_event_and_fabricated_quotes_fail(self):
        for key, value in [('source_id', 'missing'), ('quote', 'Fabricated quote'),
                           ('scope', 'article_text')]:
            b, e = fixture(); b['review_queue'][0]['claims'][0]['evidence'][0][key] = value
            with self.assertRaises(WebExportError): export_edition(b, e, RUN)
        b, e = fixture(); e['event_sources']['event_1'] = []
        with self.assertRaises(WebExportError): export_edition(b, e, RUN)

    def test_empty_edition_stays_empty(self):
        b, e = fixture(); b['review_queue'] = []
        self.assertEqual(export_edition(b, e, RUN)['stories'], [])

    def test_duplicate_events_and_over_three_leads_rejected(self):
        b, e = fixture(); b['review_queue'] *= 2
        with self.assertRaises(WebExportError): export_edition(b, e, RUN)

    def test_insecure_source_and_wrong_run_rejected(self):
        b, e = fixture(); e['records'][0]['url'] = 'javascript:alert(1)'
        with self.assertRaises(WebExportError): export_edition(b, e, RUN)
        b, e = fixture()
        with self.assertRaises(WebExportError): export_edition(b, e, 'https://example.com')

    def test_retrieved_article_keeps_original_link_and_status(self):
        b, e = fixture()
        e['records'][0].update(content_scope='article_text', article={
            'status': 'retrieved', 'original_url': 'https://www.bbc.com/news/articles/abcdefgi',
            'text': 'Researchers announce a new materials study'})
        b['review_queue'][0]['claims'][0]['evidence'][0]['scope'] = 'article_text'
        self.assertEqual(export_edition(b, e, RUN)['stories'][0]['sources'][0]['url'],
                         'https://www.bbc.com/news/articles/abcdefgi')
        self.assertEqual(export_edition(b, e, RUN)['stories'][0]['verification_status'],
                         'insufficient_evidence')


if __name__ == '__main__': unittest.main()
