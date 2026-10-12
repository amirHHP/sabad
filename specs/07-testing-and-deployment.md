# Spec 07: Testing Strategy & Cloud Deployment

> **Status**: Approved & Verified  
> **Test Suite**: 198 pytest tests (100% pass rate)  
> **Deployment Target**: Streamlit Community Cloud (`share.streamlit.io`)

---

## 1. Automated Test Suite Architecture

Sabad enforces automated test-driven verification across 4 distinct testing tiers:

```
┌───────────────────────────────────────────────────────────┐
│ Tier 4: Real-World Shopping Scenarios (End-to-End)        │
│ tests/test_e2e_suite.py, tests/verify_live_endpoints.py    │
├───────────────────────────────────────────────────────────┤
│ Tier 3: Adversarial & Cross-Store Optimization Challenges │
│ tests/test_adversarial_challenge.py,                      │
│ tests/test_challenger_ui_stress.py                        │
├───────────────────────────────────────────────────────────┤
│ Tier 2: Boundary Value Analysis (BVA) & Edge Cases        │
│ tests/test_sku_matching.py, tests/test_pricing_*.py       │
├───────────────────────────────────────────────────────────┤
│ Tier 1: Unit & Component Isolation                        │
│ tests/test_normalizer.py, tests/test_adapters.py,         │
│ tests/test_matcher.py, tests/test_optimizer.py,           │
│ tests/test_dispatcher.py, tests/test_ui_app.py            │
└───────────────────────────────────────────────────────────┘
```

### Dedicated Test Suites
| Test File | Test Count | Focus Area |
|:---|:---:|:---|
| `tests/test_pricing_normalization.py` | 9 | Asserts SnappMarket, Digikala Jet, and Okala prices, delivery fees, and MOVs are strictly in Tomans without 10x discrepancies. |
| `tests/test_sku_matching.py` | 40 | Persian unit suffix parsing, 4L vs 1kg exclusion, flavor exclusions (melon milk), boundary lookaheads. |
| `tests/test_ui_app.py` | 11 | Headless AppTest execution, 4-tab calculation breakdown rendering, 9-column dataframe schema validation. |
| `tests/test_adversarial_challenge.py` | 84 | High-load stress tests, corrupted API payloads, malformed numerals, rapid reruns. |
| `tests/test_challenger_ui_stress.py` | 14 | UI stress tests under out-of-stock and zero-item basket conditions. |
| `tests/test_adapters.py` | 13 | Store adapter network contracts and headers. |
| `tests/test_normalizer.py` | 11 | Persian digit conversions, comma delimiters, and verbal quantities. |
| `tests/test_optimizer.py` | 2 | MILP mathematical optimization correctness. |
| `tests/test_e2e_suite.py` | 6 | End-to-end integration across all subsystems. |
| `tests/test_dispatcher.py` | 1 | Authenticated remote cart population. |
| `tests/test_harvester.py` | 1 | Concurrent catalog harvesting. |
| `tests/test_matcher.py` | 6 | RapidFuzz token matching score verification. |

### Execution Command
```bash
./.venv/bin/pytest -v
# Output: 198 passed in ~2.5m (100% pass rate)
```

---

## 2. Streamlit Community Cloud Deployment

### Configuration Files
1. **`.streamlit/config.toml`**:
   - `server.headless = true`: Runs without local browser spawn.
   - `server.enableCORS = false`: Allows modern cross-origin web requests.
   - `server.enableXsrfProtection = true`: Prevents cross-site request forgery.
   - Custom Persian-compatible theme (Emerald primary color, clean typography).
2. **`requirements.txt`**:
   - Pinned production dependencies: `httpx`, `pydantic`, `streamlit`, `pulp`, `scipy`, `rapidfuzz`, `pytest`, `pytest-asyncio`, `python-dotenv`.
3. **`streamlit_app.py`**:
   - Canonical 1-click entrypoint importing and invoking `app.py`.

### Deployment Steps (share.streamlit.io)
1. Push the repository to GitHub:
   ```bash
   git add .
   git commit -m "feat: complete spec-oriented development consolidation"
   git push origin master
   ```
2. Navigate to [share.streamlit.io](https://share.streamlit.io) and authenticate with GitHub.
3. Select your repository, branch `master`, and specify `streamlit_app.py` (or `app.py`) as the main entrypoint.
4. *(Optional)* In **Advanced Settings -> Secrets**, add `GEMINI_API_KEY = "..."` if using AI-assisted list parsing.
5. Click **Deploy!**. The app will be live with a public URL within 2 minutes.
