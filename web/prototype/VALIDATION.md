# Validation — 2026-10-27

Baseline: latest fetched `origin/main`, `e6ff0f9b76d189325dedf3bdc55c394919030e05`.
No AGENTS.md files were present under /workspace. README, existing Python tests,
reader/PWA assets, and deployment/push workflows were inspected before changes.

## Executed checks

From `/workspace/daily_news`:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -v
```

**76 tests passed.** Output captured in `/tmp/daily-news-v2-python-tests.log`.
Messages beginning `FAIL:` inside negative-path tests are expected diagnostics;
the unittest runner reports `OK` with no failures or skips.

From `/workspace/daily_news/web/prototype`:

```sh
npm ci --ignore-scripts --cache /tmp/daily-news-npm-cache
CHROMIUM_PATH=/usr/bin/chromium npm test
```

**143 assertions passed**, across 375×667, 390×844, 430×932 and 844×390.
Playwright 1.58.2 with system Chromium 154.0.8037.57 on Debian 13.
Synthetic pointer tests and Chromium CDP browser touch emulation were both run.
Native browser touch scrolling, bidirectional paging and touch cancellation passed.
No unexpected console/page errors or external network requests in normal scenarios.
Image-request failures were deliberately injected in the fallback scenario.

Additional browser geometry checks verified that the headline, caption, read
control and credit fit for all four stories at 375×667 and 844×390; eight story
screenshots were captured. Screenshots were visually inspected for portrait,
landscape, expanded summaries, the mid-turn fold/shadow and image failure.

Artifacts: `/tmp/daily-news-v2-screenshots/` (generated, outside Git).

## Preservation

```sh
git diff --exit-code origin/main -- . ':!web/prototype'
sha256sum web/app-icon.png web/icon.svg
```

No existing tracked files differ from the baseline. Original asset hashes:

- `app-icon.png`: `e05a7a7518945afc044f6bd2de697a0d4ab2cb15f21da83103371e898db6818f`
- `icon.svg`: `72996744ce8dd7da0aa7d17130db6cdc4d15a0f87bcc8a476f5587aeb5bd7dd5`

## Limitations

The Playwright-managed Chromium download was blocked by a network-policy 403
from `cdn.playwright.dev`. The installed system Chromium provided a working
browser test path. External photo hosting was also blocked; licensed photos
were instead downloaded from the allowed upstream GitHub repository and served
locally. No TLS or artifact verification was disabled.

No physical iPhone, Safari/WebKit, VoiceOver or GPU frame-time measurements
were available. iPhone safe areas and dynamic Safari toolbar behavior still need
the manual checklist in README.md. Browser emulation does not prove those work
on hardware. The curl is a stylized CSS approximation, not a deformable mesh.

No merge, remote push, deployment, workflow dispatch, production secret use,
notification permission request or notification delivery was performed.
