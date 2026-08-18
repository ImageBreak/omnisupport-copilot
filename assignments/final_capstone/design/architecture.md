# Architecture

## Product problem: Webhook remediation card

Northstar support agents already use OmniSupport Copilot to inspect a case, retrieve
internal evidence, add internal notes, and submit service-credit requests for
approval. They currently have to turn a free-form answer into a safe, repeatable
incident response themselves. The **Webhook remediation card** makes that decision
explicit for the `northstar_workspace` product line.

The selected topic is **Workspace webhook delivery troubleshooting**: HTTP 404 and
401 failures, signing-secret rotation, retries, duplicate delivery, and webhook
version handling. It is intentionally narrow enough to be grounded by a small
knowledge pack while exercising the existing RAG, governed-tool, evaluation,
Phoenix, and release/rollback paths.

### Primary user and trigger

The primary user is a Northstar support agent working inside an authenticated,
tenant-scoped Workspace case. The agent asks a webhook troubleshooting question
(for example, a failed delivery after an endpoint change). The card retrieves
published internal evidence constrained to the case tenant and product line, then
returns a diagnostic plan. It does not use untrusted case text as proof and does
not infer a root cause that the retrieved evidence does not support.

### Main request path

```text
Authenticated support agent + tenant-scoped Workspace case
  -> remediation-card API validates ticket and actor context
  -> Query Rewrite preserves exact identifiers (HTTP status, version, error code)
     and falls back deterministically on model failure
  -> existing Hybrid RAG applies tenant, product-line, visibility, and release filters
  -> evidence gate accepts only retrieved anchors with source and section metadata
  -> schema-validated remediation card: diagnosis, <=3 ordered steps, citations,
     confidence, clarification/abstention decision, and proposed action
  -> optional action: explicit confirmation + idempotency + card trace/evidence receipt
     -> internal note completed OR service credit awaiting approval -> authorized resume
  -> Phoenix spans and release pointer connect the response/action to its trace and version
```

The same path fails safely: missing operational context produces a clarification;
missing, conflicting, or unauthorized evidence produces an abstention with no
invented citation; a model failure degrades Rewrite/Generation rather than
returning a 500.

### Successful outcome

A successful card:

- gives a one-sentence, evidence-supported diagnosis without asserting an
  unverified cause;
- orders the next troubleshooting steps, preserving supplied HTTP status, webhook
  version, event identifier, and request/correlation identifier where present;
- cites only evidence returned by the active RAG retrieval, with the original
  `evidence_id` and source metadata;
- reports calibrated confidence and a concrete next-action recommendation;
- returns the active `release_id` and request `trace_id`, so a reviewer can
  connect the response to retrieval, generation, decision, and governed-action
  spans in Phoenix.

### Clarification, abstention, and approval boundaries

The card must request clarification rather than diagnose when required operational
facts are absent (notably both the HTTP status and webhook version when no
concrete delivery status is provided). With a concrete status it may give a
non-causal checklist while retaining the version as a requested verification
step. A service-credit request is handled as a policy-grounded HITL proposal,
not as a diagnosis. It must abstain when no tenant-authorized published evidence is
retrieved, when evidence conflicts, or when the evidence does not support the
claimed cause. It must never invent citations, evidence identifiers, URLs, status
codes, versions, or secret values.

The card may propose `add_internal_note` or `grant_service_credit`; it is not an
authority to execute either operation. Its action endpoint requires an
authenticated actor, explicit confirmation, a fresh idempotency key, and the
card trace plus cited evidence IDs. Code loads the tenant- and release-scoped
server audit record, rejects a different proposed operation or handwritten
evidence, and only then passes the action to the existing Skill/Tool control
plane. Internal notes may complete after confirmation; service credits always
enter HITL and may complete only after an authorized approval resumes them.

Tenant filtering applies both to case context and retrieval. Trace attributes use
identifiers, hashes, lengths, release IDs, and controlled decision metadata by
default; they must not record customer message text, webhook payloads, signing
secrets, or PII.

### Frozen output contract

The capability response is a JSON object with this frozen shape. `citations` is
populated only from the retrieval response; each citation retains its retrieved
evidence anchor, source, and section locator. `trace_id` and `release_id` come
from the runtime request/release context, not from model output.

```json
{
  "summary": "一句话诊断，不编造未证实原因",
  "steps": ["步骤1", "步骤2", "步骤3"],
  "citations": [{"evidence_id": "...", "source": "...", "section": "..."}],
  "confidence": 0.0,
  "needs_clarification": false,
  "abstain_reason": null,
  "proposed_action": {
    "operation": "none|add_internal_note|grant_service_credit",
    "control": "none|confirm|hitl"
  },
  "release_id": "...",
  "trace_id": "..."
}
```

### Non-goals

- No redesigned frontend, new vector database, model training, cloud deployment,
  production-scale load test, or wholesale GraphRAG rewrite.
- No direct webhook replay, secret rotation, endpoint update, or other operational
  write from the card.
- No automatic service-credit grant and no bypass of the existing approval,
  authorization, evidence, or idempotency controls.
- No cross-tenant case or evidence lookup, no hand-authored citation treated as
  retrieval evidence, and no sensitive customer or secret content in Trace.

### Key decisions and trade-offs

- **Reuse the production retrieval chain, not a new knowledge stack.** The card
  uses existing Query Rewrite, FTS + vector Hybrid RAG, evidence anchors, and
  pgvector. This keeps data lineage and tenant filtering in one proven path;
  the trade-off is that the small package does not attempt a separate GraphRAG
  design or production-scale retrieval tuning.
- **Prefer safe uncertainty over fluent speculation.** The card may return a
  shorter clarification or abstention instead of a diagnosis when evidence is
  absent, conflicting, or insufficient. This reduces apparent answer coverage
  but preserves the no-false-evidence requirement.
- **The model proposes; server code authorizes and executes.** Proposed actions
  are constrained by the frozen contract, while tenant/case/release binding,
  explicit confirmation, idempotency, permissions, and HITL are enforced by the
  existing Skill/Tool control plane. This deliberately adds a control step
  before any side effect.
- **Trace identifiers, not customer content.** Phoenix receives trace/release
  links, decision metadata, and identifiers/hashes by default, while raw
  questions, payloads, secrets, and PII are excluded. The trade-off is less
  convenient prompt-level debugging in exchange for the privacy hard gate.
- **Release is a version binding plus a feature gate.** Data, index, prompt,
  Skill, service, and Git versions are recorded in the governed manifest; the
  remediation-card feature gate makes the candidate capability explicitly
  disableable after rollback. This requires service recreation during a local
  rollback but makes the rollback behavior observable.

### Hard delivery gates

The feature is not releasable unless all of the following are demonstrated:

- **G1 runnable:** the README Docker/Devbox workflow can reproduce it without a
  personal virtual environment;
- **G2 real evidence:** citations originate from actual retrieval results;
- **G3 tenant and privacy:** retrieval is tenant-scoped and default telemetry
  excludes customer text, secrets, and PII;
- **G4 controlled side effects:** high-risk actions remain permissioned,
  idempotent, and human-approved in code and contracts;
- **G5 regression safety:** new contract/unit tests pass and
  `scripts.capstone.verify_e2e` remains green;
- **G6 traceability:** response IDs and a verification report connect a request to
  its key spans and versioned release context.

```text
Synthetic documents + manifest
  -> bootstrap ingest
  -> PostgreSQL Bronze/Silver metadata + MinIO raw objects
  -> parse, quality gate, evidence anchors, pgvector index
  -> Copilot API / governed analytics / GraphRAG

PostgreSQL runtime tables
  -> optional Lakehouse materialization
  -> Iceberg Bronze/Silver snapshots in MinIO
```

`bootstrap` prepares the operational product path. Iceberg materialization is a separate lakehouse step for offline analytics, snapshots, and time-travel use cases.
