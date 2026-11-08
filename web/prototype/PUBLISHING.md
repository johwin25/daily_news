# Published phone reader

Public address: **https://johwin25.github.io/daily_news/prototype/**

This is the Daily News 2.0 **sample edition** with interactive page curl. It does
not claim to show live news. On iPhone, open the address in Safari, choose
**Share → Add to Home Screen**, then open the new icon. The manifest and Apple
metadata keep the shortcut on `/prototype/` and reuse the existing app icon.
No new notification permission is requested and no service worker is registered.

## Publishing without sending alerts

`Publish Daily News 2.0 Prototype` is a separate GitHub Actions workflow. It:

1. Checks out the selected prototype and the latest production `main` files.
2. Runs the offline and publication-safety tests.
3. Downloads the currently published public briefing; a missing or invalid edition
   aborts the release rather than replacing the live reader with empty sample data.
4. Assembles `main/web/` plus the isolated `/prototype/` route. The original live
   briefing bytes, production reader, icon, manifest and service worker are retained.
5. Publishes with the same concurrency group as the existing daily publisher.
6. Checks the deployed revision marker, rendered entry point, manifest, mechanism
   scripts, original icon and retained briefing over public HTTPS.

The publisher never calls the research pipeline or push sender and uses no
production secrets. The sample code is included in `main` so later normal daily
publishes retain the prototype route.

For this initial release, the promotion commit uses `[skip actions]` to suppress
the normal `web/**` deployment (which also sends alerts). A following change to
**only** `.github/workflows/prototype-pages.yml` triggers the static-only publisher.
The existing `.github/workflows/mobile-edition.yml` remains byte-for-byte unchanged.

For later releases, remember that normal `web/**` pushes on main still trigger the
original production workflow. Use the same skip-then-static-publish process if no
news regeneration or notification delivery is wanted. The separate workflow can
also be run manually in GitHub Actions after a skipped promotion.

The link requires an Internet connection. Physical iPhone Safari/installed-app
behavior must still be checked using the checklist in README.md.
