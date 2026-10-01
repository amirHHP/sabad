# BRIEFING — 2026-10-01T12:58:00Z

## Mission
Deliver the Sabad project: production-grade cross-store grocery optimizer and automated cart dispatcher for SnappMarket, Digikala Jet, and Okala.

## 🔒 My Identity
- Archetype: teamwork_preview_orchestrator
- Roles: orchestrator, user_liaison, human_reporter, successor
- Working directory: /Users/sotoon/personal/Sabad/.agents/teamwork/orchestrator_1
- Original parent: parent (sentinel)
- Original parent conversation ID: 32fc6b02-9912-4ba9-b062-161d8860350e

## 🔒 My Workflow
- **Pattern**: Project Pattern (Dual Track: Implementation + E2E Testing)
- **Scope document**: /Users/sotoon/personal/Sabad/PROJECT.md
1. **Decompose**: Survey with 3 Explorers -> PROJECT.md -> Milestones M1..M5 + E2E Test Suite
2. **Dispatch & Execute**: Delegate sub-orchestrators for milestones and E2E testing
3. **On failure**: Retry -> Replace -> Skip -> Redistribute -> Redesign -> Escalate
4. **Succession**: At spawn count >= 16 and all subagents completed, write soft handoff.md, cancel timers, spawn successor.
- **Work items**:
  1. Survey and Scope Mapping [in-progress]
  2. E2E Testing Track [pending]
  3. M1: Live Platform Adapters (SnappMarket, Digikala Jet, Okala) [pending]
  4. M2: Persian Grocery Basket Normalizer [pending]
  5. M3: MILP Optimizer & Flash Deal Trap Auditor [pending]
  6. M4: Cart Dispatcher & Payment Handoff [pending]
  7. M5: Streamlit Web Dashboard [pending]
  8. Final Milestone: 100% E2E Pass + Adversarial Coverage Hardening [pending]
- **Current phase**: 0 (Survey)
- **Current focus**: 3 Explorers investigating APIs, Persian NLP, and MILP/Architecture

## 🔒 Key Constraints
- NEVER write, modify, or create source code files directly.
- NEVER run build/test commands yourself — require workers to do so.
- NEVER investigate or explore the problem at the code level — dispatch Explorers for technical investigation.
- You MAY use file-editing tools ONLY for metadata/state files (.md) in your .agents/teamwork/ folder (and PROJECT.md at project root).
- Mandatory audit enforcement: Binary veto on Forensic Auditor INTEGRITY VIOLATION.
- Pass ORIGINAL_REQUEST.md path to every subagent.
- Mandatory integrity warning on all worker prompts.
- Never reuse a subagent after handoff.

## Current Parent
- Conversation ID: 32fc6b02-9912-4ba9-b062-161d8860350e
- Updated: 2026-10-01T12:55:03Z

## Key Decisions Made
- Project Orchestrator initialized; starting Phase 0 (Survey) with 3 parallel Explorers.

## Team Roster
| Agent | Type | Work Item | Status | Conv ID |
|-------|------|-----------|--------|---------|
| explorer_survey_1 | teamwork_preview_explorer | Live APIs & Networking | in-progress | 62f01a8a-1b80-4a24-9731-9cdeee528efd |
| explorer_survey_2 | teamwork_preview_explorer | Persian NLP & SKU Matcher | in-progress | a83e366a-da31-4a46-878d-1c20935314f7 |
| explorer_survey_3 | teamwork_preview_explorer | MILP Optimizer & Architecture | in-progress | bfc937ac-93b0-4591-ac15-da21f300707f |

## Succession Status
- Succession required: no
- Spawn count: 3 / 16
- Pending subagents: 62f01a8a-1b80-4a24-9731-9cdeee528efd, a83e366a-da31-4a46-878d-1c20935314f7, bfc937ac-93b0-4591-ac15-da21f300707f
- Predecessor: none
- Successor: not yet spawned

## Active Timers
- Heartbeat cron: 5799893c-d08a-4074-9f4c-d6c418836bfa/task-20 (every 10m)
- Safety timer: covered by heartbeat cron
- On succession: kill all timers before spawning successor
- On context truncation: run manage_task(Action="list") — re-create if missing

## Artifact Index
- /Users/sotoon/personal/Sabad/.agents/teamwork/ORIGINAL_REQUEST.md — Authoritative requirements
- /Users/sotoon/personal/Sabad/.agents/teamwork/orchestrator_1/DISPATCH.md — Dispatch log
- /Users/sotoon/personal/Sabad/.agents/teamwork/orchestrator_1/plan.md — Orchestrator plan
- /Users/sotoon/personal/Sabad/.agents/teamwork/orchestrator_1/progress.md — Liveness & status tracking
- /Users/sotoon/personal/Sabad/PROJECT.md — Global project index & milestones
