"""Adversarial contracts and fake HTTP responses; no network or real key."""
import copy
import io
import json
import os
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from news_analyzer import GeminiConnectionError
from news_collector import normalize_article
from news_contracts import (
    ASSESSMENT_SCHEMA, ContractError, SHORTLIST_SCHEMA, provider_schema,
    validate_contract,
)
from news_editor import call_model, validate_assessment, validate_shortlist
from test_news_collector import NOW, article

FAKE_KEY = "synthetic-secret-never-send"


def records():
    return [
        normalize_article(article(url="https://news.google.com/a"), NOW, "feed-a", "Science"),
        normalize_article(article(
            url="https://news.google.com/b", publisher="BBC News",
            publisher_url="https://bbc.com",
            title="SYNTHETIC: Research team publishes new material - BBC News",
        ), NOW, "feed-b", "Science"),
    ]


def shortlist(rows=None):
    rows = rows or records()
    return {"events": [{
        "event_id": "event_1",
        "working_headline": "SYNTHETIC: New material research",
        "category": "Science", "priority": 80,
        "rationale": "Synthetic significance for testing only.",
        "source_ids": [row["id"] for row in rows],
        "search_query": "SYNTHETIC new material research",
    }]}


def assessment(rows=None):
    rows = rows or records()
    return {"events": [{
        "event_id": "event_1",
        "draft_summary": "SYNTHETIC draft: headlines mention new material research.",
        "why_it_matters": "SYNTHETIC potential engineering relevance.",
        "unresolved_issues": ["Full articles not retrieved; independence unknown."],
        "claims": [{
            "text": "SYNTHETIC: A research team publishes new material.",
            "proposed_status": "corroborated",
            "evidence": [
                {"source_id": row["id"], "relationship": "supports", "quote": row["title"]}
                for row in rows
            ],
        }],
    }]}


class EditorContractTests(unittest.TestCase):
    def test_provider_schema_stays_small_but_local_array_limits_still_apply(self):
        schema = provider_schema(ASSESSMENT_SCHEMA)
        encoded = json.dumps(schema)
        for keyword in ("maxItems", "minItems", "maxLength", "minLength"):
            self.assertNotIn(keyword, encoded)
        self.assertIn('"required"', encoded)
        value = assessment()
        value["events"][0]["claims"] *= 5
        with self.assertRaises(ContractError):
            validate_contract(value, ASSESSMENT_SCHEMA)

    def test_invented_citations_are_rejected(self):
        value = shortlist()
        value["events"][0]["source_ids"] = ["src_invented"]
        with self.assertRaises(ContractError):
            validate_shortlist(value, records())

    def test_unexpected_keys_and_boolean_scores_are_rejected(self):
        for change in ({"url": "https://invented.example"}, {"priority": True}):
            value = shortlist()
            value["events"][0].update(change)
            with self.subTest(change=change):
                with self.assertRaises(ContractError):
                    validate_contract(value, SHORTLIST_SCHEMA)

    def test_duplicate_events_and_reused_sources_are_rejected(self):
        for duplicate_id in (True, False):
            value = shortlist()
            second = copy.deepcopy(value["events"][0])
            if not duplicate_id:
                second["event_id"] = "event_2"
            value["events"].append(second)
            with self.assertRaises(ContractError):
                validate_shortlist(value, records())

    def test_oversized_and_multiline_queries_are_rejected(self):
        for query in ("x" * 161, "safe\ninjected"):
            value = shortlist()
            value["events"][0]["search_query"] = query
            with self.assertRaises(ContractError):
                validate_shortlist(value, records())

    def test_invented_quotes_and_wrong_events_are_rejected(self):
        rows = records()
        value = assessment()
        value["events"][0]["claims"][0]["evidence"][0]["quote"] = "invented detail"
        with self.assertRaises(ContractError):
            validate_assessment(value, shortlist(), rows,
                                {"event_1": [row["id"] for row in rows]})
        value = assessment()
        value["events"][0]["event_id"] = "event_2"
        with self.assertRaises(ContractError):
            validate_assessment(value, shortlist(), rows, {"event_1": []})

    def test_sources_from_another_event_are_rejected(self):
        rows = records()
        with self.assertRaises(ContractError):
            validate_assessment(assessment(), shortlist(), rows,
                                {"event_1": [rows[0]["id"]]})

    def test_fake_http_success_is_validated_and_keeps_secret_out_of_prompt(self):
        envelope = {"candidates": [{
            "finishReason": "STOP",
            "content": {"parts": [{"text": json.dumps(shortlist())}]},
        }]}
        response = MagicMock(status=200)
        response.read.return_value = json.dumps(envelope).encode()
        with patch.dict(os.environ, {"GEMINI_API_KEY": FAKE_KEY}):
            with patch("news_editor.urlopen") as opener:
                opener.return_value.__enter__.return_value = response
                result = call_model("test task", {"records": []}, SHORTLIST_SCHEMA)
        self.assertEqual(result, shortlist())
        opener.assert_called_once()
        request = opener.call_args.args[0]
        self.assertIn("gemini-3.5-flash-lite", request.full_url)
        self.assertNotIn(FAKE_KEY.encode(), request.data)
        self.assertNotIn(FAKE_KEY, request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), FAKE_KEY)
        body = json.loads(request.data)
        self.assertNotIn("tools", body)
        self.assertEqual(body["generationConfig"]["maxOutputTokens"], 8192)

    def test_truncated_or_invalid_model_output_fails(self):
        for finish, text in (("MAX_TOKENS", "{}"), ("STOP", "not-json"),
                             ("STOP", "NaN"), ("STOP", "{}")):
            response = MagicMock(status=200)
            response.read.return_value = json.dumps({"candidates": [{
                "finishReason": finish, "content": {"parts": [{"text": text}]},
            }]}).encode()
            with patch.dict(os.environ, {"GEMINI_API_KEY": FAKE_KEY}):
                with patch("news_editor.urlopen") as opener:
                    opener.return_value.__enter__.return_value = response
                    with self.assertRaises(ContractError):
                        call_model("test", {}, SHORTLIST_SCHEMA)

    def test_http_failure_is_not_retried_or_echoed(self):
        error = HTTPError("https://example.invalid", 503, FAKE_KEY, {},
                          io.BytesIO(json.dumps({"error": {
                              "status": "UNAVAILABLE", "message": FAKE_KEY,
                          }}).encode()))
        with patch.dict(os.environ, {"GEMINI_API_KEY": FAKE_KEY}):
            with patch("news_editor.urlopen", side_effect=error) as opener:
                with self.assertRaises(GeminiConnectionError) as caught:
                    call_model("test", {}, SHORTLIST_SCHEMA)
                opener.assert_called_once()
        self.assertNotIn(FAKE_KEY, str(caught.exception))

    def test_input_size_limit_stops_before_network(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": FAKE_KEY}):
            with patch("news_editor.urlopen") as opener:
                with self.assertRaises(ContractError):
                    call_model("test", {"title": "x" * 100001}, SHORTLIST_SCHEMA)
                opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
