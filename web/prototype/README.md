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
  per-story expansion state and a narrow navigation interface.
- `curl-navigation.js`: pointer state machine, velocity/distance decisions, capture,
  cancellation, bounds, keyboard alternatives and settling.
- `curl-geometry.js`: pure material clipping, cylindrical deformation and perspective
  compensation for the gripped point.
- `curl-renderer.js`: WebGL surface, cached article snapshots, front/back lighting
  and projected shadow. `curl-dom-renderer.js`: curved native-DOM fallback.
- `vendor/`: unmodified html-to-image 1.11.13 browser bundle and MIT license;
  only used to snapshot the existing article before a turn, not to render the UI.
- `assets/`: four local illustrative photographs; attribution and license provenance
  in `assets/CREDITS.md`. Existing icons are referenced, never copied or modified.
- `tests/reader.cjs`, `tests/curl.cjs`, `tests/geometry.mjs`, `package.json`, `package-lock.json`: pinned Playwright interaction
  tests. Browser-test dependencies only; the interface needs no build or npm runtime.
- `.gitignore`: local browser dependencies and generated outputs.

### Curved sheet geometry and rendering

This replaces the original rigid CSS flip. The sheet deforms continuously around
an angled cylinder. The line from the gripped edge to the pointer determines
its orientation; pointer distance determines radius (capped at 54 CSS pixels).
Moving Y at the same X changes the actual fold axis, not just its shadow.

In material coordinates, distance `s` from the crease maps to
`u = R sin(s/R)`, `z = R (1 - cos(s/R))` through the bend, then to a reversed
flat sheet beyond half a circumference. A perspective-corrected crease keeps
the gripped point under the screen-space pointer. The GPU surface uses 64 curved
bands with shared boundary positions, blank warm paper on its reverse, continuous
normal-based lighting and a blurred projected contact shadow. Article text on
the reverse is deliberately omitted rather than mirrored.

The article is captured once outside the interaction loop using the 20.6 KB
MIT-licensed html-to-image bundle. It preserves the existing DOM layout and local
photograph in a texture. Capture is prewarmed after image decoding and refreshed
when the page, viewport or expansion state changes. Texture/snapshot resolution
is capped at 1.5× pixel density. The settled page remains native accessible
HTML; rasterization is only used during the temporary gesture. No data fetching
or live-news integration is added.

Without WebGL, while a snapshot is unavailable, on snapshot failure, or after a
graphics-context loss, a 32-band native-DOM curved mesh provides the same geometry.
That fallback is more expensive and may be less smooth. Reduced motion changes
the story immediately with no curl. This is a cylindrical thin-sheet approximation,
not a conical/cloth simulation or a claim of exact reproduction of the reference.
The supplied screenshot and Markdown were used; the YouTube video was not viewed.

Input states are `idle → tracking → dragging → settling-complete/cancel → idle`.
A 12px threshold distinguishes intent; summary regions and controls protect their
normal interactions. The transparent triangular bottom-corner grips reserve
steep diagonal touch drags (`touch-action: none`) without covering the text.
Elsewhere native vertical scrolling remains available. Release uses progress
(28% width), recent velocity, a minimum 56px flick distance and reversal detection.
New gestures during settling are ignored. Escape, pointer cancellation, lost
capture, resize and visibility changes release resources and restore a stable
page. Adjustable constants are in `curl-geometry.js`.

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

The browser tests start and stop local servers on ports 8765 and 8766. `ARTIFACTS` overrides
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
   touch swipes, native vertical summary scrolling and touch cancellation. Dedicated curl tests
   also exercise held desktop mouse drags, fixed-X/varying-Y geometry, reversal,
   velocity-sensitive release, orientation interruption, WebGL unavailability and
   context loss. Pure geometry tests check gripped-point projection and clipping.

Neither substitutes for actual iPhone hardware, Safari/WebKit or VoiceOver testing.
Screenshots cover each viewport collapsed/expanded, mid-turn frames at two Y positions, forward/backward and touch curls,
image failure and the no-WebGL fallback. Frame intervals are recorded separately
in `curl-frame-timing.json`; they measure this headless environment, not iPhone FPS.

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
