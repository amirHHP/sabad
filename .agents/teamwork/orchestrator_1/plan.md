# Orchestration Plan: Sabad Project

## Objective
Build a production-grade cross-store grocery optimizer and automated cart dispatcher for Iranian quick-commerce platforms (SnappMarket, Digikala Jet, Okala), featuring Persian grocery list normalization, MILP mathematical optimization with flash deal trap auditing, cart dispatching with payment handoff, and an interactive Streamlit dashboard.

## Methodology & Architectural Pattern
Project Pattern with Dual Track:
- **Track 1: Implementation Track** (decomposed across independent milestones, each sub-orchestrated or iterated)
  - Milestone 1: Live Reverse-Engineered Platform Adapters (SnappMarket, Digikala Jet, Okala API clients, session persistence in `.sessions/`, rate limiting, live coordinates)
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
1. **Phase 0: Survey**:
   - Dispatch 3 parallel Explorers to inspect the environment, python libraries, existing live network access/coordinates, and detail requirements for R1-R5.
   - Aggregate into merged `PROJECT.md § Feature Inventory` and define interface contracts.
2. **Phase 1: Dual Track Dispatch**:
   - Spawn E2E Testing Orchestrator (Track 2) to design and implement the test harness and test suites.
   - Spawn Implementation Sub-Orchestrators for M1 (Live Platform Adapters) and M2 (Persian Basket Normalizer).
3. **Phase 2: Core Optimization & Dispatch Engine**:
   - Spawn Sub-Orchestrator for M3 (MILP Optimizer & Trap Auditor) depending on M1 & M2 contracts.
   - Spawn Sub-Orchestrator for M4 (Cart Dispatcher) depending on M1 & M3.
4. **Phase 3: Interactive Dashboard UI**:
   - Spawn Sub-Orchestrator for M5 (`app.py` Streamlit UI) integrating all modules.
5. **Phase 4: Final Milestone (E2E Verification & Hardening)**:
   - Await `TEST_READY.md`.
   - Run full E2E test suite (Tiers 1-4) against complete implementation. Fix any failures.
   - Adversarial coverage hardening (Tier 5) with Challengers and Forensic Auditor.
6. **Phase 5: Victory Audit & Completion**:
   - Run Forensic Auditor.
   - Confirm all acceptance criteria satisfied.
   - Report to Sentinel.
