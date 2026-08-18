# Release and rollback evidence — Webhook Remediation Card

## Release binding

- `release_id`: `capstone-v1.1.1` (candidate; activated, then deliberately rolled back for C8 verification)
- `data_release_id`: `data-capstone-v1` — synthetic package is versioned in Git at `assignments/final_capstone/data/` (commit `9a75b83`)
- `index_release_id`: `index-capstone-v1`
- `prompt_release_id`: `prompt-capstone-v1`
- `skill/service release`: `skills-webhook-remediation-v1.1.0` / `services-webhook-remediation-v1.1.0`; service versions: `rag_api=1.1.0`, `tool_api=1.0.0`, `copilot_api=1.1.0`
- Candidate Git SHA: `98c7f4f6c4519684b4d8e4be7475901cac3d610e`
- Previous approved release / rollback target: `capstone-v1.0.0`

The governed manifest binds these values together, including `previous_release_id`, rather than relying on an untracked local environment alone. Trace capture keeps raw content disabled through `OTEL_CAPTURE_CONTENT=false`.

## Gates

`contract / eval / security / e2e = pass`

- Contract: `pytest tests/contract/test_webhook_remediation_card.py tests/contract/test_week15_capstone_product.py -q` — **19 passed**.
- Evaluation: `eval_report.md` records C1–C8 at **8/8**, citation support 100%, high-risk-action bypasses 0, and the documented Phoenix bad-case repair.
- Security: `pytest tests/integration/test_week15_capstone_security.py -q` — **3 passed**. Controlled-action evidence remains in `remediation_card_actions_api.json`: confirmation required; idempotent low-risk action; high-risk HITL wait and resume.
- Original E2E after rollback: **pass**, run `70eadfba6968`; durable output is `e2e_post_rollback.json`.

## Candidate dry-run and activation

The release dry-run returned `dry_run_pass`, target `capstone-v1.1.1`, rollback target `capstone-v1.0.0`, next pointer generation `4`, and manifest digest `sha256:80d58421b4d89872e05bd3700b77c8d2ad997c101b9df2254d14154ebe4b02b7`.

Activation evidence: local `governed_release_manifest` row `capstone-v1.1.1` and `release_environment_pointer(dev)` at generation `4`. A real authenticated card request then returned:

```json
{
  "release_id": "capstone-v1.1.1",
  "trace_id": "b22c45f89f471846bbe4fe0b6b04f88a",
  "citation_count": 2,
  "needs_clarification": false,
  "proposed_action": {"operation": "none", "control": "none"}
}
```

This is an API result produced from Hybrid RAG; its citations are emitted retrieval evidence, not handwritten anchors.

## Dry-run and rollback verification

Rollback dry-run passed from candidate `capstone-v1.1.1` to direct predecessor `capstone-v1.0.0` (planned generation `5`). The actual rollback advanced `release_environment_pointer(dev)` to generation `5`, with `active_release_id=capstone-v1.0.0` and `previous_release_id=capstone-v1.1.1`.

Runtime verification after recreating services with the baseline bindings:

```json
{
  "health_release_id": "capstone-v1.0.0",
  "card_status": 404,
  "card_detail": "remediation_card_not_enabled_for_release"
}
```

Thus C8 verifies both sides of rollback: the original E2E remains green and the candidate-only card is explicitly disabled by a service configuration gate. The final local environment intentionally remains on the proven rollback target, not on the candidate.
