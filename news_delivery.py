"""Prepare or send one private Telegram briefing with durable duplicate guards."""
import argparse
import base64
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo


class DeliveryError(ValueError):
    pass


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DeliveryError("delivery_redirect_refused")


def api_json(url, payload, headers, method="POST", allow_404=False, opener=None):
    request = Request(url, data=json.dumps(payload).encode() if payload is not None else None,
                      headers={"Content-Type": "application/json", **headers}, method=method)
    try:
        with (opener or build_opener(NoRedirects())).open(request, timeout=20) as response:
            raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise DeliveryError("delivery_response_size_limit")
        return json.loads(raw)
    except HTTPError as error:
        code = error.code
        error.close()
        if code == 404 and allow_404:
            return None
        raise DeliveryError("delivery_provider_http_failure") from None
    except DeliveryError:
        raise
    except Exception:
        # API URLs contain the bot token. Never log exception text or URLs.
        raise DeliveryError("delivery_network_or_response_failure") from None


def telegram_call(method, payload):
    if method not in {"getChat", "sendMessage", "getUpdates", "getMe"}:
        raise DeliveryError("unsupported_telegram_method")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{20,}", token):
        raise DeliveryError("missing_or_invalid_telegram_bot_token")
    result = api_json("https://api.telegram.org/bot" + token + "/" + method, payload, {})
    if result.get("ok") is not True:
        raise DeliveryError("telegram_request_rejected")
    return result.get("result")


class GitHubLedger:
    """Private state branch; reserve BEFORE sending and never replay uncertainty."""
    branch = "news-delivery-state"
    path = ".daily-news-delivery.json"

    def __init__(self):
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        token = os.environ.get("GITHUB_TOKEN", "")
        sha = os.environ.get("GITHUB_SHA", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or not token or not re.fullmatch(r"[a-f0-9]{40}", sha):
            raise DeliveryError("missing_github_delivery_ledger_configuration")
        self.base = "https://api.github.com/repos/" + repo
        self.headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json"}
        self.sha = None
        self.entries = {}
        self.initial_sha = sha

    def load(self):
        url = self.base + "/contents/" + self.path + "?ref=" + self.branch
        response = api_json(url, None, self.headers, "GET", allow_404=True)
        if response is None:
            ref = api_json(self.base + "/git/ref/heads/" + self.branch, None,
                           self.headers, "GET", allow_404=True)
            if ref is None:
                api_json(self.base + "/git/refs", {"ref": "refs/heads/" + self.branch,
                                                   "sha": self.initial_sha}, self.headers)
            self.entries, self.sha = {}, None
        else:
            try:
                self.entries = json.loads(base64.b64decode(response["content"]))["entries"]
                self.sha = response["sha"]
                if not isinstance(self.entries, dict):
                    raise ValueError
            except Exception:
                raise DeliveryError("invalid_delivery_ledger") from None

    def save(self):
        raw = json.dumps({"schema_version": 1, "entries": self.entries}, sort_keys=True).encode()
        body = {"message": "Record daily news delivery state", "branch": self.branch,
                "content": base64.b64encode(raw).decode()}
        if self.sha:
            body["sha"] = self.sha
        result = api_json(self.base + "/contents/" + self.path, body, self.headers, "PUT")
        try:
            self.sha = result["content"]["sha"]
        except (KeyError, TypeError):
            raise DeliveryError("delivery_ledger_write_unconfirmed") from None

    def reserve(self, key, digest, now):
        self.load()
        if key in self.entries:
            return False
        self.entries[key] = {"status": "reserved", "payload_sha256": digest,
                             "at": now.isoformat()}
        self.save()
        return True

    def finish(self, key, status, message_id=None):
        self.entries[key]["status"] = status
        if message_id is not None:
            self.entries[key]["message_id"] = message_id
        self.save()


def briefing_message(briefing, now):
    try:
        generated = datetime.fromisoformat(briefing["generated_at"])
        if generated.tzinfo is None or not -timedelta(minutes=15) <= now - generated <= timedelta(hours=18):
            raise ValueError
        items = briefing["items"]
        if len(items) > 3 or briefing["confirmed_count"] != len(items):
            raise ValueError
        if briefing["pipeline_status"] not in {"completed", "completed_with_evidence_shortfall"}:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise DeliveryError("briefing_stale_failed_or_invalid") from None
    date = now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    lines = ["Daily News — " + date, f"{len(items)}/3 stories passed the evidence policy.", ""]
    if not items:
        lines.append("No stories met the corroboration requirements today. Unverified drafts were withheld.")
    for index, item in enumerate(items, 1):
        if item.get("status") != "corroborated" or item.get("evidence_policy") != "two_attributed_reporting_chains_v1":
            raise DeliveryError("unverified_item_cannot_be_delivered")
        lines.extend([f"{index}. {item['headline'][:180]}", item["summary"][:400]])
        lines.append("Why it matters (analysis): " + item["why_it_matters_analysis"][:180])
        for source in item["sources"][:2]:
            from news_fetcher import approved_publisher
            if approved_publisher(source["url"]) != source["publisher"]:
                raise DeliveryError("invalid_delivery_source_url")
            lines.append(source["publisher"] + ": " + source["url"])
        lines.append("")
    lines.append("Corroboration uses retrieved excerpts and attributed reporting; it is not a guarantee of truth.")
    text = "\n".join(lines)
    if len(text.encode("utf-16-le")) // 2 > 3900:
        raise DeliveryError("telegram_message_size_limit")
    return text


def send_message(text, now, kind="briefing", ledger=None, caller=telegram_call):
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not re.fullmatch(r"[1-9]\d{3,19}", chat_id):
        raise DeliveryError("missing_or_invalid_private_telegram_chat_id")
    chat = caller("getChat", {"chat_id": chat_id})
    if not isinstance(chat, dict) or chat.get("type") != "private" or str(chat.get("id")) != chat_id:
        raise DeliveryError("telegram_private_recipient_not_verified")
    day = now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    key = day + ":" + kind + ":" + hashlib.sha256(chat_id.encode()).hexdigest()[:16]
    digest = hashlib.sha256(text.encode()).hexdigest()
    ledger = ledger or GitHubLedger()
    if not ledger.reserve(key, digest, now):
        return {"status": "duplicate_or_uncertain_delivery_withheld", "date_korea": day}
    try:
        response = caller("sendMessage", {"chat_id": chat_id, "text": text,
                                           "link_preview_options": {"is_disabled": True}})
        message_id = response.get("message_id") if isinstance(response, dict) else None
        if type(message_id) is not int:
            raise DeliveryError("telegram_delivery_not_confirmed")
    except Exception:
        ledger.finish(key, "delivery_unknown")
        raise DeliveryError("telegram_delivery_unknown_no_automatic_retry") from None
    ledger.finish(key, "accepted_by_telegram", message_id)
    return {"status": "accepted_by_telegram", "date_korea": day}


def load_revalidated_briefing(folder):
    from news_editor import validate_assessment, validate_shortlist
    from news_pipeline import build_briefing
    def read(name):
        return json.loads((Path(folder) / (name + ".json")).read_text())
    c, s, a, e, b = map(read, ("candidates", "shortlist", "assessment", "evidence", "briefing"))
    s, a = {"events": s["events"]}, {"events": a["events"]}
    validate_shortlist(s, c["records"])
    validate_assessment(a, s, e["records"], e["event_sources"])
    if build_briefing(s, a, e, datetime.fromisoformat(b["generated_at"])) != b:
        raise DeliveryError("briefing_does_not_match_saved_evidence")
    return b


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--failure-notice", action="store_true")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    output = Path("output/delivery")
    output.mkdir(parents=True, exist_ok=True)
    try:
        if args.failure_notice:
            text = "Daily News could not complete today's research run. No news briefing was sent. Check GitHub Actions for diagnostics."
        else:
            folders = sorted(Path("output").glob("*/briefing.json"))
            if not folders:
                raise DeliveryError("no_generated_briefing")
            text = briefing_message(load_revalidated_briefing(folders[-1].parent), now)
        (output / "preview.txt").write_text(text, encoding="utf-8")
        if args.send:
            result = send_message(text, now, "failure" if args.failure_notice else "briefing")
        else:
            result = {"status": "dry_run_no_message_sent"}
        (output / "status.json").write_text(json.dumps(result, indent=2) + "\n")
        print("PASS: delivery status: " + result["status"])
        return 0
    except Exception as error:
        reason = str(error) if isinstance(error, DeliveryError) else "delivery_validation_failure"
        (output / "status.json").write_text(json.dumps({"status": "failed", "error": reason}) + "\n")
        print("FAIL: " + reason)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
