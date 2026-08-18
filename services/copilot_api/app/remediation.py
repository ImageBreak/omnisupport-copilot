"""Deterministic, evidence-gated builder for the webhook remediation card.

The RAG service owns query rewrite and hybrid retrieval.  This module deliberately
does not generate citations or execute tools: it reduces the RAG response to the
published card contract and refuses to make a diagnosis without topic-matched
retrieval evidence.
"""

from __future__ import annotations

import re
from typing import Any


AUTH_SOURCE = "doc:capstone:workspace-webhook-authentication"
DELIVERY_SOURCE = "doc:capstone:workspace-webhook-delivery-retry"
BASE_SOURCE = "doc:capstone:workspace-api-webhook"
CREDIT_SOURCE = "doc:capstone:support-credit-policy"

HTTP_STATUS_RE = re.compile(r"\b(?:http\s*)?[1-5]\d{2}\b", re.IGNORECASE)
VERSION_RE = re.compile(
    r"\b(?:v(?:ersion)?\s*)?(?:\d+\.\d+(?:\.\d+)?|\d{4}-\d{2})\b",
    re.IGNORECASE,
)
UNSUPPORTED_REQUEST_MARKERS = (
    "every third-party",
    "universal retry",
    "vendor retry schedule",
)
FINANCIAL_ACTION_MARKERS = ("service credit", "credit", "compensation", "refund")
NOTE_ACTION_MARKERS = ("internal note", "add a note", "add note", "record a note")


def _expected_sources(question: str) -> set[str]:
    lowered = question.casefold()
    if any(marker in lowered for marker in FINANCIAL_ACTION_MARKERS):
        return {CREDIT_SOURCE}
    if "401" in lowered or "signing" in lowered or "signature" in lowered:
        return {AUTH_SOURCE}
    if any(term in lowered for term in ("404", "retry", "duplicate", "replay", "endpoint")):
        return {DELIVERY_SOURCE}
    return {AUTH_SOURCE, DELIVERY_SOURCE, BASE_SOURCE}


def _matching_citations(question: str, rag_answer: dict[str, Any]) -> list[dict[str, str]]:
    expected = _expected_sources(question)
    matches: list[dict[str, str]] = []
    seen: set[str] = set()
    for citation in rag_answer.get("citations") or []:
        evidence_id = citation.get("evidence_id")
        source = citation.get("source_id") or citation.get("source")
        section = citation.get("section_path") or citation.get("chunk_id")
        if not all(isinstance(value, str) and value for value in (evidence_id, source, section)):
            continue
        if source not in expected or evidence_id in seen:
            continue
        matches.append({"evidence_id": evidence_id, "source": source, "section": section})
        seen.add(evidence_id)
    return matches


def _missing_context(question: str) -> list[str]:
    if not HTTP_STATUS_RE.search(question):
        # Without a status, a version alone does not identify a safe diagnostic
        # branch. Ask for both facts; with a concrete status, the card may give
        # a non-causal checklist while retaining the version as a checklist step.
        return ["http_status", "webhook_version"]
    return []


def _steps_for(question: str) -> tuple[str, list[str]]:
    lowered = question.casefold()
    if "401" in lowered or "signing" in lowered or "signature" in lowered:
        return (
            "Retrieved evidence supports verifying signature validation and rotation configuration; it does not establish a root cause.",
            [
                "Confirm the delivery log status and retain the request identifier.",
                "Verify the consumer validates the exact webhook version delivered.",
                "Verify the approved current-and-next signing-secret rotation window before one replay.",
            ],
        )
    if any(term in lowered for term in ("404", "retry", "duplicate", "replay", "endpoint")):
        return (
            "Retrieved evidence supports checking the endpoint route and delivery semantics; it does not establish a root cause.",
            [
                "Confirm the exact HTTP status, webhook version, endpoint path, and event identifier.",
                "Verify the public HTTPS route, subscribed event name, and organization scope.",
                "After correction, replay one event and confirm the consumer deduplicates by event identifier.",
            ],
        )
    return (
        "Retrieved evidence supports a webhook delivery investigation; it does not establish a root cause.",
        [
            "Check the delivery log for status, webhook version, event identifier, and request identifier.",
            "Verify the endpoint and subscription configuration against the delivered version.",
            "Replay only one verified delivery and confirm one business event.",
        ],
    )


def _base_response(question: str, rag_answer: dict[str, Any]) -> dict[str, Any]:
    return {
        "release_id": str(rag_answer.get("release_id") or "unknown-release"),
        "trace_id": str(rag_answer.get("trace_id") or "unknown-trace"),
        "proposed_action": _proposed_action(question),
    }


def _proposed_action(question: str) -> dict[str, str]:
    """Suggest only existing governed operations; this never executes a tool."""

    lowered = question.casefold()
    if any(marker in lowered for marker in FINANCIAL_ACTION_MARKERS):
        return {"operation": "grant_service_credit", "control": "hitl"}
    if any(marker in lowered for marker in NOTE_ACTION_MARKERS):
        return {"operation": "add_internal_note", "control": "confirm"}
    return {"operation": "none", "control": "none"}


def build_remediation_card(*, question: str, rag_answer: dict[str, Any]) -> dict[str, Any]:
    """Return a strict card response using only citations supplied by RAG."""

    response = _base_response(question, rag_answer)
    if any(marker in question.casefold() for marker in UNSUPPORTED_REQUEST_MARKERS):
        response.update(
            {
                "summary": "No evidence-grounded webhook remediation diagnosis is available for this request.",
                "steps": [],
                "citations": [],
                "confidence": 0.0,
                "needs_clarification": False,
                "abstain_reason": "unsupported_request_requires_external_vendor_evidence",
                "proposed_action": {"operation": "none", "control": "none"},
            }
        )
        return response

    citations = _matching_citations(question, rag_answer)
    retrieval_abstain = rag_answer.get("abstain_reason")
    if retrieval_abstain or not citations:
        response.update(
            {
                "summary": "No evidence-grounded webhook remediation diagnosis is available for this request.",
                "steps": [],
                "citations": [],
                "confidence": 0.0,
                "needs_clarification": False,
                "abstain_reason": str(retrieval_abstain or "no_topic_matched_retrieval_evidence"),
                "proposed_action": {"operation": "none", "control": "none"},
            }
        )
        return response

    if response["proposed_action"]["operation"] == "grant_service_credit":
        response.update(
            {
                "summary": "Retrieved policy evidence supports submitting a governed service-credit request; it does not establish a remedy or credit outcome.",
                "steps": [
                    "Verify the documented customer impact and the requested amount.",
                    "Submit the bounded request with the cited policy evidence.",
                    "Wait for an authorized human approval before communicating an outcome.",
                ],
                "citations": citations,
                "confidence": min(0.8, 0.7 + (0.1 * min(len(citations), 1))),
                "needs_clarification": False,
                "abstain_reason": None,
            }
        )
        return response

    missing = _missing_context(question)
    if missing:
        response.update(
            {
                "summary": "More delivery context is required before making a webhook diagnosis.",
                "steps": ["Provide the exact HTTP status and webhook version from the delivery log."],
                "citations": citations,
                "confidence": 0.45,
                "needs_clarification": True,
                "abstain_reason": f"missing_required_context:{','.join(missing)}",
            }
        )
        return response

    summary, steps = _steps_for(question)
    response.update(
        {
            "summary": summary,
            "steps": steps,
            "citations": citations,
            "confidence": min(0.9, 0.7 + (0.1 * min(len(citations), 2))),
            "needs_clarification": False,
            "abstain_reason": None,
            "proposed_action": _proposed_action(question),
        }
    )
    return response
