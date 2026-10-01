# Dispatch: Explorer Survey 3 (MILP Optimization, Architecture & E2E)
Working directory: /Users/sotoon/personal/Sabad/.agents/teamwork/explorer_survey_3
Original request: /Users/sotoon/personal/Sabad/.agents/teamwork/ORIGINAL_REQUEST.md

## 2026-10-01T12:57:28Z
You are the Optimizer & Architecture Explorer for the Sabad project.
Working directory: /Users/sotoon/personal/Sabad/.agents/teamwork/explorer_survey_3
Authoritative requirements: /Users/sotoon/personal/Sabad/.agents/teamwork/ORIGINAL_REQUEST.md

You MUST read /Users/sotoon/personal/Sabad/.agents/teamwork/ORIGINAL_REQUEST.md before doing anything else.
Note: You are a read-only exploration agent. Do not modify production code. Maintain progress.md with timestamped updates in your working directory.

Your mission:
1. Investigate R3 (Mathematical Basket Optimizer & Flash Deal Trap Auditor):
   - MILP mathematical formulation minimizing total cost: sum of item prices * quantity * store assignment + delivery fee per store.
   - Delivery fee tiered / step function modeling (binary variables for store selection and tier thresholds).
   - Formulations for:
     a) Single-Store Best (100% basket from each individual store)
     b) Flash Deal Trap Audit (quantifying loss-leader discount vs remaining items markup and extra delivery fee)
     c) Multi-Store Split (determining net-positive multi-store division accounting for multiple shipping fees and minimum order values).
   - Solvers available in Python environment (pulp, scipy, ortools, etc.).
2. Investigate R4 (Cart Dispatcher & Payment Handoff): mutation sequencing, item & discount verification, checkout link generation.
3. Investigate R5 (Streamlit Web Dashboard app.py): layout, RTL/Persian support, connection badges, live search progress logs, interactive audit tables, and one-click dispatch.
4. Investigate E2E Testing strategy: 4-tier opaque-box test suite (Tier 1: Feature coverage, Tier 2: Boundary/corner, Tier 3: Combinatorial pairwise, Tier 4: Real-world scenarios) and live verification suite tests/verify_live_endpoints.py.
5. Propose global system architecture, module boundaries, and file layout.
6. Write your comprehensive report to /Users/sotoon/personal/Sabad/.agents/teamwork/explorer_survey_3/handoff.md and notify the parent orchestrator when complete.
