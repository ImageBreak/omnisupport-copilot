# Webhook remediation knowledge pipeline evidence

## Scope and reproducibility

This report covers the existing `parse -> chunk -> evidence anchor -> index` path
only. It is reproducible from the repository root with Docker Devbox and does not
require a host Python virtual environment:

```bash
docker compose --profile capstone --env-file infra/env/.env.local \
  -f infra/docker-compose.yml run --rm capstone_bootstrap \
  python -m scripts.capstone.bootstrap --root /workspace --stage knowledge
```

The generated Workspace manifest is
`manifest-capstone-northstar-workspace-20260721-002`; it includes the two
Webhook-remediation sources and is bound to `data-capstone-v1` and
`index-capstone-v1`.

## New sources and evidence

| Source | Chunks | Unique sections | Evidence anchors | Example real evidence ID |
|---|---:|---:|---:|---|
| `doc:capstone:workspace-webhook-authentication` | 14 | 14 | 14 | `anchor-8a44ddfa06e95d0a0192a1d1` |
| `doc:capstone:workspace-webhook-delivery-retry` | 16 | 16 | 16 | `anchor-001f95ca6d2a23624203b67d` |

The counts came from PostgreSQL `knowledge_section` and `evidence_anchor` rows
for `data-capstone-v1`; each source had `chunk_count == unique_section_count`.
This rules out duplicate sections for the new sources.

## Embedding and repeatability result

To create a strict first-run versus rerun comparison, only the local derived rows
for the two new sources were reset before run 1: 2 parsed-document records, 30
chunks, and 30 evidence anchors. Raw asset metadata, all other sources, the
release pointer, and MinIO objects were preserved.

Run 1 then recreated and embedded the new sources: `embedded=30` and
`skipped=175`. Run 2 used the identical manifest and release context:
`embedded=0`, `skipped=205`, and `errors=0`. In this indexer, `skipped` means
"already indexed on the requested release", not "embedding was omitted".

Post-run PostgreSQL verification shows `14/14` embedded vectors for the
authentication source and `16/16` for the retry source, all with
`index_release_id=index-capstone-v1`.

The two recorded runs are [run 1](knowledge_pipeline_run_1.json) and
[run 2](knowledge_pipeline_run_2.json). Both ended with 12 active sources and
205 active chunks. The second run had a chunk delta of `0`; the index performed
`embedded=0`, `skipped=205`, and `errors=0`. This is the required no-duplicate
result for identical input and release context.

## Retrieval proof

An authenticated, tenant-scoped call to the existing `/rag/answer` endpoint
returned these citations from the new authentication source:

- `anchor-8a44ddfa06e95d0a0192a1d1`: the HTTP 401 delivery-log and request-ID step.
- `anchor-bb22279dc0926ba91ca5e5da`: the required HTTP status, webhook version,
  event ID, request ID, and timestamp facts.

The response carried `release_id=capstone-v1.0.0`,
`data_release_id=data-capstone-v1`, `index_release_id=index-capstone-v1`, and
`trace_id=9df6b9ed184d6ff203809c9efdb681aa`. The evidence IDs above are copied from
the live RAG response, not hand-authored.

## Explicit GraphRAG boundary

Running the all-stage bootstrap reaches the knowledge stage successfully but then
stops at graph construction because the two new sources have no reviewed graph
annotations. This is intentionally outside this small knowledge-pack scope: this
stage reuses hybrid RAG and does not claim a GraphRAG rebuild. The knowledge-stage
evidence above remains valid and indexed.
