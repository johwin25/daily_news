# Snapshot helper

Unmodified browser distribution of **html-to-image 1.11.13** by Carlo Frinolli,
licensed under MIT (see `html-to-image.LICENSE`). No external CDN requests.

Source: https://github.com/bubkoo/html-to-image/tree/v1.11.13
Distribution: https://registry.npmjs.org/html-to-image/-/html-to-image-1.11.13.tgz
Retrieved using `npm pack html-to-image@1.11.13`; extracted `package/dist/` files
and `package/LICENSE`. The source map is included for browser debugging.

SHA-256 of `html-to-image.js`:
`a90b42909d80964269ef6d5f3d1e4a5a7e2a4c263a5d2a76a9e7151901343262`

Why this dependency: browsers cannot upload a live HTML subtree directly as a
WebGL texture. This small helper snapshots the existing article DOM, including
local illustrations and typography, without adding a frontend framework or
rewriting the article layout in Canvas. It runs before the gesture. Failed or
unavailable snapshots select the curved DOM fallback; the reader remains usable.
