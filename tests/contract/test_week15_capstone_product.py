from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from pipelines.ingestion.doc_ingest import raw_bucket_for
from scripts.capstone.generate_demo_data import generate_manifests, generate_tickets, resolve_as_of

pytest.importorskip("dagster")
from pipelines.definitions import defs  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def test_capstone_data_factory_emits_contract_valid_records(tmp_path):
    tickets_path = tmp_path / "tickets.jsonl"
    records = generate_tickets(
        count=24,
        output=tickets_path,
        seed=20260721,
        as_of=__import__("datetime").datetime(2026, 7, 21, tzinfo=__import__("datetime").timezone.utc),
    )
    ticket_schema = json.loads((ROOT / "contracts/data/ticket_contract.json").read_text())
    for record in records:
        jsonschema.Draft202012Validator(ticket_schema).validate(record)
        assert record["pii_redacted"] is True
        assert record["tenant_id"] == "northstar-demo"
        assert record["data_release_id"] == "data-capstone-v1"
        assert int(record["ticket_id"].rsplit("-", 1)[-1]) >= 900001
        assert "@" not in record["description"]
        created_at = __import__("datetime").datetime.fromisoformat(record["created_at"])
        updated_at = __import__("datetime").datetime.fromisoformat(record["updated_at"])
        assert updated_at >= created_at
        if record["resolved_at"]:
            assert __import__("datetime").datetime.fromisoformat(record["resolved_at"]) >= created_at

    manifest_schema = json.loads((ROOT / "data/seed_manifests/source_manifest_schema.json").read_text())
    manifests = generate_manifests(root=ROOT, output_dir=tmp_path / "manifests")
    assert len(manifests) == 4
    for path in manifests:
        jsonschema.Draft202012Validator(manifest_schema).validate(json.loads(path.read_text()))

    workspace_manifest = next(
        json.loads(path.read_text())
        for path in manifests
        if path.name == "manifest_northstar_workspace.json"
    )
    assert workspace_manifest["manifest_id"].endswith("-002")
    assert workspace_manifest["license_tag"] == "course_synthetic"
    webhook_assets = {
        asset["source_id"]: asset
        for asset in workspace_manifest["assets"]
        if "workspace-webhook-" in asset["source_id"]
    }
    assert set(webhook_assets) == {
        "doc:capstone:workspace-webhook-authentication",
        "doc:capstone:workspace-webhook-delivery-retry",
    }
    for asset in webhook_assets.values():
        assert asset["asset_type"] == "html"
        assert asset["metadata_status"] == "complete"
        assert asset["pii_scan_status"] == "clear"
        raw = Path(asset["source_url_or_path"]).read_bytes()
        assert asset["size_bytes"] == len(raw)
        assert asset["checksum_sha256"] == hashlib.sha256(raw).hexdigest()


def test_final_capstone_knowledge_package_is_contract_valid_and_fingerprint_pinned():
    manifest_path = ROOT / "assignments/final_capstone/data/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    schema = json.loads((ROOT / "data/seed_manifests/source_manifest_schema.json").read_text())

    jsonschema.Draft202012Validator(schema).validate(manifest)
    assert manifest["license_tag"] == "course_synthetic"
    assert manifest["product_line"] == "northstar_workspace"
    assert len(manifest["assets"]) == 2
    for asset in manifest["assets"]:
        assert asset["asset_type"] == "html"
        assert asset["metadata_status"] == "complete"
        assert asset["pii_scan_status"] == "clear"
        raw = (ROOT / asset["source_url_or_path"]).read_bytes()
        runtime_raw = (
            ROOT / "data/capstone/knowledge" / Path(asset["source_url_or_path"]).name
        ).read_bytes()
        assert raw == runtime_raw
        assert asset["size_bytes"] == len(raw)
        assert asset["checksum_sha256"] == hashlib.sha256(raw).hexdigest()


def test_final_capstone_remediation_contracts_and_golden_set_are_complete():
    contract_root = ROOT / "assignments/final_capstone/contracts"
    card_schema = json.loads((contract_root / "webhook_remediation_card.schema.json").read_text())
    action_schema = json.loads((contract_root / "webhook_remediation_action.schema.json").read_text())
    skill_contract = json.loads(
        (contract_root / "webhook_remediation_skill.contract.json").read_text()
    )
    jsonschema.Draft202012Validator.check_schema(card_schema)
    jsonschema.Draft202012Validator.check_schema(action_schema)
    validator = jsonschema.Draft202012Validator(card_schema)
    valid_card = {
        "summary": "The evidence supports checking signature validation before asserting a cause.",
        "steps": ["Check the delivery log."],
        "citations": [{"evidence_id": "evidence-1", "source": "doc:capstone:workspace-webhook-authentication", "section": "Evidence-supported sequence"}],
        "confidence": 0.8,
        "needs_clarification": False,
        "abstain_reason": None,
        "proposed_action": {"operation": "add_internal_note", "control": "confirm"},
        "release_id": "capstone-v1.0.0",
        "trace_id": "trace-contract-001",
    }
    validator.validate(valid_card)
    invalid_card = json.loads(json.dumps(valid_card))
    invalid_card["proposed_action"]["control"] = "none"
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid_card)

    assert skill_contract["output_schema_ref"] == "webhook_remediation_card.schema.json"
    assert skill_contract["governed_action_schema_ref"] == "webhook_remediation_action.schema.json"
    assert skill_contract["dependencies"]["governed_ticket_tool_contract"].endswith(
        "contracts/tools/tools/ticket_update.json"
    )
    action_controls = {
        item["operation"]: item["card_control"]
        for item in skill_contract["action_policy"]
    }
    assert action_controls == {
        "none": "none",
        "add_internal_note": "confirm",
        "grant_service_credit": "hitl",
    }
    assert skill_contract["evaluation_policy"]["high_risk_action_bypass_max"] == 0

    golden_path = ROOT / "assignments/final_capstone/evals/golden_set.jsonl"
    cases = [json.loads(line) for line in golden_path.read_text().splitlines() if line]
    assert [case["case_id"] for case in cases] == [
        "C1_normal_evidence_answer",
        "C2_identifier_preservation",
        "C3_ambiguous_clarification",
        "C4_insufficient_or_conflicting_evidence",
        "C5_low_risk_action_idempotency",
        "C6_high_risk_action_hitl",
        "C7_model_fault_fallback",
        "C8_regression_and_rollback",
    ]
    assert all(case["data_classification"] == "synthetic_only" for case in cases)
    assert all(case["expected_action_control"] in {"none", "confirm", "hitl"} for case in cases)
    assert cases[2]["needs_clarification"] is True
    assert cases[3]["expect_abstain"] is True
    assert cases[4]["expected_action_control"] == "confirm"
    assert cases[5]["expected_action_control"] == "hitl"
    assert cases[6]["expected_http_status"] == 200
    assert "release pointer" in cases[7]["required_release_artifacts"]

    source_ids = {
        f"doc:capstone:{path.stem}"
        for path in (ROOT / "data/capstone/knowledge").glob("*.html")
    }
    for case in cases:
        assert set(case["required_evidence"]).issubset(source_ids)


def test_capstone_data_factory_is_reproducible_across_reruns(tmp_path):
    first_path = tmp_path / "first.jsonl"
    second_path = tmp_path / "second.jsonl"
    as_of = resolve_as_of()
    generate_tickets(count=24, output=first_path, seed=20260721, as_of=as_of)
    generate_tickets(count=24, output=second_path, seed=20260721, as_of=as_of)

    assert as_of.isoformat() == "2026-07-21T00:00:00+00:00"
    assert first_path.read_bytes() == second_path.read_bytes()


def test_capstone_data_factory_honors_the_configured_data_release(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPSTONE_DATA_RELEASE_ID", "data-capstone-review-v2")
    records = generate_tickets(
        count=3,
        output=tmp_path / "configured-release.jsonl",
        seed=20260721,
        as_of=resolve_as_of(),
    )

    assert {record["data_release_id"] for record in records} == {"data-capstone-review-v2"}


def test_capstone_bootstrap_reconciles_operational_and_knowledge_snapshots():
    source = (ROOT / "scripts/capstone/bootstrap.py").read_text()

    assert "retired_stale_count" in source
    assert "reconcile_knowledge_snapshot" in source
    assert "retired_chunk_count" in source
    assert "CAPSTONE_STALE_DATA_RELEASE_ID" in source
    assert "load_capstone_graph_chunks" in source
    assert 'root / "data" / "capstone" / "graph_annotations_v1.json"' in source
    assert 'root / "data" / "week13"' not in source
    assert "already exists with a different manifest digest" in source

    annotations = json.loads((ROOT / "data/capstone/graph_annotations_v1.json").read_text())
    assert annotations["review_status"] == "approved"
    assert len(annotations["sources"]) == 10


def test_multimodal_raw_assets_are_routed_to_modality_buckets():
    assert raw_bucket_for("pdf") == "omni-raw-documents"
    assert raw_bucket_for("image") == "omni-raw-documents"
    assert raw_bucket_for("audio") == "omni-raw-audio"
    assert raw_bucket_for("video") == "omni-raw-video"


def test_capstone_product_contract_and_migration_cover_control_plane():
    schema = json.loads((ROOT / "contracts/product/copilot_message.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    migration = (ROOT / "infra/migrations/012_week15_capstone_product.sql").read_text()
    for table in (
        "app_user",
        "support_conversation",
        "support_message",
        "copilot_feedback",
        "financial_adjustment",
        "product_audit_event",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in migration
    assert "tenant_id" in migration
    llm_migration = (ROOT / "infra/migrations/015_week15_llm_runtime.sql").read_text()
    assert "generation_provider" in llm_migration
    assert "generation_model" in llm_migration


def test_compose_exposes_a_real_product_and_keeps_course_components_in_path():
    compose = yaml.safe_load((ROOT / "infra/docker-compose.yml").read_text())
    services = compose["services"]
    for service in (
        "postgres",
        "minio",
        "dagster",
        "rag_api",
        "tool_api",
        "copilot_api",
        "copilot_console",
        "otel_collector",
        "phoenix",
        "capstone_bootstrap",
    ):
        assert service in services
    assert services["copilot_console"]["depends_on"]["copilot_api"]["condition"] == "service_healthy"
    assert services["copilot_api"]["depends_on"]["rag_api"]["condition"] == "service_healthy"
    assert services["copilot_api"]["environment"]["DATA_RELEASE_ID"].startswith("${CAPSTONE_DATA_RELEASE_ID")
    assert services["copilot_api"]["environment"]["PROMPT_RELEASE_ID"].startswith(
        "${CAPSTONE_PROMPT_RELEASE_ID"
    )
    assert services["tool_api"]["environment"]["DATA_RELEASE_ID"].startswith(
        "${CAPSTONE_DATA_RELEASE_ID"
    )
    for key in (
        "CAPSTONE_RELEASE_ID",
        "CAPSTONE_DATA_RELEASE_ID",
        "CAPSTONE_INDEX_RELEASE_ID",
        "CAPSTONE_PROMPT_RELEASE_ID",
        "CAPSTONE_GRAPH_RELEASE_ID",
    ):
        assert key in services["capstone_bootstrap"]["environment"]
    migrate_command = services["db_migrate"]["command"][0]
    assert "--single-transaction" in migrate_command
    assert '-f "$$file"' in migrate_command
    assert '-c "INSERT INTO app_schema_migration' in migrate_command
    assert services["capstone_bootstrap"]["depends_on"]["minio_init"]["condition"] == "service_completed_successfully"
    assert services["rag_api"]["environment"]["REQUIRE_INTERNAL_AUTH"].startswith(
        "${REQUIRE_INTERNAL_AUTH"
    )
    for key in ("LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL"):
        assert key in services["rag_api"]["environment"]
    assert services["tool_api"]["environment"]["REQUIRE_INTERNAL_AUTH"].startswith(
        "${REQUIRE_INTERNAL_AUTH"
    )


def test_capstone_analytics_preserves_tenant_and_source_release_boundaries():
    model_paths = (
        ROOT / "analytics/models/staging/stg_tickets.sql",
        ROOT / "analytics/models/intermediate/int_support_cases.sql",
        ROOT / "analytics/models/intermediate/int_ticket_activity_daily.sql",
        ROOT / "analytics/models/marts/support_kpi_mart.sql",
        ROOT / "analytics/models/marts/agent_tool_input_view.sql",
    )
    for path in model_paths:
        source = path.read_text()
        assert "tenant_id" in source, path
        assert "data_release_id" in source, path

    kpi_model = model_paths[-2].read_text()
    assert "coalesce(data_release_id" in kpi_model
    assert "'{{ var(\"week05_data_release_id\") }}' as data_release_id" not in kpi_model


def test_dagster_registers_the_real_capstone_asset_chain():
    asset_keys = {"/".join(key.path) for key in defs.resolve_all_asset_keys()}
    assert {
        "capstone_source_pack",
        "capstone_operational_data",
        "capstone_knowledge_index",
        "capstone_analytics_marts",
        "capstone_graph_projection",
        "capstone_product_release",
    }.issubset(asset_keys)


def test_ticket_tools_no_longer_return_week01_stub_payloads():
    source = (ROOT / "services/tool_api/app/routers/tickets.py").read_text()
    assert '"_stub"' not in source
    assert "INSERT INTO hitl_approval_request" in source
    assert "INSERT INTO agent_action_lineage" in source
    assert "INSERT INTO financial_adjustment" in source
    assert "settings.data_release_id" in source

    product_source = (ROOT / "services/copilot_api/app/main.py").read_text()
    assert '"prompt_release_id": settings.prompt_release_id' in product_source


def test_capstone_runtime_hardening_is_tenant_scoped_and_evidence_gated():
    migration = (ROOT / "infra/migrations/014_week15_runtime_hardening.sql").read_text()
    ticket_contract = json.loads(
        (ROOT / "contracts/tools/tools/ticket_update.json").read_text()
    )
    schema = ticket_contract["input_schema"]
    financial = {
        "ticket_id": "TKT-20260721-900001",
        "operation": "grant_service_credit",
        "reason": "Verified service impact for the active support case",
        "actor_role": "support_agent",
        "risk_level": "financial",
        "amount_cents": 2500,
        "idempotency_key": "week15-financial-001",
        "trace_id": "trace-week15-financial-001",
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(financial)
    financial["evidence_ids"] = ["evidence-capstone-001"]
    jsonschema.Draft202012Validator(schema).validate(financial)

    assert "PRIMARY KEY (tenant_id, tool_name, idempotency_key)" in migration
    assert "ADD COLUMN IF NOT EXISTS tenant_id" in migration
    assert "CHECK (amount_cents > 0)" in migration
    assert "idx_app_user_login_email" in migration


def test_week_runbooks_include_internal_identity_for_direct_business_calls():
    for path in (
        ROOT / "runbooks/week05/README.md",
        ROOT / "runbooks/week08-rag-engineering.md",
        ROOT / "runbooks/week13-graphrag.md",
        ROOT / "runbooks/podman-local.md",
    ):
        source = path.read_text()
        assert "X-Service-Token" in source, path
        assert "X-Actor-Role" in source, path
        assert "X-Tenant-ID" in source, path
