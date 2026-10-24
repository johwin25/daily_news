# Mobile news reader (initial prototype)

Open `index.html` through an HTTP server (for example `cd web && python -m http.server 8000`), then visit http://localhost:8000/.

The reader fetches `briefing.json` on every load. The checked-in JSON is deliberately empty, not invented news. To preview a real research run locally, copy its dated `output/YYYY-MM-DD/briefing.json` into `web/briefing.json` and refresh. **Do not commit research outputs as confirmed news** unless they have passed the editorial verification gate.

The reader supports the existing pipeline schema (`items` and `review_queue`). It labels unverified leads prominently, renders external publisher source links, and uses safe text rendering rather than injecting publisher/model HTML. The news scraper, automated deployment, daily schedule, and iPhone push notification subscription/server are **not** implemented here. This stage establishes the display contract.

Later deployment should publish only a sanitized, bounded public briefing rather than raw evidence files, and should only notify when a new edition has been successfully generated.
