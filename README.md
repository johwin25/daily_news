# Daily News

A private daily global-news briefing for iPhone via Telegram. Python 3.12,
standard library only, hosted in GitHub Actions. The existing Gemini key and
`gemini-3.5-flash-lite` model are used without changing billing or models.

## Current behavior

Google News RSS supplies World, Economy, Technology and Science candidates from
the original ten-publisher allowlist. A bounded set of fresh BBC and Guardian
publisher-feed originals improves article access. Duplicate publisher/headline
records are merged, retaining original collection links. There are at most
100 candidates; publication dates must be within 48 hours.

Gemini groups up to five events. Targeted follow-up searches gather reporting.
Up to six BBC/Guardian originals are read, prioritizing cross-publisher pairs;
other publishers remain headline-only. Each article retains up to 5,000 text
characters, metadata, retrieval provenance, hashes and access diagnostics.
Guardian pages must explicitly declare free access in their structured metadata.
Blocked, missing, ambiguous and unsupported pages remain unavailable evidence.

The second Gemini call compares core claims with exact, scoped quotations.
Python rejects invented sources, wrong-event references, fabricated quotations,
and title excerpts labeled as article text. At most two Gemini generation calls
are made per research run, without automatic model retries or paid fallbacks.

## Corroboration policy

The publication gate checks every material claim. A claim needs two different
publishers' retrieved article-text quotations, each explicitly attributing
reporting to its own outlet (such as “told the BBC” or “told the Guardian”).
The article metadata must have named bylines and fresh page publication dates.
Shared authors, wire-service attribution, copied text, contradictory evidence,
missing reporting origin, mismatched source URLs or corrupted text hashes hold
the event. Distinct outlet names and bylines alone never establish independence.

Only checked claim text is used in the published summary; the free-form draft
summary cannot add facts. Significance is labeled as analysis. This is an
operational, conservative corroboration policy based on retrieved excerpts and
publisher self-attribution, not a guarantee of truth or a claim to have verified
an entire article. Extracted page metadata and model interpretation may be wrong.
Unknowns remain held rather than counted as independently supported stories.

The output contains the top three qualifying events, or fewer when insufficient
evidence is available. Unverified drafts remain in a separate review queue and
are never sent as confirmed news. A zero-story day sends an explicit shortfall.

## Your delivery schedule

- Monday–Friday: **18:00 Asia/Seoul** (`0 9 * * 1-5` UTC).
- Saturday–Sunday: **09:00 Asia/Seoul** (`0 0 * * 0,6` UTC).

GitHub Actions schedules can run late. The schedule is present but remains
inactive until the Actions variable `DAILY_NEWS_ENABLED` is exactly `true`.
Manual research runs default to preview only. Sending is allowed only from
`main`; pull requests cannot send Telegram messages or update delivery state.

## One-time Telegram setup

1. In Telegram, open the official **@BotFather**, use `/newbot`, and create your
   own bot. Save its token in this repository's Actions **Secrets** as
   `TELEGRAM_BOT_TOKEN`. Keep token values out of chat, commits and logs.
2. Open your new bot in Telegram and tap **Start**. Enable its iPhone notifications.
3. Open **Actions → Set Up Telegram → Run workflow** on `main`. The job shows
   your bot link and private-chat candidates without sending anything. Find
   your own chat and save its numeric ID as Actions secret `TELEGRAM_CHAT_ID`.
   The setup does not guess or select a recipient.
4. Open **Actions → Daily News Research → Run workflow**, choose `main`, and
   enable the **deliver** checkbox. Confirm that the message reaches your iPhone.
5. In **Settings → Secrets and variables → Actions → Variables**, create
   `DAILY_NEWS_ENABLED` with value `true`. This activates the requested schedule.

Existing `GEMINI_API_KEY` remains required. Actions' own `GITHUB_TOKEN` is supplied
automatically; no personal GitHub token is needed. The connected coding tools
cannot install Telegram or create your bot credentials, so those account steps
must be completed by you. Never paste the token into a conversation.

[Actions secrets](https://github.com/johwin25/daily_news/settings/secrets/actions)
· [Actions variables](https://github.com/johwin25/daily_news/settings/variables/actions)
· [Workflows](https://github.com/johwin25/daily_news/actions)

## Delivery integrity

Before sending, the briefing is rebuilt from its saved evidence and compared
with the output. Failed, stale or unverified items cannot be delivered. The bot
checks that the configured chat ID resolves to the exact private chat before
sending. The recipient is chosen by your configured secret, never inferred from
a name, email or the first bot message.

A private `news-delivery-state` branch stores per-day reservations and receipts,
without tokens, chat IDs or message bodies. The reservation is written before
sending. Same-day duplicates and uncertain outcomes are withheld. If Telegram
may have accepted a request before a timeout, the system will not automatically
resend it. This avoids duplicates but can require manual review after a network
failure. GitHub delivery-state write failures prevent the send. Research failure
alerts are fixed messages and have a separate once-per-day identity.

“Accepted by Telegram” confirms the API accepted the message, not that the
phone displayed it. Device receipt must be checked during setup. Sending uses
plain text and direct source links; model text is not treated as Telegram markup.

## Inspect and test

```sh
python -m unittest discover -v
python news_pipeline.py
python news_delivery.py                  # validate and write a preview; no send
```

The research workflow saves dated candidate records, shortlisted events, source
text, model assessments, evidence-gate decisions, the briefing and Telegram
preview under `output/`, retained for 14 days. Its run Summary shows the report.
The research artifact has one stable name per workflow run so a delivery-job
rerun can retrieve the original research result. Failed research reruns replace
stale outputs. Separate delivery artifacts retain status and preview for 7 days.

`--send` requires the Telegram secrets plus GitHub Actions ledger configuration;
it is normally invoked by the workflow after the explicit manual checkbox or
scheduled activation. The dedicated BBC integration workflow reads one current
article and validates model quotations separately from editorial ranking.

## Source references

- [Telegram Bot API](https://core.telegram.org/bots/api)
- [GitHub scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [Guardian RSS help](https://help.theguardian.com/article/how-do-i-use-the-guardian-s-rss-feeds)

## Prior validation

The BBC reader and article-to-Gemini path were live-verified before this stage:
[reader](https://github.com/johwin25/daily_news/actions/runs/39974676001),
[integration](https://github.com/johwin25/daily_news/actions/runs/40056472579).
Current corroboration and delivery changes require their own live workflow check.
