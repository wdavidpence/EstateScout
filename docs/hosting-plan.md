# Backend Hosting Plan (pre-launch decision)

The proof-phase proxy (server/server.py + ai_proxy.py) cannot ship:
it tunnels a personal Codex subscription over a LAN dev server.

## Required before store submission
1. Official API key (user already has one for Luna) — swap
   ai_proxy's Codex OAuth path for the standard chat/completions
   endpoint with the paid key. No auth subtrees in the app bundle.
2. A hosted proxy the phone actually talks to. Options, cheapest
   first:
   - Fly.io / Railway free-or-~$5 tier: run server/server.py nearly
     as-is (single Python process). Needs HTTPS (Caddy/traefik or
     their managed certs).
   - VPS (Hetzner CX22 ~€4/mo): same code + Caddy; full control.
   - Serverless (Workers/Lambda): needs rewrite (SSE + file bodies);
     skip — the proxy is stateful-ish and low-traffic.
3. Real subscription gating server-side (client flag is
   proof-only): verify StoreKit/Play receipts against Apple/Google
   and keep per-device scan counters server-side, or use RevenueCat
   (~free < $2.5k/mo revenue) so you don't implement billing APIs.
   Recommended: RevenueCat — one dependency, handles both stores,
   and the $5/mo entitlement check is one REST call from the proxy.
4. Rate limiting + budget guard MUST live server-side (keep the
   per-day counter; move it to per-API-key or per-device).
5. Privacy nutrition labels: AI analysis sends user photos to
   OpenAI — disclose; keep images in memory only, no retention.

## Test path for ads
AdMob: create account → create app (both platforms) → use test
ad-unit IDs during review; swap to live units before release.
Plugin @capacitor-community/admob@8.1.0 already synced into both
native projects (APK builds with the Ads SDK, 14 MB).
