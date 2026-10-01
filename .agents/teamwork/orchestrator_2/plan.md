# Orchestration Plan: Sabad Project (Generation 2)

## Objective
Build a production-grade cross-store grocery optimizer and automated cart dispatcher for Iranian quick-commerce platforms (SnappMarket, Digikala Jet, Okala), featuring Persian grocery list normalization, MILP mathematical optimization with flash deal trap auditing, cart dispatching with payment handoff, and an interactive Streamlit dashboard.

## Methodology & Architectural Pattern
Project Pattern with Dual Track:
- **Track 1: Implementation Track** (decomposed across independent milestones, each sub-orchestrated or iterated)
  - Milestone 1: Live Reverse-Engineered Platform Adapters (SnappMarket, Digikala Jet, Okala API clients, session persistence in `.sessions/`, rate limiting, live coordinates, spoofed headers)
  - Milestone 2: Natural Language Persian Basket Normalizer (fuzzy matching, Persian digit support, strict attribute verification: brand, volume, fat percentage)
  - Milestone 3: Mathematical Basket Optimizer & Flash Deal Trap Auditor (MILP formulation, single-store best, trap audit, multi-store split)
  - Milestone 4: Cart Dispatcher & Payment Gateway Handoff (authenticated cart mutations, discount verification, checkout URLs)
  - Milestone 5: Streamlit Web Dashboard (`app.py` with real-time status badges, Persian input preview, live search logs, trap report, one-click dispatch)
  - Final Milestone: Pass 100% of E2E Test Suite (Tiers 1-4) + Adversarial Coverage Hardening (Tier 5)
- **Track 2: E2E Testing Track** (opaque-box, requirement-driven, 4-tier test suite + test runner)
  - Tier 1: Feature Coverage (>=5 per feature)
  - Tier 2: Boundary & Corner Cases (>=5 per feature)
  - Tier 3: Cross-Feature Combinations (pairwise coverage)
  - Tier 4: Real-World Persian Grocery Application Scenarios
  - Publishes `TEST_READY.md`

## Phase Execution Steps
1. **Phase 0: Survey Completion & Scope Definition**:
   - We have Explorer 3 handoff covering MILP, Cart Dispatch, UI, and Architecture.
   - Dispatch Explorers for M1 (Live Platform APIs probe) and M2 (Persian NLP extraction).
   - Consolidate all findings into `PROJECT.md` at root and `TEST_INFRA.md`.
2. **Phase 1: Dual Track Dispatch**:
   - Spawn E2E Testing Orchestrator / Test Writers for Track 2.
   - Spawn Implementation Subagents / Sub-Orchestrator for M1 (Live Adapters) and M2 (Persian Normalizer).
3. **Phase 2: Core Optimization & Dispatch Engine**:
   - Spawn Implementation for M3 (MILP Optimizer & Trap Auditor).
   - Spawn Implementation for M4 (Cart Dispatcher).
4. **Phase 3: Interactive Dashboard UI**:
   - Spawn Implementation for M5 (`app.py` Streamlit UI) integrating all modules.
5. **Phase 4: Final Milestone (E2E Verification & Hardening)**:
   - Await `TEST_READY.md`.
   - Run full E2E test suite (Tiers 1-4) against complete implementation. Fix any failures.
   - Adversarial coverage hardening (Tier 5) with Challengers.
6. **Phase 5: Victory Audit & Completion**:
   - Run Forensic Auditor (`teamwork_preview_auditor`).
   - Confirm all acceptance criteria satisfied.
   - Report to Sentinel.
