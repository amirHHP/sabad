# Sabad (سبد) — Specification-Oriented Development (SOD) Hub

> **Single Source of Truth (SSOT)** for AI coding agents and software engineers.  
> Every feature, model, business rule, and interface contract in Sabad is formally specified here.

---

## 📖 What is Spec-Oriented Development (SOD)?

In **Spec-Oriented Development**, specifications precede and govern code. Any AI agent or developer working on Sabad must:
1. **Read the Relevant Spec First**: Never guess how an API behaves, how currency is converted, or how matching rules work. Check the spec.
2. **Code Implements the Spec**: If an implementation deviates from the spec, update the code to conform—or explicitly amend the spec if business requirements evolved.
3. **Tests Verify the Spec**: Every acceptance criterion in the specifications maps directly to automated tests in `tests/`.

---

## 🗺️ Specification Map

| Spec File | Focus Area | Description |
|:---|:---|:---|
| [**`01-architecture-and-dataflow.md`**](01-architecture-and-dataflow.md) | **System Topology** | 5-layer pipeline architecture, end-to-end dataflow, and component interactions. |
| [**`02-data-models-and-contracts.md`**](02-data-models-and-contracts.md) | **Domain Models** | Pydantic data schemas: catalog items, parsed grocery lists, orders, and optimization results. |
| [**`03-store-adapters-api.md`**](03-store-adapters-api.md) | **Live Store APIs** | Endpoints, headers, OTP authentication, and currency normalization (Tomans vs Rials). |
| [**`04-nlp-and-sku-matching.md`**](04-nlp-and-sku-matching.md) | **Persian NLP & Matcher** | Entity extraction, Persian unit regexes, fuzzy matching, and strict volume/flavor filters. |
| [**`05-optimization-engine.md`**](05-optimization-engine.md) | **MILP & Trap Auditor** | Mathematical cost minimization, tiered shipping, split friction, and marketing trap audit. |
| [**`06-ui-and-transparency.md`**](06-ui-and-transparency.md) | **User Interface** | Streamlit dashboard design, 4-tab itemized calculation audit UI, and session isolation. |
| [**`07-testing-and-deployment.md`**](07-testing-and-deployment.md) | **Testing & Cloud Ops** | 198-test verification matrix, smoke tests, and Streamlit Community Cloud deployment. |

---

## 🤖 Guidance for Future AI Agents

When interacting with or extending Sabad:
- **Never divide SnappMarket search prices by 10**: SnappMarket prices are native Tomans. Digikala Jet and Okala are Rials and require `/ 10.0`. See [Spec 03](03-store-adapters-api.md).
- **Preserve Persian regex boundaries**: Standard `\b` fails on Persian characters. Use negative lookaheads `(?![آ-ی\w\u0600-\u06FF])`. See [Spec 04](04-nlp-and-sku-matching.md).
- **Enforce strict volume and flavor exclusions**: 4L dish soap must never match 1kg. Plain milk must never match flavored milk (melon, chocolate). See [Spec 04](04-nlp-and-sku-matching.md).
- **Run the full test suite**: Always run `pytest` before finalizing any changes. All 198 tests must pass. See [Spec 07](07-testing-and-deployment.md).
