# daily_news

Personal daily top-three global news briefing project.

## Current implementation

- Google News RSS collection for World, Economy, Technology, and Science.
- Ten-publisher domain allowlist and offline parser tests.
- Stage 3A complete: a live-verified, manually triggered Gemini connection check.
- Stage 3B: normalized dated source records, two structured Gemini calls for
  event shortlisting and claim comparison, and targeted follow-up RSS searches.
- Dated JSON records and a readable review report saved as Actions artifacts.
- Strict evidence gate: headline-only evidence produces unverified draft leads,
  with zero confirmed stories. Full-text evidence, reporting independence,
  daily scheduling, and iPhone delivery remain to be built.

## Requirements and secret

Python 3.12; standard library only. No third-party packages are needed.

Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey).
In this repository, go to Settings -> Secrets and variables -> Actions -> Secrets,
then add a repository secret named `GEMINI_API_KEY`. Never put its value in code,
commits, screenshots, or logs.

The connection check uses `gemini-3.5-flash-lite`. Google's
[pricing page](https://ai.google.dev/gemini-api/docs/pricing) lists free-tier text
input/output as of October 19, 2026; project eligibility and quotas must be checked
in AI Studio. Keep billing disabled for this free prototype. The script never
enables billing or switches models automatically.

## Run the tests

Offline tests need neither a key nor network access:

```sh
python -m unittest discover -v
```

For the live check, use Actions -> Test Daily News -> Run workflow.
Select `main`, then click Run workflow.

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

## Alternate-model connectivity diagnostic

Repeated live requests to `gemini-3.8-flash` returned HTTP 503 / UNAVAILABLE,
including the retry at 14:27 UTC on October 19, 2026. The connection check now
targets `gemini-3.5-flash-lite`, whose text input/output is listed on the free tier
in Google's pricing documentation checked that day.

Only the model identifier changed in Python. The key, prompt, endpoint method,
low thinking setting, token cap, and output validation are unchanged. All 15
offline tests pass with this model identifier.

Live verification succeeded on October 19, 2026 at 14:30 UTC (23:30 Asia/Seoul):
[successful workflow run](https://github.com/johwin25/daily_news/actions/runs/39269560989),
code commit `16d3e3cf689450393fc5d40827a7e9b2bf5c0045`.

- Gemini job: `gemini-3.5-flash-lite` returned `DAILY_NEWS_OK`.
- All 15 offline tests passed.
- RSS job: 4/4 feeds, 47 approved unique articles.

This confirms that the current key and project can call Flash-Lite. The result
suggests the repeated 503 failures were specific to the other model's serving
path; it does not establish the exact root cause of those errors or the earlier
403. Structured headline analysis is now implemented on `feat/evidence-pipeline`;
independent-source corroboration remains incomplete.

## Run the research pipeline

The separate **Daily News Research** workflow runs offline tests before collecting
four topic feeds and making at most two calls to the working Flash-Lite model.
It runs on same-repository pull requests and by manual dispatch. Fork PRs run
only offline tests. It has read-only repository permissions and no schedule.

A manual local run (with the key already in the environment) is:

```sh
python news_pipeline.py
```

The workflow supplies `GEMINI_API_KEY` only to the pipeline step. It does not
print the key or save raw provider responses. Each model request is limited to
60 seconds, 100,000 input bytes, 200,000 response bytes and 8,192 output tokens,
with no retries, model switching, grounding tools, or billing changes. Quota
exhaustion stops the run; eligibility and billing settings remain account-side.

Collection accepts articles from the publisher allowlist with valid timestamps
within 48 hours (up to 15 minutes of clock skew). It caps candidates at 25 per
category and 100 overall, merges duplicate URLs across categories, and retains
source URLs and provenance under stable IDs. Gemini shortlists up to five
events. Each event receives one follow-up RSS search, retaining at most eight
fresh results. The second call compares discrete claims using source IDs and
exact excerpts from their headlines. Local checks reject invented IDs, invented
quotes, wrong-event citations, invalid JSON, and truncated responses.

Open the run's **Summary** to read the report. Download the
`daily-news-research-<run>-<attempt>` artifact for files under `output/YYYY-MM-DD/`
(UTC, retained for 14 days):

| File | Purpose |
| --- | --- |
| `candidates.json` | Normalized source registry, exclusions and feed failures |
| `shortlist.json` | Unverified model event grouping and editorial priorities |
| `evidence.json` | Follow-up source records, event mappings and search failures |
| `assessment.json` | Unverified model claim comparisons and headline excerpts |
| `briefing.json` | Evidence-gate decision and up to three draft review leads |
| `briefing.txt` | Readable report with collected links and retrieved headlines |
| `run_status.json` | Operational outcome or fixed failure diagnostic |
| `contracts.json` | Output contracts used for local model validation |

A successful run prints `PASS: research pipeline completed` and records
`completed_with_evidence_shortfall`. This means execution succeeded, while
`confirmed_count` remains zero and `items` is empty. Drafts appear only in
`review_queue`, with `insufficient_evidence` status. Editorial priority measures
importance, not probability of truth. An empty shortlist is valid; no stories
are invented to fill the requested three slots.

Different publishers may repeat the same wire report. Matching headlines are
flagged, but different wording does not establish independence. The retrieved
links may be Google News redirects, not resolved publisher article URLs.
Full-text retrieval and reporting provenance must be implemented before this
pipeline can produce confirmed stories. The report does not claim to have read
articles it has not retrieved.

Partial initial collection, no fresh candidates, provider failures, or invalid
model output fail the run and preserve diagnostic artifacts. Follow-up search
failures remain visible and cannot promote a draft into confirmed news. Reruns
replace the dated files and remove stale reports before starting.

Next acceptance checkpoint: inspect one live research run, its source mappings,
headline excerpts, grouping, priorities, summaries and exclusion reasons before
adding full-text corroboration, a daily schedule, or phone delivery.

Provider decoding schemas retain types, keys and enums but omit nested array
and text length limits to reduce decoder complexity. Full array and text bounds
remain enforced locally after each response.
