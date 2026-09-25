"""
Comprehensive Tests for MRPL Generic Knowledge Base Integration & Position-Based RAG Filtering.
"""

import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from config.settings import settings
from src.api.app import app
from src.auth.models import User, UserRole
from src.rag.ingest_mrpl import MRPLKnowledgeBaseIngester, CANONICAL_JSONL_PATH
from src.rag.rag_service import RAGService


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def ingester():
    ing = MRPLKnowledgeBaseIngester()
    ing.ingest(force=True)
    return ing


def test_01_canonical_dataset_loading_and_validation():
    """Verify canonical JSONL dataset exists, validates, and has 15 records with preserved metadata."""
    assert CANONICAL_JSONL_PATH.exists(), f"Canonical JSONL dataset file missing at {CANONICAL_JSONL_PATH}"

    ingester = MRPLKnowledgeBaseIngester()
    records = ingester.load_and_validate_jsonl()

    assert len(records) == 15
    for rec in records:
        assert "id" in rec
        assert "department" in rec
        assert "position" in rec
        assert "topic" in rec
        assert "document_type" in rec
        assert "content" in rec
        assert len(rec["content"].strip()) > 10


def test_02_ingestion_and_metadata_preservation(ingester):
    """Verify records are ingested into ChromaDB with all metadata fields preserved."""
    vector_store = ingester.vector_store
    assert vector_store.count() >= 15

    # Inspect record MRPL-GEN-001
    item = vector_store.get_by_id("MRPL-GEN-001-chunk-000")
    assert item is not None
    meta = item.get("metadata", {})

    assert meta.get("document_id") == "MRPL-GEN-001"
    assert meta.get("department") == "Reliability / Maintenance"
    assert meta.get("position") == "Reliability Engineer"
    assert meta.get("topic") == "Pump vibration investigation"
    assert meta.get("document_type") == "Engineering Knowledge"
    assert "centrifugal pump" in item.get("document", "")


def test_03_duplicate_prevention(ingester):
    """Verify re-running ingestion does not duplicate chunks or corrupt vector store."""
    count_before = ingester.vector_store.count()
    res = ingester.ingest(force=False)

    assert res["status"] == "up_to_date"
    assert res["indexed_chunks"] == 0
    assert res["skipped_chunks"] == 15
    assert ingester.vector_store.count() == count_before


def test_04_position_based_rbac_filtering(ingester):
    """
    Verify pre-retrieval position-based authorization filtering:
    - Reliability Engineer retrieves reliability records.
    - Process Engineer retrieves process engineering records.
    - HSE Engineer retrieves safety records.
    - Console Operator retrieves operations records.
    - Process Engineer CANNOT retrieve protected Reliability Engineer records.
    """
    rag_service = RAGService(vector_store=ingester.vector_store, embedding_provider=ingester.embedding_provider)

    # 1. Reliability Engineer
    rel_user = User(
        user_id="u_rel",
        full_name="Reliability Eng",
        email="reliability_engineer@mrpl.local",
        role=UserRole.ENGINEER,
        department="Reliability / Maintenance",
        position="Reliability Engineer",
        clearance_level=3,
    )
    rel_chunks = rag_service.retriever.retrieve(query="pump vibration investigation", user=rel_user, top_k=5)
    rel_doc_ids = [c.get("document_id") for c in rel_chunks]
    assert "MRPL-GEN-001" in rel_doc_ids

    # 2. Process Engineer
    proc_user = User(
        user_id="u_proc",
        full_name="Process Eng",
        email="process_engineer@mrpl.local",
        role=UserRole.ENGINEER,
        department="Process Engineering",
        position="Process Engineer",
        clearance_level=3,
    )
    proc_chunks = rag_service.retriever.retrieve(query="process troubleshooting operating envelopes", user=proc_user, top_k=5)
    proc_doc_ids = [c.get("document_id") for c in proc_chunks]
    assert "MRPL-GEN-005" in proc_doc_ids

    # 3. HSE Engineer
    hse_user = User(
        user_id="u_hse",
        full_name="HSE Eng",
        email="hse_engineer@mrpl.local",
        role=UserRole.ENGINEER,
        department="HSE",
        position="HSE Engineer",
        clearance_level=3,
    )
    hse_chunks = rag_service.retriever.retrieve(query="process safety lockout tagout gas testing", user=hse_user, top_k=5)
    hse_doc_ids = [c.get("document_id") for c in hse_chunks]
    assert "MRPL-GEN-007" in hse_doc_ids

    # 4. Console Operator
    op_user = User(
        user_id="u_op",
        full_name="Console Operator",
        email="operator@mrpl.local",
        role=UserRole.PLANT_OPERATOR,
        department="Operations",
        position="Console Operator",
        clearance_level=1,
    )
    op_chunks = rag_service.retriever.retrieve(query="process alarm operating procedure", user=op_user, top_k=5)
    op_doc_ids = [c.get("document_id") for c in op_chunks]
    assert "MRPL-GEN-006" in op_doc_ids

    # 5. Unauthorized Access Prevention: Process Engineer searching specifically for pump vibration failure investigation
    proc_vibr_chunks = rag_service.retriever.retrieve(query="pump vibration investigation imbalance misalignment", user=proc_user, top_k=5)
    proc_vibr_ids = [c.get("document_id") for c in proc_vibr_chunks]
    assert "MRPL-GEN-001" not in proc_vibr_ids, "Security Violation: Process Engineer retrieved protected Reliability Engineer document MRPL-GEN-001!"


def test_05_knowledge_base_health_endpoint(client):
    """Verify GET /knowledge-base endpoint returns dataset readiness status."""
    res = client.get("/knowledge-base")
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["status"] == "ready"
    assert data["dataset"] == "MRPL Generic Knowledge Base"
    assert data["records"] == 15
    assert data["vector_store"] == "ready"
    assert "embedding_model" in data


def test_06_rag_grounded_pump_vibration_query(ingester):
    """
    RAG Test: 'What are possible causes of abnormal pump vibration?'
    Verifies retrieval of MRPL-GEN-001 and evidence-based answer structure.
    """
    import asyncio
    rag_service = RAGService(vector_store=ingester.vector_store, embedding_provider=ingester.embedding_provider)
    rel_user = User(
        user_id="u_rel",
        full_name="Reliability Eng",
        email="reliability_engineer@mrpl.local",
        role=UserRole.ENGINEER,
        department="Reliability / Maintenance",
        position="Reliability Engineer",
        clearance_level=3,
    )

    response = asyncio.run(rag_service.query(query="What are possible causes of abnormal pump vibration?", user=rel_user))
    assert response.status == "SUCCESS"
    assert len(response.sources) > 0

    answer = response.answer.lower()
    # Verify core causes mentioned in dataset MRPL-GEN-001
    assert any(term in answer for term in ["imbalance", "misalignment", "bearing", "cavitation", "looseness", "vibration"])
    assert "MRPL-GEN-001" in [s.filename for s in response.sources] or "mrpl_generic_knowledge_base.jsonl" in [s.filename for s in response.sources]
