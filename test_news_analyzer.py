"""Offline Gemini boundary tests. No real key or API request is used."""
import copy
import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import news_analyzer as analyzer

FAKE_KEY = "offline-test-key-not-a-real-credential"
VALID_REPLY = {
    "candidates": [{
        "finishReason": "STOP",
        "content": {"parts": [{"text": "DAILY_NEWS_OK"}]},
    }],
}


class GeminiConnectionTests(unittest.TestCase):
    def run_with_reply(self, raw, status=200):
        response = MagicMock()
        response.status = status
        response.read.return_value = raw
        with patch("news_analyzer.urlopen") as open_mock:
            open_mock.return_value.__enter__.return_value = response
            result = analyzer.main()
        return result, open_mock, response

    def setUp(self):
        self.env = patch.dict(os.environ, {"GEMINI_API_KEY": FAKE_KEY})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.out = io.StringIO()
        self.err = io.StringIO()
        out_patch = redirect_stdout(self.out)
        err_patch = redirect_stderr(self.err)
        out_patch.__enter__()
        err_patch.__enter__()
        self.addCleanup(out_patch.__exit__, None, None, None)
        self.addCleanup(err_patch.__exit__, None, None, None)

    def test_success_uses_header_and_one_bounded_request(self):
        result, open_mock, response = self.run_with_reply(
            json.dumps(VALID_REPLY).encode()
        )
        self.assertEqual(result, 0)
        open_mock.assert_called_once()
        request = open_mock.call_args.args[0]
        self.assertEqual(open_mock.call_args.kwargs["timeout"], 45)
        self.assertEqual(request.get_header("X-goog-api-key"), FAKE_KEY)
        self.assertNotIn(FAKE_KEY, request.full_url)
        self.assertNotIn(FAKE_KEY.encode(), request.data)
        self.assertEqual(request.get_method(), "POST")
        self.assertNotIn("tools", json.loads(request.data))
        response.read.assert_called_once_with(analyzer.MAX_RESPONSE_BYTES + 1)
        self.assertIn("PASS:", self.out.getvalue())
        self.assertNotIn(FAKE_KEY, self.out.getvalue() + self.err.getvalue())

    def test_missing_or_blank_key_makes_no_request(self):
        for key in ("", "   "):
            with self.subTest(key=key):
                with patch.dict(os.environ, {"GEMINI_API_KEY": key}):
                    with patch("news_analyzer.urlopen") as open_mock:
                        self.assertEqual(analyzer.main(), 1)
                        open_mock.assert_not_called()

    def test_http_failures_are_safe_and_not_retried(self):
        for code in (400, 401, 403, 404, 429, 503):
            with self.subTest(code=code):
                error = HTTPError(analyzer.ENDPOINT, code, FAKE_KEY, {}, io.BytesIO(FAKE_KEY.encode()))
                with patch("news_analyzer.urlopen", side_effect=error) as open_mock:
                    self.assertEqual(analyzer.main(), 1)
                    open_mock.assert_called_once()
                self.assertIn(f"HTTP {code}", self.err.getvalue())
        self.assertNotIn(FAKE_KEY, self.out.getvalue() + self.err.getvalue())

    def test_network_failures_do_not_leak_exception_details(self):
        for error in (URLError(FAKE_KEY), TimeoutError(FAKE_KEY)):
            with self.subTest(error=type(error).__name__):
                with patch("news_analyzer.urlopen", side_effect=error) as open_mock:
                    self.assertEqual(analyzer.main(), 1)
                    open_mock.assert_called_once()
        self.assertNotIn(FAKE_KEY, self.out.getvalue() + self.err.getvalue())

    def test_invalid_or_missing_output_is_rejected_without_echoing(self):
        for raw in (b"not-json", b"\xff", b"null", b"[]", b"{}", b'{"candidates":[]}',
                    json.dumps({"error": FAKE_KEY}).encode()):
            with self.subTest(raw=raw):
                result, _, _ = self.run_with_reply(raw)
                self.assertEqual(result, 1)
        self.assertNotIn(FAKE_KEY, self.out.getvalue() + self.err.getvalue())

    def test_incomplete_and_unexpected_text_are_rejected(self):
        for finish, text in (("MAX_TOKENS", "DAILY_NEWS_OK"),
                             ("SAFETY", "DAILY_NEWS_OK"),
                             ("STOP", FAKE_KEY), ("STOP", "")):
            reply = copy.deepcopy(VALID_REPLY)
            reply["candidates"][0]["finishReason"] = finish
            reply["candidates"][0]["content"]["parts"][0]["text"] = text
            result, _, _ = self.run_with_reply(json.dumps(reply).encode())
            self.assertEqual(result, 1)
        self.assertNotIn(FAKE_KEY, self.out.getvalue() + self.err.getvalue())

    def test_thought_text_cannot_pass_as_the_answer(self):
        reply = copy.deepcopy(VALID_REPLY)
        reply["candidates"][0]["content"]["parts"][0]["thought"] = True
        result, _, _ = self.run_with_reply(json.dumps(reply).encode())
        self.assertEqual(result, 1)

    def test_oversized_response_is_rejected(self):
        result, _, _ = self.run_with_reply(b"x" * (analyzer.MAX_RESPONSE_BYTES + 1))
        self.assertEqual(result, 1)

    def test_non_200_response_is_rejected(self):
        result, _, _ = self.run_with_reply(json.dumps(VALID_REPLY).encode(), 204)
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
