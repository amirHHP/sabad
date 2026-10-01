# BRIEFING — 2026-10-01T13:05:00Z

## Mission
Deliver a production-grade cross-store grocery optimizer and automated cart dispatcher for Iranian quick-commerce platforms (SnappMarket, Digikala Jet, Okala) with Persian grocery normalization, MILP optimization, flash deal trap auditing, cart dispatching, and Streamlit UI.

## 🔒 My Identity
- Archetype: orchestrator
- Roles: orchestrator, user_liaison, human_reporter, successor
- Working directory: /Users/sotoon/personal/Sabad/.agents/teamwork/orchestrator_2
- Original parent: 32fc6b02-9912-4ba9-b062-161d8860350e
- Original parent conversation ID: 32fc6b02-9912-4ba9-b062-161d8860350e

## 🔒 My Workflow
- **Pattern**: Project Pattern with Dual Track
- **Scope document**: /Users/sotoon/personal/Sabad/PROJECT.md
1. **Decompose**: Decompose the project into Milestones M1-M5 + Final Milestone (Phase 1 E2E test pass, Phase 2 adversarial hardening) plus Dual Track E2E Testing Track.
2. **Dispatch & Execute** (pick ONE):
   - **Direct (iteration loop)**: For milestones, delegate each milestone to subagents (or sub-orchestrator) following the Explorer -> Worker -> Reviewer -> Challenger -> Auditor iteration loop.
3. **On failure** (in this order):
   - Retry: nudge stuck agent or re-send task
   - Replace: spawn fresh agent with partial progress
   - Skip: proceed without (only if non-critical)
   - Redistribute: split stuck agent's remaining work
   - Redesign: re-partition decomposition
   - Escalate: report to parent (sub-orchestrators only, last resort)
4. **Succession**: At 16 spawns and all pending subagents complete, write soft handoff.md, cancel crons, spawn successor, record ID, and exit.
- **Work items**:
  1. Survey and Scope Mapping [in-progress]
  2. E2E Testing Track [pending]
  3. M1 Live Platform Adapters [pending]
  4. M2 Persian Grocery Normalizer [pending]
  5. M3 Mathematical Optimizer & Trap Auditor [pending]
  6. M4 Cart Dispatcher & Payment Handoff [pending]
  7. M5 Streamlit Web Dashboard [pending]
  8. Final Milestone (Phase 1 100% E2E, Phase 2 Hardening & Audit) [pending]
- **Current phase**: 0 (Survey & Scope Definition)
- **Current focus**: Complete Survey for M1 (Live Adapters) and M2 (Normalizer), establish PROJECT.md and TEST_INFRA.md

## 🔒 Key Constraints
- Dispatch-only orchestrator: NEVER write or modify production source code directly.
- NEVER run build/test commands yourself — require workers to do so.
- NEVER explore code directly — dispatch Explorers for technical investigation.
- You MAY use file-editing tools ONLY for metadata/state files (.md) in your .agents/teamwork/ folder or project metadata.
- Audit is a binary veto: if auditor reports integrity violation, milestone fails unconditionally.
- Never reuse a subagent after handoff.
- Succession threshold: 16 spawns.

## Current Parent
- Conversation ID: 32fc6b02-9912-4ba9-b062-161d8860350e
- Updated: 2026-10-01T13:04:00Z

## Key Decisions Made
- Inherit explorer_survey_3 handoff for R3, R4, R5, and architecture.
- Re-run/complete Survey for R1 (Live endpoints & network access) and R2 (Persian normalizer) since explorer_survey_1 and explorer_survey_2 were interrupted before handoff.
- Structure project with clean modular architecture under `src/sabad/`.

## Team Roster
| Agent | Type | Work Item | Status | Conv ID |
|-------|------|-----------|--------|---------|
| explorer_survey_live_apis | teamwork_preview_explorer | Survey Live APIs (SnappMarket, Jet, Okala) | in-progress | 05fe1224-feb6-4e4a-87c8-6a34ad7247b0 |
| explorer_survey_persian_nlp | teamwork_preview_explorer | Survey Persian NLP Normalizer & SKU Matcher | in-progress | f35a49d0-fc50-4219-8444-018c86dd075b |

## Succession Status
- Succession required: no
- Spawn count: 2 / 16
- Pending subagents: 05fe1224-feb6-4e4a-87c8-6a34ad7247b0, f35a49d0-fc50-4219-8444-018c86dd075b
- Predecessor: orchestrator_1
- Successor: not yet spawned

## Active Timers
- Heartbeat cron: 5f3ddd0b-8fff-4532-82d8-412561e17041/task-46
- Safety timer: none
- On succession: kill all timers before spawning successor
- On context truncation: run manage_task(Action="list") — re-create if missing

## Artifact Index
- /Users/sotoon/personal/Sabad/.agents/teamwork/ORIGINAL_REQUEST.md — Authoritative User Requirements
- /Users/sotoon/personal/Sabad/.agents/teamwork/explorer_survey_3/handoff.md — Survey Analysis for Optimization, Cart, UI, Architecture
