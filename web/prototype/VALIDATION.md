# Curved-paper validation — 2026-10-27

Baseline: fetched `origin/main`, `e6ff0f9b76d189325dedf3bdc55c394919030e05`.
Work remains on `feat/daily-news-v2-prototype`. The previous implementation at
`1597c0d` used a rigid flip; this revision replaces it with cylindrical deformation.
The supplied Markdown specification and screenshot were used as references;
the YouTube video was not viewed.

## Commands and results

From `/workspace/daily_news`:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -v
```

**76 Python tests passed**, no failures or skips. Latest log:
`/tmp/daily-news-v2-curl-python.log`. Expected negative-path diagnostics in the
suite do not indicate runner failures; its final result is `OK`.

From `/workspace/daily_news/web/prototype`:

```sh
CHROMIUM_PATH=/usr/bin/chromium npm test
```

This runs, in order:

- `node tests/geometry.mjs`: **11,620 checks passed**, covering both directions,
  finite transforms, clipping, varying Y and perspective-correct grip projection.
- `node tests/reader.cjs`: **143 browser assertions passed** across 375×667,
  390×844, 430×932 and 844×390. Expansion, bounded scrolling, both paging directions,
  boundaries, short/cancelled/rapid input, keyboard focus, reduced motion,
  orientation, image failures, local-only requests and normal console errors.
- `node tests/curl.cjs`: **27 browser assertions passed**. Held mouse dragging,
  same-X/different-Y folds, intermediate exposure, reversal, slow release versus
  quick flick at equal distance, Escape, orientation interruption, summary protection,
  native-browser touch diagonal from the corner, cancellation, missing WebGL and
  simulated graphics-context loss.

Tooling: Playwright 1.58.2 and system Chromium 154.0.8037.57 on Debian 13.
Tests explicitly distinguish synthetic PointerEvents (capture stubbed for those
synthetic events), browser-routed CDP touch input, and held desktop mouse input.
No actual iPhone, Safari/WebKit or VoiceOver test was performed.
A separate browser probe also confirmed that the DOM fallback preserves the
scroll position of an already-expanded summary during a held page drag.

## Visual and performance evidence

Generated artifacts live outside Git in `/tmp/daily-news-v2-screenshots/`:

- Portrait/landscape collapsed and expanded reader captures.
- `curl-mouse-shallow.png`, `curl-mouse-diagonal.png`: same X, different Y.
- `curl-backward.png`, `curl-touch-diagonal.png`: reverse and emulated-touch folds.
- `curl-fallback.png`: actual curved DOM fallback with WebGL disabled.
- `image-failure.png`: article remains readable without the illustration.
- `curl-frame-timing.json`: measured requestAnimationFrame intervals while dragging.

Captured intermediate frames were visually inspected for actual bending,
visible paper reverse, shadow movement, page exposure and content clipping.
The WebGL mesh uses continuous boundaries and lighting; the native-DOM fallback
can have subtle facet seams and lower performance.

An early DOM-only implementation measured approximately 183 ms median frame
intervals in this headless environment. This prompted the WebGL path. A captured
WebGL run measured approximately 16.7 ms median and 16.8 ms p95 intervals
(sample counts and exact values are written by each run). These are browser
frame intervals, not GPU timestamps, input-latency measurements, thermal testing,
or an iPhone FPS guarantee. Physical-device performance remains unverified.

## Preservation and limitations

```sh
git diff --exit-code origin/main -- . ':!web/prototype'
git diff --exit-code 1597c0d -- web/prototype/assets
sha256sum web/app-icon.png web/icon.svg
```

All changes are inside `web/prototype/`. Existing production reader, briefing,
Python pipeline/tests, push system, workflows, schedule, manifest and service
worker are unchanged. All prototype photographs also remain unchanged.
Original production asset hashes:

- `app-icon.png`: `e05a7a7518945afc044f6bd2de697a0d4ab2cb15f21da83103371e898db6818f`
- `icon.svg`: `72996744ce8dd7da0aa7d17130db6cdc4d15a0f87bcc8a476f5587aeb5bd7dd5`

No merge, deployment, workflow dispatch, production secret use, notification
permission request or notification delivery was performed. Only the feature
branch is pushed to GitHub; that does not publish an interactive website.

The curved sheet is a thin-cylinder approximation, not a cloth simulation or an
exact reproduction of the video. Snapshot preparation is asynchronous; an early
gesture or capture failure uses the curved DOM fallback. The fallback is more
expensive. Modern Safari snapshot/WebGL behavior, installed-PWA behavior,
safe-area hardware and dynamic toolbar resizing still require the manual
Safari checklist in README.md. The prototype registers no service worker.
