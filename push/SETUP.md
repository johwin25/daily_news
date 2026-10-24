# Real iPhone Web Push — setup and test

This PR adds a Web Push **implementation**, not a configured live service.

## Prerequisites
- iPhone iOS 16.4+ with the Daily News web app added to Home Screen and opened from its icon.
- A Cloudflare account to host the free-tier Worker and KV namespace (subject to service limits).
- An HTTPS Worker endpoint. Do not place subscriber endpoints, VAPID private keys, or tokens in published website files.

## Configure server
1. Create Cloudflare KV namespace and bind it to a Worker as `SUBSCRIPTIONS`.
2. Deploy `push/worker.js` as the Worker source.
3. Generate VAPID keypair using `npx web-push generate-vapid-keys` locally. Do not commit the private key.
4. Set Cloudflare Worker environment **variable** `VAPID_PUBLIC_KEY` to the public key and **secret** `ADMIN_TOKEN` to a long random string.
5. Add GitHub Actions **secrets** `PUSH_WORKER_URL` (Worker base HTTPS URL), `PUSH_ADMIN_TOKEN`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` (for example a legitimate `mailto:` contact). Never paste secrets into chat.
6. Set **only** the public Worker URL in `web/push-config.js`, then merge/deploy.
7. Open the installed Home Screen app; tap **Enable notifications** and grant system permission.
8. Trigger **Publish Daily News Website** on main. After the Pages deployment succeeds, the sender looks up registered endpoints and sends a Web Push alert saying *research briefing*, not *verified news*.

## Testing and limits
- The PR itself runs offline tests but does not deploy any infrastructure.
- Delivery depends on iOS permission, networking, Worker/KV and push-provider availability. A successful push service response is not proof of display on the device.
- The Cloudflare Worker permits subscriptions only from the configured GitHub Pages origin, restricts push endpoints to standard provider hosts and requires an admin token to enumerate registrations. Origin checking alone does not stop scripted abuse; add rate limiting before any multi-user launch.
- The server retains registrations for up to 90 days (renewal/re-registration is necessary).
- Sender currently handles up to 1,000 registrations; it refuses an incomplete page. Intended for one personal device.
- Notifications only send after a successful fresh deployment. Failure of the push step does not retract the already published edition.
- Current stories are explicitly unverified research leads, not independently confirmed articles.
- The installed PWA notification button supports opt-in and opt-out. System-level notification settings remain under the user's control.
