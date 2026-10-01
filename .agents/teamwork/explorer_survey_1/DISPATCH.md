# Dispatch: Explorer Survey 1 (Live APIs & Networking)
Working directory: /Users/sotoon/personal/Sabad/.agents/teamwork/explorer_survey_1
Original request: /Users/sotoon/personal/Sabad/.agents/teamwork/ORIGINAL_REQUEST.md

## 2026-10-01T12:57:28Z
You are the Live APIs & Networking Explorer for the Sabad project.
Working directory: /Users/sotoon/personal/Sabad/.agents/teamwork/explorer_survey_1
Authoritative requirements: /Users/sotoon/personal/Sabad/.agents/teamwork/ORIGINAL_REQUEST.md

You MUST read /Users/sotoon/personal/Sabad/.agents/teamwork/ORIGINAL_REQUEST.md before doing anything else.
Note: You are a read-only exploration agent. Do not modify production code. Maintain progress.md with timestamped updates in your working directory.

Your mission:
1. Inspect the local Python environment (version, installed networking packages like httpx, requests, pydantic, curl_cffi, etc.).
2. Test live network connectivity to Iranian quick-commerce endpoints:
   - SnappMarket (snapp.market APIs, e.g. /api/v1/promotions/flash-deals, /api/v1/search/products, OTP endpoints /api/v1/auth/otp/send and verify, cart items POST /api/v1/cart/items, shipping rule tiers)
   - Digikala Jet (jet.digikala.com APIs, e.g. deals / شگفت‌انگیز جت, search with store ID, pricing, discounts, inventory, cart mutation POST /v1/cart/add/, cookies / SSO tokens)
   - Okala (okala.com APIs, e.g. special / timed discounts, catalog queries with package size & barcode, session token management, remote basket mutation)
   Use realistic Tehran coordinates (e.g. lat=35.715298, lng=51.404343 or central Tehran). Verify spoofed browser/mobile headers and real response formats.
3. Detail error handling strategies for HTTP 429 (rate limits), HTTP 401 (session expiry), and out-of-stock items. Note constraint: No mock data or fallback stubs in production paths!
4. Detail the session persistence design in `.sessions/` across application restarts.
5. Provide a complete platform adapter architecture and interface contract.
6. Write your comprehensive report to /Users/sotoon/personal/Sabad/.agents/teamwork/explorer_survey_1/handoff.md and notify the parent orchestrator when complete.
