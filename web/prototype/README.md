# Daily News 2.0 prototype

An isolated, mobile-first sample edition on `feat/daily-news-v2-prototype`.
Four explicitly fictional stories and four local archival photographs. No live
news, credentials, notification permission requests, service-worker registration,
production JSON reads, or deployment steps.

## Preview

From the repository root:

```sh
python -m http.server 8000 --bind 127.0.0.1 --directory web
```

Open the server's `/prototype/` path in a local browser. Serve **web**, rather
than only the prototype folder, so the existing `../icon.svg` favicon resolves.
Use a fresh browser profile/origin: an existing production service worker on the
same origin can control subpaths even though this prototype registers none.
There is intentionally no link from the production reader to this prototype.

For an iPhone on the same trusted LAN, bind the server to `0.0.0.0` and navigate
to the development machine's LAN IP, port 8000, path `/prototype/`. This temporary
server is for local development. The cloud onboarding UI offers no public preview.

## Files and architecture

- `index.html`: standalone shell, accessible reader region and previous/next controls.
- `style.css`: full dynamic viewport, safe-area padding, warm editorial overlay,
  portrait/landscape layouts, bounded scrollable summary, focus and reduced-motion styles.
- `app.js`: local sample fixtures and DOM rendering; one visible/inert-aware story;
  per-story expansion state; pointer direction locking and a single active turn.
- `assets/`: four local illustrative photographs; attribution and license provenance
  in `assets/CREDITS.md`. Existing icons are referenced, never copied or modified.
- `tests/reader.cjs`, `package.json`, `package-lock.json`: pinned Playwright interaction
  tests. Browser-test dependencies only; the interface needs no build or npm runtime.
- `.gitignore`: local browser dependencies and generated outputs.

### Page-turn approximation

A temporary, inert copy of the turning page rotates around its left edge in a
1,400px perspective scene. A paper reverse, curved gradient edge, slight torsion,
and progress-dependent shadow suggest a folded newspaper leaf. Forward turns
peel away; backward turns lay the preceding leaf back down. Only transforms and
shadow opacity change during the animation. This is a rigid CSS plane with a
stylized curled edge, **not a physically deforming sheet or WebGL mesh**.
Reduced motion switches stories immediately.

Horizontal intent locks after a 12px movement and a 1.3:1 direction ratio.
Vertical intent remains native scrolling (`touch-action: pan-y`). Turns commit
past 18% of the reader width; shorter or cancelled drags settle back. Pointer
capture is established before the source card is hidden. Input during settling
is ignored rather than queued, so repeated swipes cannot skip multiple stories.
Resize and preference changes safely resolve the in-progress animation.

## Tests

Python 3.12; standard library only for the existing suite:

```sh
python -m unittest discover -v
```

Browser tests (Node.js and Python available):

```sh
cd web/prototype
npm ci --ignore-scripts
npx playwright install chromium  # only if a browser is not already installed
npm test
# Optional system browser override:
CHROMIUM_PATH=/usr/bin/chromium npm test
```

The test starts and stops its own local server on port 8765. `ARTIFACTS` overrides
the screenshot directory, which defaults to `/tmp/daily-news-v2-screenshots`.
No production workflows, notifications or external services are invoked.

Coverage includes 375×667, 390×844, 430×932 and 844×390; expansion/collapse and
scroll bounds; previous/next boundaries; short and cancelled drags; vertical
intent; rapid keyboard and pointer input; keyboard focus and activation;
reduced motion; image failures; orientation resize while expanded; no horizontal
overflow; visible controls; no console/page errors or external data requests.

Tests distinguish two methods:

1. Synthetic `PointerEvent` dispatch, with capture stubbed only because dispatched
   events have no browser-active pointer, checks deterministic cancellation and
   rapid-input state transitions.
2. Chromium CDP touch input with `isMobile` and `hasTouch` exercises browser-routed
   touch swipes, native vertical summary scrolling and touch cancellation.

Neither is actual iPhone hardware, Safari/WebKit, VoiceOver, or a frame-rate benchmark.
Screenshots cover each viewport collapsed/expanded, a mid-turn frame and image failure.

## iPhone Safari acceptance checklist (manual, still outstanding)

- Open on an actual iPhone in Safari; verify sample/illustration labels and credits.
- Check the notch, home indicator and Safari toolbar with the toolbar expanded and
  collapsed; controls must remain reachable as dynamic viewport height changes.
- Swipe both ways slowly, release short drags, reverse direction, cancel with a
  second gesture, and swipe repeatedly during settling; check all boundaries.
- Expand each story; scroll to its final paragraph and back; collapse without a
  page change. Verify VoiceOver rotor/focus and external-keyboard arrows/Tab/Enter.
- Rotate while collapsed, expanded, and mid-turn; check for clipping or stuck pages.
- Enable iOS Reduce Motion; verify immediate changes without a rotating leaf.
- Test offline/image failures and large text settings. Confirm no permission prompts.
- Watch page edges/shadows on-device for flicker, seams and dropped frames.

## Production preservation

Only `web/prototype/` is added. The production reader, `briefing.json`, all original
logo/icon assets, manifest, service worker, Python pipeline/tests, push files and
workflows remain unchanged. Existing main-branch `web/**` deployment rules are
untouched: **merging this branch would make the prototype deployable with web/**.
Merge, deployment, workflow dispatch and notification delivery require separate,
explicit approval. Nothing is pushed, merged, deployed or sent by this work.
