# IBVAP Command Center — Frontend

Real Phase 6 implementation — connects to the live backend over REST + WebSocket. For the full API contract, known gaps, and design rationale, see `../FRONTEND_BLUEPRINT.md`. `CommandCenterReference.jsx` in this folder is the earlier mock-data reference build this was extended from; this app replaces every piece of mock state in it with real data.

## Setup

```bash
npm install
npm run dev
```

Defaults to `http://127.0.0.1:8000` for the backend. Override with a `.env` file (copy `.env.example`) if your backend runs elsewhere.

**The backend must be running** (`uvicorn backend.main:app --reload` from the project root) for this to show anything — there's a visible error banner if it can't be reached, rather than a silent blank screen.

## What's real vs. what's a placeholder

Everything in this app is wired to live data — no mock state left in `App.jsx` or the components. The one intentional exception: the selected-camera panel shows the **latest evidence snapshot**, not a live video feed, because no live overlay stream exists in the backend yet (labeled directly in the UI, and documented in the blueprint §5). That's an honest gap, not a bug.

## Verification

This wasn't just built and assumed to work — before being wired into React:

- `src/lib/reconnectingSocket.js` was unit-tested against the real running backend from Node (`ws` package standing in for the browser's `WebSocket`) — connected, received a live broadcast, survived the backend being killed and restarted (5 reconnect attempts with exponential backoff, then a clean recovery), and received a new broadcast after reconnecting. See the test transcript in the project's build history.
- `src/lib/api.js` was loaded through Vite's own SSR module transform (`scripts/test-api.mjs`) — not reimplemented or mocked — and exercised against a live backend with a real seeded incident: every REST function call, plus `patchIncidentStatus` actually changing a real database row and the change being confirmed by a follow-up read.
- `npm run build` produces a clean production bundle with zero warnings (an initial CSS `@import` ordering bug — Google Fonts import placed after Tailwind's — was caught by the build output and fixed, not left in).

What wasn't tested: actual in-browser rendering and click interactions — this sandbox has no browser available. The data layer (REST + WebSocket + reconnect behavior) is verified against the real backend; the last mile (does it look right, do the buttons feel right) still needs a real run in your browser.

## Scripts

- `npm run dev` — dev server with hot reload
- `npm run build` — production build to `dist/`
- `npm run preview` — serve the production build locally
