from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=256)


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=180)


class MessageCreate(BaseModel):
    question: str = Field(min_length=2, max_length=2048)
    retrieval_mode: Literal[
        "hybrid", "auto", "graph_local", "graph_global", "graph_multihop", "graph_drift"
    ] = "auto"
    include_debug: bool = False


class RemediationCardCreate(BaseModel):
    question: str = Field(min_length=2, max_length=2048)


class RemediationCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    section: str = Field(min_length=1)


class ProposedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["none", "add_internal_note", "grant_service_credit"]
    control: Literal["none", "confirm", "hitl"]


class RemediationCardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=500)
    steps: list[str] = Field(default_factory=list, max_length=3)
    citations: list[RemediationCitation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    needs_clarification: bool
    abstain_reason: str | None = Field(default=None, max_length=500)
    proposed_action: ProposedAction
    release_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)


class RemediationActionCreate(BaseModel):
    """A human-confirmed request to execute the card's already-governed proposal."""

    model_config = ConfigDict(extra="forbid")

    card_trace_id: str = Field(min_length=1, max_length=160)
    operation: Literal["add_internal_note", "grant_service_credit"]
    confirmed: bool
    reason: str = Field(min_length=8, max_length=2048)
    evidence_ids: list[str] = Field(min_length=1, max_length=5)
    idempotency_key: str = Field(min_length=8, max_length=160)
    amount_cents: int | None = Field(default=None, gt=0)
    currency: Literal["USD", "CNY"] = "USD"


class FeedbackCreate(BaseModel):
    rating: Literal[-1, 1]
    reason_code: str | None = Field(default=None, max_length=80)
    comment: str | None = Field(default=None, max_length=1000)


class TicketActionCreate(BaseModel):
    operation: Literal[
        "add_internal_note",
        "update_status",
        "change_priority",
        "assign_agent",
        "grant_service_credit",
        "refund_payment",
    ]
    reason: str = Field(min_length=8, max_length=2048)
    new_status: str | None = None
    new_priority: str | None = None
    assignee_id: str | None = None
    amount_cents: int | None = Field(default=None, gt=0)
    currency: Literal["USD", "CNY"] = "USD"
    evidence_ids: list[str] = Field(default_factory=list)
    idempotency_key: str = Field(min_length=8, max_length=160)


class ApprovalDecision(BaseModel):
    approved: bool
    reason: str = Field(min_length=5, max_length=1000)


class KpiQuery(BaseModel):
    metrics: list[str] = Field(min_length=1, max_length=8)
    dimensions: list[str] = Field(default_factory=list, max_length=4)
    filters: dict[str, object] = Field(default_factory=dict)
    date_from: str
    date_to: str
    include_experimental_metrics: bool = False
    limit: int = Field(default=100, ge=1, le=500)
