# GitHub Pages publication

The `Publish Daily News Website` workflow tests changes on pull requests and, on its default-branch scheduled or manual runs, builds a fresh research edition and deploys **only** `web/` to GitHub Pages. The `output/` evidence directory and `GEMINI_API_KEY` are never included in the Pages artifact.

## Owner setup

1. Open repository **Settings → Pages** and set **Source: GitHub Actions**.
2. Review whether the repository is public, and audit its current files **and commit history** for secrets before changing visibility. GitHub Pages is publicly accessible; do not assume a private repository means a private website.
3. Ensure `GEMINI_API_KEY` is set under Actions secrets.
4. After the deployment pull request is tested and merged, use **Actions → Publish Daily News Website → Run workflow** on `main`.
5. Open the deployment job's `github-pages` environment URL, then confirm the page loads its newly generated `briefing.json`.

## Deliberate safeguards

- Only the website directory is deployed. Raw publisher article text, evidence excerpts, tokens and internal reports are not published.
- The export strips unverified model claims and keeps at most three labeled research leads with limited source metadata.
- The current verification gate reports **zero confirmed stories**. This is a research preview, not a verified news briefing. Do not send a push notification asserting a confirmed edition is ready.
- If tests, collection, AI generation or export fail, the workflow does **not** deploy a new edition. The previous site may remain visible; its dated label must be checked.
- GitHub scheduled Actions may be delayed or disabled by repository inactivity. Deployment requires Pages to be enabled and an eligible plan.
- iPhone installation, service workers and Web Push are future work; GitHub Pages alone cannot send push notifications.
