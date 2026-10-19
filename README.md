# daily_news

Personal daily top-three global news briefing project.

## Current implementation

- Google News RSS collection for World, Economy, Technology, and Science.
- Ten-publisher domain allowlist and offline parser tests.
- Stage 3A: a manually triggered Gemini connection check.
- News ranking, independent-source corroboration, daily scheduling, and iPhone delivery are still to be built.

## Requirements and secret

Python 3.12; standard library only. No third-party packages are needed.

Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey).
In this repository, go to Settings -> Secrets and variables -> Actions -> Secrets,
then add a repository secret named `GEMINI_API_KEY`. Never put its value in code,
commits, screenshots, or logs.

The connection check uses `gemini-3.8-flash`. Google's
[pricing page](https://ai.google.dev/gemini-api/docs/pricing) lists free-tier text
input/output as of October 19, 2026; project eligibility and quotas must be checked
in AI Studio. Keep billing disabled for this free prototype. The script never
enables billing or switches models automatically.

## Run the tests

Offline tests need neither a key nor network access:

```sh
python -m unittest -v test_news_fetcher.py test_news_analyzer.py
```

For the live check, use Actions -> Test Daily News -> Run workflow.
Select the branch containing this change (currently `fix/bbc-allowlist-test`;
use `main` after merging), then click Run workflow.

Open the new run and choose the **Test Gemini connection** job. Its expected log is:

```text
PASS: Gemini returned DAILY_NEWS_OK.
```

This is a separate job from RSS collection, so feed failures do not hide the Gemini
result. Each manual run makes one generation request, with a 45-second timeout,
a 1,024-token output cap (including thinking), low thinking, and no automatic
retries or search tools. The request sends only a fixed connection-test prompt.
The job receives the secret as an environment variable; the key is sent in an
HTTPS header, not the URL. Raw provider responses and exception details are not
printed. Recognized Google error reasons are translated into fixed diagnostics;
provider messages, project IDs, and metadata remain hidden. Saving a secret alone does not prove that the key works; only a live
successful run establishes connectivity.

## Troubleshooting

| Result | Next check |
| --- | --- |
| Missing GEMINI_API_KEY | Use a repository Actions secret with that exact name. |
| HTTP 400 | Check key validity and the model request configuration. |
| HTTP 401/403 | Read the new Google reason/status line; check the specific permission or restriction it identifies. |
| HTTP 404 | Check whether this model is available to your project. |
| HTTP 429 | Check AI Studio quota and wait for reset; do not enable paid billing automatically. |
| HTTP 5xx or network/timeout error | Check service availability and retry manually later. |
| Invalid, blocked, incomplete, or unexpected response | The reply failed validation; this is not a successful connection check. |

Even a successful connection test does not establish news accuracy. The RSS
allowlist is publisher filtering, not independent fact verification.

## Diagnosing a refused Gemini request

The October 19 live run confirmed successful RSS collection (4/4 feeds, 48 approved
unique articles) and all 12 then-existing offline tests. The Gemini job received
a nonempty secret but returned HTTP 403. The original logger discarded the
provider's error body, so that run does not identify the specific cause.

The improved logger reads a bounded error body and prints only recognized, fixed
diagnostics such as SERVICE_DISABLED, API_KEY_SERVICE_BLOCKED, or
API_KEY_HTTP_REFERRER_BLOCKED. Unknown details are not echoed. A generic 403 does
not establish which setting is wrong and does not prove the supplied key is valid.

To use the updated diagnostics, start a **new** manual run on
`fix/bbc-allowlist-test`. Re-running jobs in the old run uses its original commit
and will not use the new logging code. Share the new run URL for diagnosis.
