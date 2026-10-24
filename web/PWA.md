# iPhone PWA foundation

After PR merge and successful deployment, open the GitHub Pages URL in **Safari** on iPhone, tap **Share → Add to Home Screen**, then open Daily News from its icon. The installed standalone mode is necessary for iOS web push.

This stage adds a manifest, icon and service worker. It does **not** request notification permission, create a PushSubscription, retain subscriber endpoints, or send notifications. A secure push sender (with VAPID credentials, protected storage and opt-in controls) is required. Never place private VAPID keys, Gemini keys or subscriber endpoints in the published `web/` folder.

The service worker caches only the reader shell for offline fallback; `briefing.json` always uses the network and can display an unavailable message when offline. Avoid showing stale research as the latest edition.

Deployment and iPhone install must be tested separately; support depends on installed-app browser/OS versions.
