import copy
import io
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import URLError

from news_delivery import (DeliveryError, GitHubLedger, api_json, briefing_message,
                           load_revalidated_briefing, send_message)
from news_pipeline import build_briefing
from test_news_collector import NOW
from test_news_corroboration import corroborated_fixture


def briefing():
    rows, assessment, shortlist = corroborated_fixture()
    return build_briefing(shortlist, assessment, {"records": rows}, NOW)


class MemoryLedger:
    def __init__(self):
        self.entries = {}

    def reserve(self, key, digest, now):
        if key in self.entries:
            return False
        self.entries[key] = "reserved"
        return True

    def finish(self, key, status, message_id=None):
        self.entries[key] = status


class DeliveryTests(unittest.TestCase):
    def test_only_corroborated_claims_and_checked_source_links_are_in_preview(self):
        text = briefing_message(briefing(), NOW)
        self.assertIn("1/3", text)
        self.assertIn("theguardian.com", text)
        self.assertNotIn("MODEL INVENTION", text)
        self.assertIn("analysis", text)

    def test_zero_supported_stories_delivers_a_shortfall_without_drafts(self):
        value = briefing()
        value["items"], value["confirmed_count"] = [], 0
        value["review_queue"] = [{"working_headline": "UNVERIFIED INVENTION"}]
        text = briefing_message(value, NOW)
        self.assertIn("0/3", text)
        self.assertNotIn("UNVERIFIED INVENTION", text)

    def test_stale_failed_and_unverified_briefings_are_rejected(self):
        with self.assertRaises(DeliveryError):
            briefing_message(briefing(), NOW + timedelta(hours=19))
        for change in (lambda b:b.update(pipeline_status="failed"),
                       lambda b:b['items'][0].update(status="insufficient_evidence")):
            value = briefing()
            change(value)
            with self.assertRaises(DeliveryError):
                briefing_message(value, NOW)

    def test_group_or_mismatched_private_chat_is_never_messaged(self):
        for chat in ({"type": "group", "id": 12345}, {"type": "private", "id": 99999}):
            caller = Mock(return_value=chat)
            ledger = MemoryLedger()
            with patch.dict('os.environ', {"TELEGRAM_CHAT_ID": "12345"}):
                with self.assertRaisesRegex(DeliveryError, "recipient_not_verified"):
                    send_message("Test", NOW, ledger=ledger, caller=caller)
            self.assertEqual(caller.call_count, 1)
            self.assertEqual(ledger.entries, {})

    def test_durable_reservation_precedes_send_and_duplicate_is_not_replayed(self):
        ledger = MemoryLedger()
        calls = []
        def caller(method, payload):
            calls.append(method)
            if method == "getChat":
                return {"type": "private", "id": 12345}
            self.assertIn("reserved", ledger.entries.values())
            return {"message_id": 17}
        with patch.dict('os.environ', {"TELEGRAM_CHAT_ID": "12345"}):
            self.assertEqual(send_message("Test", NOW, ledger=ledger, caller=caller)["status"],
                             "accepted_by_telegram")
            result = send_message("Different payload same day", NOW, ledger=ledger, caller=caller)
        self.assertEqual(result["status"], "duplicate_or_uncertain_delivery_withheld")
        self.assertEqual(calls.count("sendMessage"), 1)

    def test_ambiguous_timeout_is_not_retried_and_never_echoes_secret(self):
        ledger = MemoryLedger()
        caller = Mock(side_effect=[{"type": "private", "id": 12345}, TimeoutError("SYNTHETIC_SECRET")])
        with patch.dict('os.environ', {"TELEGRAM_CHAT_ID": "12345"}):
            with self.assertRaises(DeliveryError) as caught:
                send_message("Test", NOW, ledger=ledger, caller=caller)
        self.assertNotIn("SYNTHETIC_SECRET", str(caught.exception))
        self.assertEqual(list(ledger.entries.values()), ["delivery_unknown"])
        self.assertEqual(caller.call_count, 2)

    def test_ledger_failure_prevents_the_send(self):
        caller = Mock(return_value={"type": "private", "id": 12345})
        ledger = Mock()
        ledger.reserve.side_effect = DeliveryError("delivery_ledger_write_unconfirmed")
        with patch.dict('os.environ', {"TELEGRAM_CHAT_ID": "12345"}):
            with self.assertRaises(DeliveryError):
                send_message("Test", NOW, ledger=ledger, caller=caller)
        self.assertEqual(caller.call_count, 1)

    def test_missing_chat_configuration_never_calls_telegram(self):
        caller = Mock()
        with patch.dict('os.environ', {"TELEGRAM_CHAT_ID": ""}):
            with self.assertRaises(DeliveryError):
                send_message("Test", NOW, ledger=MemoryLedger(), caller=caller)
        caller.assert_not_called()

    def test_provider_network_exceptions_never_expose_token_urls(self):
        opener = Mock()
        opener.open.side_effect = URLError("https://example.invalid/botSYNTHETIC_SECRET")
        with self.assertRaises(DeliveryError) as caught:
            api_json("https://example.invalid", {}, {}, opener=opener)
        self.assertNotIn("SYNTHETIC_SECRET", str(caught.exception))

    def test_saved_briefing_is_rebuilt_before_delivery(self):
        rows, assessment, shortlist = corroborated_fixture()
        evidence = {"records": rows, "event_sources": {"event_1": [r["id"] for r in rows]}}
        original = build_briefing(shortlist, assessment, evidence, NOW)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for name, value in (("candidates", {"records": rows}), ("shortlist", shortlist),
                                ("assessment", assessment), ("evidence", evidence), ("briefing", original)):
                (folder / (name + '.json')).write_text(json.dumps(value))
            self.assertEqual(load_revalidated_briefing(folder), original)
            tampered = copy.deepcopy(original)
            tampered['items'][0]['summary'] = 'Unsupported injected claim'
            (folder / 'briefing.json').write_text(json.dumps(tampered))
            with self.assertRaisesRegex(DeliveryError, "does_not_match_saved_evidence"):
                load_revalidated_briefing(folder)

    def test_failure_alert_has_separate_once_per_day_identity(self):
        ledger = MemoryLedger()
        caller = Mock(side_effect=lambda method,payload: {"type":"private","id":12345}
                      if method=="getChat" else {"message_id":1})
        with patch.dict('os.environ', {"TELEGRAM_CHAT_ID": "12345"}):
            send_message("Failure", NOW, "failure", ledger, caller)
            send_message("Briefing", NOW, "briefing", ledger, caller)
        self.assertEqual(len(ledger.entries), 2)

    def test_github_ledger_reserves_on_state_branch_and_uses_updated_file_sha(self):
        import base64
        response = {"sha": "first-file-sha", "content": base64.b64encode(
            json.dumps({"entries": {}}).encode()).decode()}
        api = Mock(side_effect=[response, {"content":{"sha":"reserved-file-sha"}},
                               {"content":{"sha":"sent-file-sha"}}])
        with patch.dict('os.environ', {"GITHUB_REPOSITORY":"owner/repo", "GITHUB_TOKEN":"SYNTHETIC",
                                       "GITHUB_SHA":"a"*40}):
            with patch('news_delivery.api_json', api):
                ledger = GitHubLedger()
                self.assertTrue(ledger.reserve('day:briefing:recipient', 'digest', NOW))
                ledger.finish('day:briefing:recipient', 'accepted_by_telegram', 1)
        reserve_body = api.call_args_list[1].args[1]
        finish_body = api.call_args_list[2].args[1]
        self.assertEqual(reserve_body['branch'], 'news-delivery-state')
        self.assertEqual(finish_body['sha'], 'reserved-file-sha')
        self.assertNotIn('SYNTHETIC', base64.b64decode(finish_body['content']).decode())


if __name__ == "__main__":
    unittest.main()
