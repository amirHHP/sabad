## 2026-10-01T13:07:40Z
You are explorer_survey_live_apis, a teamwork_preview_explorer for the Sabad project.
Your working directory is: /Users/sotoon/personal/Sabad/.agents/teamwork/explorer_survey_live_apis
Your parent orchestrator is: 5f3ddd0b-8fff-4532-82d8-412561e17041

MANDATORY: You MUST read the authoritative user requirements at:
/Users/sotoon/personal/Sabad/.agents/teamwork/ORIGINAL_REQUEST.md
before starting any investigation!

Also review prior investigation scripts in:
/Users/sotoon/personal/Sabad/.agents/teamwork/explorer_survey_1/probe_snappmarket.py
/Users/sotoon/personal/Sabad/.agents/teamwork/explorer_survey_1/scan_snapp_js.py

Your objective:
1. Probe live Iranian quick-commerce endpoints for SnappMarket (snapp.market), Digikala Jet (jet.digikala.com), and Okala (okala.com) using Python (urllib or requests/httpx or curl).
   - Test endpoints with central Tehran coordinates (e.g., lat: 35.715298, lng: 51.404343).
   - Test search, flash deals / promotions, vendors / stores in area, shipping rules, and inspect cart & auth/OTP endpoints.
   - Note exact base URLs, path formats, query params, headers (User-Agent, Origin, Referer, Accept, mobile vs web headers), and payload structures.
2. Formulate concrete API client architecture for each store:
   - SnappMarketClient
   - DigikalaJetClient
   - OkalaClient
3. Session persistence design:
   - Secure storage in `.sessions/<store>.json`
   - Token lifecycle, refresh, and reuse across restarts.
4. Error handling & resilience:
   - HTTP 429 rate limiting (exponential backoff with jitter)
   - HTTP 401 session expiration handling
   - Out-of-stock items detection
   - STRICT CONSTRAINT: Zero mock fallbacks or dummy data in production paths.
5. Define Pydantic schema contracts for:
   - `StoreProduct` / `CatalogItem`
   - `FlashDealItem`
   - `StoreShippingTier`
   - `CartItemMutation`
   - `StoreSession`

Document your full findings, verified endpoint curls/responses, schemas, and architecture in:
/Users/sotoon/personal/Sabad/.agents/teamwork/explorer_survey_live_apis/handoff.md
Update progress.md as you work. When complete, send a completion message to your parent orchestrator.
