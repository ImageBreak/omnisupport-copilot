# Change Notes

## Webhook remediation knowledge package v1

- Added two synthetic HTML knowledge sources under `../data/documents/` for
  Workspace webhook authentication (HTTP 401/signing-secret rotation) and
  delivery recovery (HTTP 404/retry/idempotency/version handling).
- Replaced the placeholder `../data/manifest.json` with the contract-compatible
  `manifest-capstone-webhook-remediation-20260818-001`.
- The manifest declares source identity, versioned source content, synthetic
  license, PII scan status, raw byte size, and SHA-256 for every asset. It is the
  auditable source-of-record for this assignment artifact.

## Webhook remediation capability contract v1

- Added `webhook_remediation_card.schema.json`: strict response schema with a
  three-step maximum, typed citations (evidence ID, source, and section), confidence, clarification/abstention,
  action proposal, release ID, and trace ID.
- Added `webhook_remediation_skill.contract.json`: binds the card to tenant-scoped
  RAG evidence and the existing governed `ticket_update` contract. It fixes the
  action controls to `none`, `confirm`, and `hitl`; it does not grant the model
  authority to execute a write.

## Governed action binding v1.1

- Added `webhook_remediation_action.schema.json`: request/result contract for a
  human-confirmed action bound to one tenant-scoped card trace and its
  server-recorded citations.
- The only eligible operations are existing `ticket_update` operations:
  `add_internal_note` (confirmation) and `grant_service_credit` (HITL). The
  contract requires an idempotency key and rejects evidence not emitted by the
  referenced card.

## Windows bootstrap reliability

- SQL migration files are normalized to LF through `.gitattributes`.
- Bootstrap computes migration checksums from raw bytes, matching the migration gate across Windows and Unix worktrees.
- The application uses the unified LLM provider path; no direct `bailian_api_key` client integration is retained.
