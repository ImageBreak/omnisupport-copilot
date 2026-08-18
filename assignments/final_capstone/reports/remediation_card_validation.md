# Webhook remediation card validation

## R3 — Query Rewrite

The card calls the existing production `/rag/answer` endpoint with
`retrieval_mode=hybrid`; that endpoint runs the production Query Rewrite service
before retrieval. The contract test case uses `EG-3000`, `EG-BOOT-004`, and `3.9`
and proves all three exact identifiers remain in both the semantic query and the
lexical protected-term set. The existing rewrite service supplies deterministic
fallback when an LLM rewrite fails. Its production integration suite passed
8 tests on 2026-08-18, including lossless timeout and unconfigured-provider
fallback cases.

## R4 — Hybrid retrieval and evidence

The live normal-path response in
[remediation_card_api.json](remediation_card_api.json) returned three real RAG
anchors from `doc:capstone:workspace-webhook-authentication`, including
`anchor-bb22279dc0926ba91ca5e5da`. The card copied each evidence ID, source, and
section from the active RAG response; it did not generate any of those values.

The same report records two safe insufficient-evidence paths:

- missing HTTP status and webhook version returns `needs_clarification=true`;
- a request for a universal third-party retry schedule returns no citations,
  `confidence=0`, and a non-empty `abstain_reason`.

## R5 — Structured output

The live response contains every field in the frozen card schema, including
`summary`, bounded `steps`, typed citations, confidence, clarification/abstention,
action control, `release_id`, and `trace_id`. The contract test validates a valid
card against `contracts/webhook_remediation_card.schema.json` and rejects a card
with a missing `trace_id` or mismatched action control.

## Trace and regression evidence

The live normal response has trace ID `756d4e2b02d8a4845fb7473827f5270e`.
Phoenix contains the card span `product.remediation_card` and its production RAG
children: `rag.query.rewrite`, `rag.retrieve.hybrid`, `rag.retrieve.lexical`,
`rag.retrieve.vector`, and `rag.audit.persist`. The trace records request and
release metadata, not the question text or webhook secret.

The unmodified README command `python -m scripts.capstone.verify_e2e` passed on
2026-08-18 (run ID `3caf2e9ae387`), including the existing governed low-risk
write, HITL wait/resume, and Phoenix checks.

## Verification commands

```bash
docker compose --profile tools --env-file infra/env/.env.local \
  -f infra/docker-compose.yml run --rm devbox \
  pytest tests/contract/test_webhook_remediation_card.py \
    tests/contract/test_week15_capstone_product.py -q

docker compose --profile tools --env-file infra/env/.env.local \
  -f infra/docker-compose.yml run --rm devbox \
  pytest tests/integration/test_query_rewrite_production.py -q

docker compose --profile tools --env-file infra/env/.env.local \
  -f infra/docker-compose.yml run --rm devbox \
  python -m scripts.capstone.verify_e2e
```
