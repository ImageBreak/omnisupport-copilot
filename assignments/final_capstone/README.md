# Final Capstone — Webhook Troubleshooting

本交付在现有 OmniSupport Copilot 上新增“问题处理方案卡”：针对 Webhook 的 401/404、签名密钥轮换与重试问题，基于 Hybrid RAG 的真实检索证据返回结构化诊断、步骤、引用、置信度和受控动作建议。全部文档、工单和账号均为合成数据。

## 一键启动

在仓库根目录执行。首次构建会下载镜像；后续运行不依赖个人 Python venv。

```powershell
Copy-Item infra/env/.env.example infra/env/.env.local
# 按下方“配置”修改 infra/env/.env.local 后：
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml up -d --build
docker compose --profile capstone --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm capstone_bootstrap
```

启动后可访问 Copilot：<http://localhost:8010>；Phoenix：<http://localhost:6006>。演示账号为 `agent@northstar.demo / Agent@2026`，管理员账号为 `admin@northstar.demo / Admin@2026`。

## 前置条件

- Docker Desktop / Docker Engine 24+，且 `docker compose` 可用。
- 16 GB 内存、25 GB 可用磁盘为课程最低建议；首次镜像构建需要网络。
- 不要求宿主机安装 Python、PostgreSQL、向量数据库或个人 venv。
- 可选：本机安装并运行 Ollama；没有模型时系统必须仍能以 deterministic fallback 完成契约与 E2E 验收。

## 配置

在 `infra/env/.env.local` 中设置候选发布和方案卡开关：

```dotenv
CAPSTONE_RELEASE_ID=capstone-v1.1.1
CAPSTONE_REMEDIATION_CARD_ENABLED=true
CAPSTONE_DATA_RELEASE_ID=data-capstone-v1
CAPSTONE_INDEX_RELEASE_ID=index-capstone-v1
CAPSTONE_PROMPT_RELEASE_ID=prompt-capstone-v1
```

本次留档验收使用现有 DeepSeek 配置；密钥仅存在于本地 `.env.local`，绝不提交。模型不可用、超时或返回非法 JSON 时，Query Rewrite 和生成流程会降级，不应返回 500：

```dotenv
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-v4-flash
QUERY_REWRITE_PROVIDER=deepseek
QUERY_REWRITE_MODEL=deepseek-v4-flash
```

若无 DeepSeek 配置，则保持 `LLM_PROVIDER=auto` 且不填密钥/模型；系统使用证据摘要与 deterministic embedding fallback。不得把真实客户文本、签名密钥、令牌或 PII 写入 `.env.local`、Golden Set 或 Trace。

## 验收命令

以下命令均在 Docker/Devbox 内运行。先完成“一键启动”。

```powershell
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox pytest tests/contract/test_webhook_remediation_card.py tests/contract/test_week15_capstone_product.py -q
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox pytest tests/integration/test_week15_capstone_security.py -q
docker compose --profile tools --env-file infra/env/.env.local -f infra/docker-compose.yml run --rm devbox python -m scripts.capstone.verify_e2e --output assignments/final_capstone/reports/e2e_verification_local.json
```

检索/评测、动作与版本证据可复核：

- [Golden Set（C1–C8）](evals/golden_set.jsonl)
- [评测报告](reports/eval_report.md)
- [方案卡动作验证](reports/remediation_card_actions_validation.md)
- [发布与回滚报告](reports/release_and_rollback.md)
- [回滚后 E2E 输出](reports/e2e_post_rollback.json)

## 预期输出

- 方案卡和产品契约：`19 passed`；安全回归：`3 passed`。
- E2E JSON 的 `status` 为 `pass`，并包含 RAG、低风险动作、HITL wait/resume、Phoenix trace。
- 方案卡响应符合 `contracts/webhook_remediation_card.schema.json`；引用只来自当前 tenant/release 的检索 evidence。无证据时给出澄清或拒答，不生成确定结论。
- 高风险 `grant_service_credit` 必须先进入 `awaiting_approval`；低风险 `add_internal_note` 需要显式确认且幂等重放不重复写入。

## 验收摘要

```text
baseline_commit: 87be56229a241f29eaf13ce6292d890fd6b36559
candidate_commit: 98c7f4f6c4519684b4d8e4be7475901cac3d610e
theme: webhook-troubleshooting
provider/model: deepseek / deepseek-v4-flash | deterministic fallback
release_id: capstone-v1.1.1
golden_set: C1..C8, 8 cases, 8 passed
hard_gates: G1..G6 pass
capstone_e2e: pass
representative_trace_id: b22c45f89f471846bbe4fe0b6b04f88a
known_limitations: synthetic eight-case gate only; no cross-machine p95 threshold; cross-product policy eligibility still needs manifest review
```

`capstone-v1.1.1` 曾激活并通过真实 API 验证；为证明 C8，环境最终被刻意回滚至 `capstone-v1.0.0`。候选 trace 为 `b22c45f89f471846bbe4fe0b6b04f88a`；回滚后的原 E2E run 为 `70eadfba6968`。

## 故障排查

| 现象 | 处理 |
|---|---|
| Docker 构建或拉取失败 | 检查 Docker Desktop 是否运行、网络/代理是否允许镜像拉取，再重复“一键启动”命令。不要改用个人 venv。 |
| `/health` 未就绪 | 用 `docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml ps` 检查 `postgres`、`rag_api`、`tool_api`、`copilot_api`；待依赖健康后重跑 bootstrap。 |
| 方案卡返回 404 `remediation_card_not_enabled_for_release` | 检查 `CAPSTONE_RELEASE_ID=capstone-v1.1.1` 和 `CAPSTONE_REMEDIATION_CARD_ENABLED=true`，随后重建 `copilot_api`。这是回滚后的预期行为。 |
| DeepSeek/Ollama 不可用或模型输出异常 | 检查 provider 的连接与模型配置；也可切回 `LLM_PROVIDER=auto`，验收仍应走 deterministic fallback 而非 500。 |
| 引用为空或卡片拒答 | 确认问题包含产品、HTTP 状态或版本/错误码；这是证据不足时的安全结果。可用 `EG-BOOT-004` 等精确标识验证 rewrite 保留。 |
| 发布指针或服务 release 不一致 | 先运行 `scripts.capstone.bootstrap --stage release --dry-run`，确认数据/索引/提示词/Skill/服务绑定，再重建三个 API 容器。回滚步骤和验证见 `reports/release_and_rollback.md`。 |
