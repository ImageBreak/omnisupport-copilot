# Bootstrap Baseline

## Provenance

- Validated source commit: `0b0a05698e807889a2af2688ec6ebb90d3d42c04` — `fix: 修正windows下bootstrap执行失败的问题`
- Evidence integration commit: `87be56229a241f29eaf13ce6292d890fd6b36559` — `merge: integrate homework changes with latest main`
- Branch: `homework`
- Bootstrap stage: `all`
- Logical generation timestamp: `2026-07-21T00:00:00+00:00` (this is the deterministic data timestamp, not the command execution time)

## Active Releases

- Product release: `capstone-v1.0.0` (`active`)
- Data release: `data-capstone-v1`
- Index release: `index-capstone-v1`
- Index manifest digest: `sha256:9f299a590c0caeec52598e983d6767c4d2dd76f8e68eed3c752f5b9e5fa691dd`

## Bootstrap Results

| Item | Actual result |
|---|---:|
| Generated/current Capstone tickets | 240 / 240 |
| Valid / invalid tickets | 240 / 0 |
| Bronze new / duplicate records | 0 / 240 |
| Silver upserts | 240 |
| Knowledge assets / active source IDs | 10 / 10 |
| Retrievable chunks | 91 |
| Embeddings written / errors | 91 / 0 |
| Graph entities / edges / communities | 32 / 28 / 4 |

## Passed Checks

- PostgreSQL, MinIO, and Phoenix were healthy; OTel Collector was running.
- Ingest completed with zero ticket errors. The duplicate path confirms an idempotent rerun.
- Five manifests completed parsing with `week8_ready=true`.
- Index build completed with deterministic embeddings and no warnings.
- `dbt build` passed for the `dev` target.
- Graph build passed.
- The governed release became active.

## Warnings and Outstanding Evidence

- Each parse result had status `warn`; the captured summary does not include the individual warning details.
- E2E passed. The unmodified verification output is `e2e_report.json` (run ID `f2beefcfc28b`): runtime health, tenant isolation, hybrid RAG evidence, feedback, governed KPI, low-risk action, HITL approval/resume, and Phoenix traces all passed.
- Iceberg lakehouse materialization was not included in this bootstrap evidence.
- Evaluation has not been executed; `eval_report.md` remains a template.
