# Webhook remediation card — governed actions validation

The card-action endpoint does not accept model authority. It requires an
authenticated actor, `confirmed=true`, a `card_trace_id`, cited evidence IDs,
and an idempotency key. Server code loads the tenant-scoped card audit record,
requires the submitted operation/control to equal the recorded proposal, and
requires every evidence ID to be one emitted by that card before it invokes the
existing `ticket_update` tool.

The binding also requires the card audit record's `release_id` to equal the
currently running release. A follow-up real call returned the same
`capstone-v1.0.0` release ID for both card and completed action.

The real synthetic-workspace run is recorded in
[remediation_card_actions_api.json](remediation_card_actions_api.json):

- An unconfirmed `add_internal_note` was rejected with
  `409 explicit_confirmation_required`.
- The confirmed note completed, and the identical idempotency key replayed as
  `cached` with the same action-lineage ID rather than writing a second note.
- A 100-cent `grant_service_credit` first returned `awaiting_approval` with
  approval ID `apr_ef2b70e9000842d9917c`; an administrator approval then
  resumed it to `completed`.

Phoenix has the low-risk action span chain
`product.remediation_card.action → tool.idempotency.check →
tool.execute.ticket_update → agent.lineage.persist`. The financial request has
`hitl.evaluate` and `hitl.wait`; its approval-resume trace
`bcea062fd8dcdf029b4955e1b444e37e` has `hitl.resume`,
`tool.execute.ticket_update`, and `agent.lineage.persist`.

## Reproduction

Run the Stage 5 card request first, then call
`POST /api/v1/cases/{ticket_id}/remediation-card/actions` with the card trace,
a cited `evidence_id`, `confirmed=true`, and a new idempotency key. For a service
credit include `amount_cents`; the existing tool contract forces it to
`awaiting_approval`. Decide the approval through
`POST /api/v1/approvals/{approval_id}/decision` as an authorized reviewer.
