"""Stage 3A: one Gemini connection check, not news analysis or verification."""
import json
import os
import sys
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MODEL = "gemini-3.5-flash-lite"
ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}"
    ":generateContent"
)
EXPECTED_REPLY = "DAILY_NEWS_OK"
MAX_RESPONSE_BYTES = 100_000


class GeminiConnectionError(Exception):
    """A safe diagnostic that contains no key or raw provider response."""



# Only these fixed labels and hints can reach logs. Provider messages and
# metadata may contain keys, project IDs, or URLs, so they are never printed.
HTTP_REASON_HINTS = {
    "SERVICE_DISABLED": "Enable the Generative Language API in the key's project.",
    "API_KEY_SERVICE_BLOCKED": "The key's API restrictions do not permit the Generative Language API.",
    "API_KEY_HTTP_REFERRER_BLOCKED": "The key's website/referrer restriction blocks this server request.",
    "API_KEY_IP_ADDRESS_BLOCKED": "The key's IP restriction blocks this runner.",
    "API_KEY_ANDROID_APP_BLOCKED": "The key's Android app restriction blocks this server request.",
    "API_KEY_IOS_APP_BLOCKED": "The key's iOS app restriction blocks this server request.",
    "API_KEY_INVALID": "Check that GitHub stores the actual Gemini key value.",
    "API_KEY_EXPIRED": "Replace the expired key in GitHub Actions secrets.",
    "IAM_PERMISSION_DENIED": "Check the key's project and service-account permissions.",
    "CONSUMER_INVALID": "Check the Google Cloud project associated with this key.",
    "BILLING_DISABLED": "Check free-tier project eligibility; do not enable paid billing automatically.",
    "KEY_REPORTED_LEAKED": "Google reports this key as leaked; create a replacement and update the GitHub secret.",
    "SCHEMA_TOO_COMPLEX": "Simplify provider schema constraints; retain local output validation.",
}


def safe_http_detail(error):
    """Translate a bounded provider error into fixed diagnostics only."""
    try:
        raw = error.read(16_385)
        if len(raw) > 16_384:
            return "Google error details exceeded the diagnostic size limit."
        details = json.loads(raw)["error"]
        records = details.get("details", [])
        if not isinstance(records, list):
            raise ValueError
        for record in records:
            if not isinstance(record, dict):
                continue
            reason = record.get("reason")
            if isinstance(reason, str) and reason in HTTP_REASON_HINTS:
                return f"Google reason: {reason}. {HTTP_REASON_HINTS[reason]}"
        # Some Gemini failures provide only a message, without ErrorInfo.
        # Match known phrases, but never echo that message.
        message = details.get("message", "")
        if isinstance(message, str):
            for phrase, reason in (
                ("reported as leaked", "KEY_REPORTED_LEAKED"),
                ("api key not valid", "API_KEY_INVALID"),
                ("api key expired", "API_KEY_EXPIRED"),
                ("has not been used in project", "SERVICE_DISABLED"),
                ("requests from referer", "API_KEY_HTTP_REFERRER_BLOCKED"),
                ("too many states", "SCHEMA_TOO_COMPLEX"),
                ("too complex", "SCHEMA_TOO_COMPLEX"),
                ("too many constraints", "SCHEMA_TOO_COMPLEX"),
            ):
                if phrase in message.lower():
                    return f"Google reason: {reason}. {HTTP_REASON_HINTS[reason]}"
        status = details.get("status")
        if status in ("PERMISSION_DENIED", "UNAUTHENTICATED", "INVALID_ARGUMENT",
                      "NOT_FOUND", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "INTERNAL"):
            return f"Google status: {status}; no recognized specific reason."
    except (ValueError, KeyError, TypeError, AttributeError, OSError,
            HTTPException, RecursionError):
        pass
    finally:
        error.close()
    return "No recognized Google error detail; raw response was not logged."


def validate_reply(raw):
    """Require a complete response with exactly the requested public text."""
    try:
        data = json.loads(raw)
        candidates = data["candidates"]
        if not isinstance(candidates, list) or len(candidates) != 1:
            raise ValueError
        candidate = candidates[0]
        if candidate["finishReason"] != "STOP":
            raise ValueError
        parts = candidate["content"]["parts"]
        if not isinstance(parts, list):
            raise ValueError
        text = ""
        for part in parts:
            if not isinstance(part, dict):
                raise ValueError
            if part.get("thought"):
                continue
            text += part.get("text", "")
        if text.strip() != EXPECTED_REPLY:
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise GeminiConnectionError(
            "Invalid, blocked, incomplete, or unexpected Gemini response; "
            "raw output was not logged."
        ) from None


def check_connection():
    """Read the secret from the environment and make one bounded API call."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise GeminiConnectionError(
            "Missing GEMINI_API_KEY. Add it under repository Actions secrets."
        )
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{
                "text": f"Reply with exactly {EXPECTED_REPLY} and nothing else."
            }],
        }],
        "generationConfig": {
            "maxOutputTokens": 1024,
            "thinkingConfig": {"thinkingLevel": "LOW"},
        },
    }
    request = Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        # No retry loop: one manual run makes at most one generation request.
        with urlopen(request, timeout=45) as response:
            if response.status != 200:
                raise GeminiConnectionError("Unexpected HTTP response status.")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        code = exc.code
        detail = safe_http_detail(exc)
        hints = {
            400: "Check API key validity and model request configuration.",
            401: "Check API key validity.",
            403: "Check project permissions, key restrictions, and eligibility.",
            404: "Check model availability for this project.",
            429: "Quota or rate limit reached. Check AI Studio limits; do not enable billing automatically.",
        }
        hint = hints.get(code, "Check Gemini service availability and try later.")
        raise GeminiConnectionError(f"Gemini HTTP {code}. {hint} {detail}") from None
    except (URLError, OSError, HTTPException):
        raise GeminiConnectionError(
            "Network, TLS, or timeout error contacting Gemini. Try later."
        ) from None
    except ValueError:
        raise GeminiConnectionError(
            "Invalid API key format or HTTP request configuration."
        ) from None

    if len(raw) > MAX_RESPONSE_BYTES:
        raise GeminiConnectionError("Gemini response exceeded the size limit.")
    validate_reply(raw)


def main():
    print(f"Daily News — Gemini connection test ({MODEL})")
    try:
        check_connection()
    except GeminiConnectionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    # Print our fixed success marker, never arbitrary model output.
    print(f"PASS: Gemini returned {EXPECTED_REPLY}.")
    print("Connection only; news ranking and verification are not implemented.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
