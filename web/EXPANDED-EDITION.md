# Daily News expanded edition

The app displays **up to three** expanded research leads (summary, why it matters, sources), followed by **up to seven** compact additional headlines sourced directly from collected publisher RSS metadata. Additional headlines are **unverified**, not independently checked or rewritten. Both sections may contain fewer items when source coverage is incomplete. Avoid invented filler.

The top three attempt a client-side Wikimedia Commons image lookup using meaningful headline words. A related JPEG is displayed **only if two or more headline terms match its Wikimedia filename**. The UI explicitly identifies the image as illustrative, with a Wikimedia Commons source link. Filename similarity is not semantic validation; photo accuracy, attribution, licensing and relevance need editorial review before relying on this in production. If lookup fails or matching is weak, no photograph appears. This design avoids claiming an illustrative image documents the news event.

No raw publisher article text or Gemini secrets are added to the public JSON. The existing conservative verification gate is retained.
