# daily_news

Personal daily top-three global news briefing project.

## Current implementation

- Google News RSS collection for World, Economy, Technology, and Science.
- Ten-publisher domain allowlist and offline parser tests.
- Stage 3A complete: a live-verified, manually triggered Gemini connection check.
- Stage 3B: normalized dated source records, two structured Gemini calls for
  event shortlisting and claim comparison, and targeted follow-up RSS searches.
- Dated JSON records and a readable review report saved as Actions artifacts.
- BBC article reader: live-tested extraction of visible article text.
- BBC evidence integration resolves original links from publisher feeds, retains
  bounded text under stable source IDs, and validates scoped model quotations.
- Evidence remains unverified while completeness and reporting independence are
  unknown. Daily scheduling and iPhone delivery remain to be built.

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
exact excerpts from headlines or successfully retrieved BBC article text. Local checks reject invented IDs, invented
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

Live research validation completed on October 19, 2026:
[successful run](https://github.com/johwin25/daily_news/actions/runs/39272735943),
code commit `a15f2e3407465e0281c2c0ce06516741ecd44bf3`.
All 45 offline tests passed in Actions. The live pipeline collected 48 candidates,
shortlisted five events, completed five follow-up searches without failures,
and retained 52 source records. It produced three unverified draft leads and
zero confirmed stories. Both structured Gemini calls succeeded. Saved source
mappings and exact headline excerpts passed local revalidation; regenerating
the JSON briefing and text report from the artifact reproduced both exactly.
These checks establish pipeline execution and citation integrity, not factual
accuracy or reporting independence.

Next implementation stage: retrieve full-article or primary evidence and establish
reporting provenance before enabling confirmed stories, daily scheduling, or
phone delivery.

Provider decoding schemas retain types, keys and enums but omit nested array
and text length limits to reduce decoder complexity. Full array and text bounds
remain enforced locally after each response.

## Read one BBC article (Stage 3C, isolated first step)

The standalone BBC reader retrieves visible article text from direct HTTPS
`bbc.com/news/articles/...` or `bbc.co.uk/news/articles/...` links. It does not
resolve Google News links itself. The integrated pipeline described below uses
publisher feeds to resolve BBC originals and supplies their text to Gemini.
Confirmed stories remain zero while independence is unestablished.

```sh
python news_article_reader.py https://www.bbc.com/news/articles/cq0ld9g9e913o
```

The result is saved in `output/article-reader/latest.json`, including the page
title, extracted text blocks, requested/final URLs, retrieval time and word count.
It is always labelled `unverified`. Extraction does not establish completeness,
publication date, reporting independence, or factual accuracy. It uses only
visible BBC text-block components, without bypassing access restrictions.

On GitHub, open **Actions -> Test BBC Article Reader -> Run workflow** after the
workflow is on `main`. Expected success:

```text
PASS: BBC article text retrieved; ... words, ... text blocks. Claims remain unverified.
```

Download the `bbc-article-reader-...` artifact to inspect `latest.json` (retained
for three days). This workflow uses no API key and makes no Gemini calls. It
also tests same-repository pull requests; forks run the offline checks only.

The reader checks direct BBC article URLs and every redirect, uses a 25-second
request timeout, caps HTML at 2 MB and requires a title plus at least 100 extracted
words. Blocked/rate-limited pages, network errors, non-HTML responses and missing
article text return failure diagnostics with a nonzero exit code. A failed rerun
replaces an earlier result with an empty-text failure record. BBC layout changes
can break extraction; word counts can change as the article is updated.


## BBC article evidence in the research pipeline

The CLI now retrieves BBC text between follow-up searches and the second Gemini
call. It indexes five fixed BBC RSS feeds, matches exact normalized headlines
within the BBC publisher, and checks the retrieved page title again before
attaching text to the existing source ID. Ambiguous, missing, stale or denied
originals remain explicit unavailable evidence. Other publishers remain
headline-only; no model-generated URL or external redirect-decoding service is
used. Publisher feed tracking queries are removed only from validated direct
BBC article links.

The budget is six article reads per run and 5,000 retained characters per
article. Failed reads do not fail the entire draft pipeline. `evidence.json`
records feed availability, individual attempts, resolution basis, original and
retrieved URLs, text hashes, truncation and wire-service mentions. Extraction
completeness, article-page publication date and reporting independence remain
explicitly unestablished. The original feed publication-date filters still apply.

Each model citation must now include a `scope` of `headline` or `article_text`.
Python checks quotations against the corresponding retained text. Headline-only
records cannot be cited as article text. Only sources assigned to shortlisted
events are sent in the second call, keeping the input bounded. New tests cover
ambiguous originals, feed dates and hosts, changed article titles, retrieval
budgets, text truncation, unavailable pages, quote fabrication and source scope.

The report displays original article links and the exact cited excerpts.
Wire-service mentions and matching article text are warning signals; neither
absence of a wire mention nor distinct publishers proves independence. Confirmed
items remain empty until the remaining corroboration requirements are met.

BBC UK feed URLs retain their original link in `feed_article_url`; the integration
requests the international `www.bbc.com` edition at the same article path because
the standalone extractor targets that layout. Small page-title edits are allowed
only after that path is established, with conservative title similarity checks
that reject changed numeric tokens or negation. Missing matches are not guessed.

The **Test BBC Evidence Integration** workflow independently exercises one current
BBC article and one Gemini comparison request, ensuring the text path is tested
even when editorial ranking selects no BBC stories. It retains its evidence,
assessment and fixed status under `output/article-evidence-check/` for three days.
This is a functional test, not a ranked or independently verified news item.

Live validation on October 24, 2026, tested code commit
`1a7f8ff7445339c7aa02a3252edadea1c0ec0560`:

- All 69 offline tests passed locally and in Actions.
- [Focused integration run](https://github.com/johwin25/daily_news/actions/runs/40056472579)
  retrieved 1,915 characters from a current BBC article. Gemini returned two
  article-text citations, both validated against the retained text. Downloaded
  artifact review also checked the stored text hash.
- [Research run](https://github.com/johwin25/daily_news/actions/runs/40056472630)
  processed 47 candidates and produced three unverified draft leads. No BBC
  sources were assigned to that run's selected events, so it made zero article
  reads. All source citations were revalidated, and its JSON briefing and text
  report were reproduced exactly from saved evidence.
- Both workflows passed. Confirmed stories remain zero: article completeness,
  article-page publication dates and independent reporting are still unestablished.

These results establish the BBC text-to-model path and citation integrity. They
do not establish factual accuracy or independent corroboration. Article readers
for additional publishers and reporting-provenance checks are still required.

## Newspaper web edition export

`news_web_export.py` converts a successful research output into
`output/web/edition.json`. The research workflow exports it after a successful
pipeline run and includes it in the existing artifact. This export does not
publish to the web app or schedule updates.

The exporter retains at most three unverified leads, cited claim text, source
publishers/URLs/timestamps, evidence scope, limitations and the originating run.
It checks quote presence and event/source membership against `evidence.json`.
The preview uses explicitly cited claims rather than a broader model draft.
Failed outputs, unknown citations, unsupported status promotion and non-HTTPS
source links are rejected. Empty editions stay empty; claims are never expanded
into fabricated long articles.

The private [Daily Fold web app](https://daily-fold-jason.cozycake3.chatgpt.site)
loads a separately hosted `edition.json`. Its initial real-news edition was
imported from successful main run
[40058801656](https://github.com/johwin25/daily_news/actions/runs/40058801656),
generated October 24, 2026 at 03:33 UTC. It contains three unverified leads and
zero confirmed stories. The app displays generation date, source links and
headline-only labels. This is a saved snapshot: automatic backend publishing,
daily refresh scheduling and push notifications remain separate work.

Site source is maintained in its own Sites repository. Do not place GitHub or
Gemini credentials in the browser or make the private news repository public.
