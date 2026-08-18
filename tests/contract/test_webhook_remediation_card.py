from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "copilot_api"))

from app.remediation import (  # noqa: E402
    AUTH_SOURCE,
    CREDIT_SOURCE,
    DELIVERY_SOURCE,
    build_remediation_card,
)
from app.models import RemediationActionCreate  # noqa: E402
from pipelines.query.rewriter import rewrite_query  # noqa: E402


def _rag_answer(*, citations: list[dict], abstain_reason: str | None = None) -> dict:
    return {
        "citations": citations,
        "abstain_reason": abstain_reason,
        "release_id": "capstone-v1.0.0",
        "trace_id": "trace-remediation-card-001",
    }


def test_remediation_card_matches_frozen_schema_and_reuses_rag_citations():
    schema = json.loads(
        (ROOT / "assignments/final_capstone/contracts/webhook_remediation_card.schema.json").read_text()
    )
    rag_answer = _rag_answer(
        citations=[
            {"evidence_id": "anchor-auth-001", "source_id": AUTH_SOURCE, "section_path": "Evidence-supported sequence"},
            {"evidence_id": "anchor-unrelated-001", "source_id": "doc:capstone:workspace-admin-recovery", "section_path": "Admin recovery"},
        ]
    )
    card = build_remediation_card(
        question="Webhook version 3.2 returned HTTP 401 after signing-secret rotation.",
        rag_answer=rag_answer,
    )

    jsonschema.Draft202012Validator(schema).validate(card)
    assert card["citations"] == [{"evidence_id": "anchor-auth-001", "source": AUTH_SOURCE, "section": "Evidence-supported sequence"}]
    assert len(card["steps"]) == 3
    assert card["abstain_reason"] is None
    assert card["proposed_action"] == {"operation": "none", "control": "none"}

    missing_trace = dict(card)
    missing_trace.pop("trace_id")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(missing_trace)


def test_remediation_card_clarifies_or_abstains_without_inventing_evidence():
    clarifying = build_remediation_card(
        question="The webhook is not working after signing-secret rotation.",
        rag_answer=_rag_answer(citations=[{"evidence_id": "anchor-auth-002", "source_id": AUTH_SOURCE, "section_path": "Required facts before diagnosis"}]),
    )
    assert clarifying["needs_clarification"] is True
    assert clarifying["abstain_reason"] == "missing_required_context:http_status,webhook_version"
    assert clarifying["confidence"] == 0.45

    abstained = build_remediation_card(
        question="Webhook version 3.2 returned HTTP 404 after retry.",
        rag_answer=_rag_answer(
            citations=[{"evidence_id": "anchor-unrelated-002", "source_id": AUTH_SOURCE, "section_path": "Authentication"}]
        ),
    )
    assert abstained["citations"] == []
    assert abstained["confidence"] == 0.0
    assert abstained["abstain_reason"] == "no_topic_matched_retrieval_evidence"

    unsupported = build_remediation_card(
        question="What universal retry schedule does every third-party vendor use for webhook version 3.2?",
        rag_answer=_rag_answer(citations=[{"evidence_id": "anchor-delivery-unsupported", "source_id": DELIVERY_SOURCE, "section_path": "Retry"}]),
    )
    assert unsupported["citations"] == []
    assert unsupported["abstain_reason"] == "unsupported_request_requires_external_vendor_evidence"

    grounded_404 = build_remediation_card(
        question="Webhook version 3.2 returned HTTP 404 after retry.",
        rag_answer=_rag_answer(citations=[{"evidence_id": "anchor-delivery-001", "source_id": DELIVERY_SOURCE, "section_path": "HTTP 404 sequence"}]),
    )
    assert grounded_404["citations"] == [
        {"evidence_id": "anchor-delivery-001", "source": DELIVERY_SOURCE, "section": "HTTP 404 sequence"}
    ]

    year_month_version = build_remediation_card(
        question="Webhook version 2026-07 returned HTTP 401 after signing-secret rotation.",
        rag_answer=_rag_answer(
            citations=[
                {"evidence_id": "anchor-auth-003", "source_id": AUTH_SOURCE, "section_path": "Authentication sequence"}
            ]
        ),
    )
    assert year_month_version["needs_clarification"] is False


def test_query_rewrite_preserves_exact_error_code_and_model_identifier():
    plan = rewrite_query("How do I recover EG-3000 after EG-BOOT-004 on version 3.9?")

    assert "EG-3000" in plan.semantic_query
    assert "EG-BOOT-004" in plan.semantic_query
    assert "3.9" in plan.semantic_query
    assert "EG-3000" in plan.lexical_terms
    assert "EG-BOOT-004" in plan.lexical_terms


def test_remediation_card_only_proposes_governed_existing_operations():
    evidence = [{"evidence_id": "anchor-auth-action", "source_id": AUTH_SOURCE, "section_path": "Action evidence"}]
    note = build_remediation_card(
        question="Webhook version 3.2 returned HTTP 401; add an internal note after diagnosis.",
        rag_answer=_rag_answer(citations=evidence),
    )
    credit = build_remediation_card(
        question="Webhook version 3.2 returned HTTP 401; request service credit compensation.",
        rag_answer=_rag_answer(
            citations=[{"evidence_id": "anchor-credit-proposal", "source_id": CREDIT_SOURCE, "section_path": "Approval policy"}]
        ),
    )

    assert note["proposed_action"] == {"operation": "add_internal_note", "control": "confirm"}
    assert credit["proposed_action"] == {"operation": "grant_service_credit", "control": "hitl"}

    policy_grounded_credit = build_remediation_card(
        question="The customer had verified impact. Propose a USD 25 service credit.",
        rag_answer=_rag_answer(
            citations=[{"evidence_id": "anchor-credit-001", "source_id": CREDIT_SOURCE, "section_path": "Approval policy"}]
        ),
    )
    assert policy_grounded_credit["needs_clarification"] is False
    assert policy_grounded_credit["abstain_reason"] is None
    assert policy_grounded_credit["proposed_action"] == {"operation": "grant_service_credit", "control": "hitl"}


def test_remediation_action_request_requires_confirmation_and_financial_amount():
    schema = json.loads(
        (ROOT / "assignments/final_capstone/contracts/webhook_remediation_action.schema.json").read_text()
    )
    request_schema = schema["$defs"]["request"]
    valid_note = {
        "card_trace_id": "trace-card-001",
        "operation": "add_internal_note",
        "confirmed": True,
        "reason": "Record the evidence-backed webhook investigation.",
        "evidence_ids": ["anchor-auth-action"],
        "idempotency_key": "remediation-note-001",
    }
    jsonschema.Draft202012Validator(request_schema).validate(valid_note)
    assert RemediationActionCreate.model_validate(valid_note).confirmed is True

    unconfirmed = dict(valid_note, confirmed=False)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(request_schema).validate(unconfirmed)

    credit_without_amount = dict(valid_note, operation="grant_service_credit")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(request_schema).validate(credit_without_amount)

