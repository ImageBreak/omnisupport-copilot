from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "rag_api"))

from app.retrieval import _apply_metadata_filters  # noqa: E402


def test_workspace_retrieval_includes_cross_product_policy_documents():
    clauses: list[str] = []
    params: list[object] = []

    _apply_metadata_filters(clauses, params, product_line="northstar_workspace")

    assert params == ["northstar_workspace"]
    assert clauses == [
        "(kd.product_line = $1 OR kd.product_line = 'cross_product'::product_line)"
    ]
