# Webhook remediation card evaluation report

## Candidate / baseline / dataset / commit / release

| Field | Value |
|---|---|
| Candidate | `webhook_remediation_card_v1.1`: structured card, production Query Rewrite + Hybrid RAG, card-to-action evidence binding |
| Baseline | Existing generic `/rag/answer` and generic action route, assessed against the *new* card/action requirements; it has no card schema, explicit confirmation, or card evidence binding |
| Dataset | `evals/golden_set.jsonl`, 8 reviewed synthetic cases, SHA-256 `d00f188c56ce0ccc6684010beb1278df4f422cc1dce90401dae929330297af21` |
| Commit | `87be56229a241f29eaf13ce6292d890fd6b36559` on `homework`, plus this uncommitted candidate working tree |
| Release | product `capstone-v1.0.0`; data `data-capstone-v1`; index `index-capstone-v1` |
| Runtime | Docker/Devbox and local service stack; all inputs are synthetic |

Raw per-case outcomes and trace references are in [eval_results.json](eval_results.json).

## Metrics and acceptance thresholds

| Metric | Threshold | Baseline | Candidate | Result |
|---|---:|---:|---:|---|
| Key-point pass rate | >= 80% | 3/8 (37.5%) | 8/8 (100%) | pass |
| Citation support rate | 100% when a citation is present | not applicable to card contract | 100% | pass |
| High-risk action bypasses | 0 | no card-level binding | 0 | pass |
| Model-fault request success | 100% (fallback allowed; no 500) | shared rewrite fallback | 8/8 regression assertions | pass |
| Original Capstone E2E | pass | pass | retained pass evidence | pass |
| API latency p95 | report, no cross-machine gate | not comparable | not used as a gate | reported limitation |

The baseline is deliberately not scored as a defective model: it is the existing generic capability evaluated against a new structured-card and governed-action contract. Its C2, C7, and C8 foundations already work; the candidate adds the missing product behavior.

## Per-case results (C1–C8)

| Case | Baseline | Candidate | Evidence / trace |
|---|---|---|---|
| C1 normal evidence answer | fail: no frozen card shape | pass | auth evidence; `c4467e16fbbffe7cd5dda0570593c622` |
| C2 identifier preservation | pass: protected terms and edge hybrid retrieval | pass | edge evidence; `86743cd4562e2305a744e785fe1af482` |
| C3 ambiguous clarification | fail: generic response has no mandatory clarification fields | pass | `needs_clarification=true`; `6e5fc65ae766ebe49d2cb51991627a09` |
| C4 insufficient evidence | fail: no card abstention contract | pass | empty citations and abstain reason; `3893016f2fb76a9efa607be580eb650c` |
| C5 low-risk action | fail: no card confirmation/evidence receipt | pass | confirm card `f274d61dd29e05cd5ab9d77307de7695`; completed/cached action in [action report](remediation_card_actions_api.json) |
| C6 financial HITL | fail: cross-product policy was unreachable before fix | pass after retrieve fix | policy evidence and `hitl` proposal; `84c6bdb6910ebd9df15b6b191b919270` |
| C7 model fault fallback | pass: existing production fallback | pass | `tests/integration/test_query_rewrite_production.py`: 8 passed |
| C8 regression / rollback | pass: original RAG evidence | pass | Workspace API evidence; `7307dce2e69af79f5e377cd8deb62ddc`; existing E2E pass report |

## Baseline vs candidate comparison

The candidate preserves the baseline Query Rewrite and Hybrid RAG implementation; it does not create another vector store or retrieval path. The differences are the evidence-gated card schema, clarification/abstention policy, allowed action proposal mapping, server-side evidence receipt, explicit confirmation, and the cross-product policy retrieval correction. C5 and C6 use the existing `ticket_update` idempotency and HITL system rather than a new write mechanism.

## Failed cases and root-cause categories

One candidate failure was observed during this run and fixed before the final candidate score:

```text
case_id: C6_high_risk_action_hitl
observed: Initial card response had no citations, abstained with no_retrieval_results, and proposed no action.
expected: The published service-credit policy is retrievable for a Workspace incident and yields only grant_service_credit/hitl.
trace_id: 77ecf6ca3dca4bf4d679146dc6cd466c
failed_stage: retrieve
root_cause: The policy document was indexed with product_line=cross_product, while the Hybrid RAG metadata filter required exact northstar_workspace equality. An initial attempted allow-list used enum value any, but the real product_line enum has no any member; that SQL error degraded retrieval to no results.
fix: Permit only the existing cross_product enum label alongside the requested product line; preserve visibility, release, and tenant filtering.
regression_test: tests/integration/test_rag_cross_product_retrieval.py::test_workspace_retrieval_includes_cross_product_policy_documents
residual_risk: Cross-product documents may become overly broad if their manifest visibility or content classification is wrong; document review remains required.
```

Final root-cause counts: retrieve 1 fixed; rewrite 0; rerank 0; generate 0; policy 0; tool 0; release 0.

## One Phoenix trace walkthrough

The failing C6 trace `77ecf6ca3dca4bf4d679146dc6cd466c` links the public card request to `product.remediation_card`, then `rag.query.rewrite`, `rag.retrieve.hybrid`, lexical/vector retrieval, RRF, rerank, and `rag.audit.persist`. The full chain completed without a 500, but yielded no eligible evidence, so the card safely abstained. PostgreSQL inspection of the indexed document showed `doc:capstone:support-credit-policy` was active, internal, embedded (22 chunks), and classified `cross_product`, establishing the retrieval-filter mismatch rather than a missing document or model failure.

After the fix, C6 trace `84c6bdb6910ebd9df15b6b191b919270` has the same observable chain and returns two policy evidence anchors plus a `hitl` proposal. Default span metadata contains identifiers, hashes, release IDs, and decision metadata; it does not record the customer question, signing secret, webhook payload, or PII.

## Regression and hard-gate result

- Candidate/card contracts: `19 passed`.
- Cross-product retrieval plus production Query Rewrite fallback: `9 passed`.
- Existing action report proves `completed`, idempotent `cached`, `awaiting_approval`, and approval `resume` states.
- Existing [Capstone E2E report](../../../../reports/capstone/e2e-verification.json) is `pass`, including Phoenix HITL wait/resume validation.

## Limitations and next experiment

This is a small synthetic eight-case gate, not a production quality estimate. Latency p95 was not compared across machines because this run uses shared local services and Docker start-up costs; collect per-request server latency over a fixed warmed sample before setting a release threshold. Next, add an approved cross-product-policy manifest flag instead of inferring eligibility only from the `cross_product` label, then test tenant/entitlement combinations explicitly.
