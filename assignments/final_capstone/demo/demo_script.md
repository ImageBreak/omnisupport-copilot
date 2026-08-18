# Demo Script — Webhook Remediation Card

本脚本只使用合成账号、合成工单 `TKT-20260706-900123` 和合成知识包。演示前应从仓库根目录启动 Docker Compose；不要使用个人 venv，也不要输入真实客户文本、密钥或 PII。

## 0. 预检与候选发布

为避免与已有演示记录的 manifest 冲突，选择一个尚未使用的候选 ID；下例使用当天的本地演示 ID。将该 ID 同时写入 `infra/env/.env.local` 的 `CAPSTONE_RELEASE_ID`，并设置 `CAPSTONE_REMEDIATION_CARD_ENABLED=true`，然后重建三个 API 服务。

```powershell
$candidate = "capstone-demo-20260819"
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm -e CAPSTONE_RELEASE_ID=$candidate -e CAPSTONE_SKILL_RELEASE_ID=skills-webhook-remediation-v1.1.0 -e CAPSTONE_SERVICE_RELEASE_ID=services-webhook-remediation-v1.1.0 devbox python -m scripts.capstone.bootstrap --root /workspace --stage release --dry-run
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm -e CAPSTONE_RELEASE_ID=$candidate -e CAPSTONE_SKILL_RELEASE_ID=skills-webhook-remediation-v1.1.0 -e CAPSTONE_SERVICE_RELEASE_ID=services-webhook-remediation-v1.1.0 devbox python -m scripts.capstone.bootstrap --root /workspace --stage release
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml up -d --force-recreate rag_api tool_api copilot_api
Invoke-RestMethod http://localhost:8002/health | ConvertTo-Json -Depth 6
```

预期：release dry-run 为 `dry_run_pass`，激活结果为 `active`，健康检查的 `release_id` 等于 `$candidate`。本地模型实际验收配置为 `deepseek / deepseek-v4-flash`；模型故障时允许 deterministic fallback。

## 1. 获取合成坐席身份

```powershell
$login = Invoke-RestMethod -Method Post -Uri http://localhost:8002/api/v1/auth/login -ContentType application/json -Body '{"email":"agent@northstar.demo","password":"Agent@2026"}'
$headers = @{ Authorization = "Bearer $($login.access_token)" }
$ticket = "TKT-20260706-900123"
```

演示时只显示 API 返回的 `trace_id`、release 和合成 evidence；不要打印 access token。

## 2. C1：正常证据方案卡

```powershell
$card = Invoke-RestMethod -Method Post -Uri "http://localhost:8002/api/v1/cases/$ticket/remediation-card" -Headers $headers -ContentType application/json -Body '{"question":"Workspace webhook returned HTTP 401 after signing-secret rotation on webhook version 2026-07. What should I verify?"}'
$card | Select-Object summary,steps,citations,confidence,needs_clarification,abstain_reason,proposed_action,release_id,trace_id | ConvertTo-Json -Depth 8
```

展示点：最多三步；至少一条 citation 的 `evidence_id/source/section`；`release_id=$candidate`；保存 `$card.trace_id`，在 Phoenix（<http://localhost:6006>）按 trace 搜索并展示 `product.remediation_card`、Rewrite、Hybrid retrieval 和 audit spans。

## 3. C3/C4/C7：安全失败而非编造答案

依次将上一步的 `question` 改为以下输入并展示结果：

- `The webhook is not working. What do I do?`：应给出 `needs_clarification=true`，而不是猜测签名或路由原因。
- `What exact retry interval does every third-party webhook consumer use?`：应 abstain，`abstain_reason` 非空且 citations 为空。
- 停止/模拟模型服务或制造非法 JSON：请求仍应成功，debug/trace 显示 fallback，而不是 HTTP 500。

不要在演示时手写 `evidence_id` 或 URL 作为引用；引用必须来自该卡片响应。

## 4. C5：低风险动作、确认和幂等

先生成一个会建议内部备注的卡片，再使用**该卡片自己的** trace 和第一条 citation。先将 `confirmed` 改为 `false` 演示 409；随后改回 `true`，并用相同 idempotency key 重放一次。

```powershell
$noteCard = Invoke-RestMethod -Method Post -Uri "http://localhost:8002/api/v1/cases/$ticket/remediation-card" -Headers $headers -ContentType application/json -Body '{"question":"Draft an internal note for this HTTP 404 webhook incident after I confirm the corrected endpoint was verified."}'
$notePayload = @{ card_trace_id=$noteCard.trace_id; operation="add_internal_note"; confirmed=$true; reason="Synthetic demo: confirmed corrected endpoint."; evidence_ids=@($noteCard.citations[0].evidence_id); idempotency_key="demo-note-20260819" } | ConvertTo-Json
$noteResult = Invoke-RestMethod -Method Post -Uri "http://localhost:8002/api/v1/cases/$ticket/remediation-card/actions" -Headers $headers -ContentType application/json -Body $notePayload
$noteReplay = Invoke-RestMethod -Method Post -Uri "http://localhost:8002/api/v1/cases/$ticket/remediation-card/actions" -Headers $headers -ContentType application/json -Body $notePayload
$noteResult, $noteReplay | Select-Object status,trace_id,release_id | ConvertTo-Json
```

预期：确认前为 `409 explicit_confirmation_required`；首次为 `completed`，相同 key 重放为 `cached`，且不会创建第二条内部备注。

## 5. C6：高风险服务补偿进入 HITL

生成“USD 1 service credit”的卡片，提交 `grant_service_credit` 时使用该卡的 trace/evidence 和新 idempotency key。展示它为 `awaiting_approval`，以管理员账号调用 `POST /api/v1/approvals/{approval_id}/decision` 批准后才变为 `completed`。这一步只对合成工单执行。

可直接展示已保存的可复现结果：

- [动作 API 结果](../reports/remediation_card_actions_api.json)：确认拒绝、`completed`/`cached`、`awaiting_approval` 和 resume trace。
- [动作控制说明](../reports/remediation_card_actions_validation.md)：tenant、case、release、card trace 和 evidence 的服务端绑定规则。

## 6. D4：代码与测试核对

```powershell
git branch --show-current
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox pytest tests/contract/test_webhook_remediation_card.py tests/contract/test_week15_capstone_product.py -q
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox pytest tests/integration/test_week15_capstone_security.py -q
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox pytest tests/integration/test_rag_cross_product_retrieval.py tests/integration/test_query_rewrite_production.py -q
```

预期：个人分支为 `homework`；方案卡/产品契约 `19 passed`，安全测试 `3 passed`，RAG+Rewrite 回归 `9 passed`。失败路径由 C3、C4、C7、未确认动作 409 和跨产品策略检索回归共同覆盖；它们是“预期安全失败”测试，不是允许测试套件失败。

## 7. C8：回滚与原 E2E

先对 `$candidate` 运行 rollback dry-run，再实际回退到 `capstone-v1.0.0`；将 `.env.local` 同步设为 `CAPSTONE_RELEASE_ID=capstone-v1.0.0`、`CAPSTONE_REMEDIATION_CARD_ENABLED=false`，重建 API 服务。

```powershell
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm -e CAPSTONE_RELEASE_ID=$candidate devbox python -m scripts.capstone.bootstrap --root /workspace --stage rollback --rollback-target capstone-v1.0.0 --dry-run
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm -e CAPSTONE_RELEASE_ID=$candidate devbox python -m scripts.capstone.bootstrap --root /workspace --stage rollback --rollback-target capstone-v1.0.0
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox python -m scripts.capstone.verify_e2e --output assignments/final_capstone/reports/e2e_verification_local.json
```

预期：基线 `/health` 返回 `capstone-v1.0.0`，新增方案卡端点返回 `404 remediation_card_not_enabled_for_release`，原 E2E 仍为 `pass`。对照 [发布与回滚报告](../reports/release_and_rollback.md) 的已验证记录：候选 trace `b22c45f89f471846bbe4fe0b6b04f88a`，回滚后 E2E run `70eadfba6968`。
