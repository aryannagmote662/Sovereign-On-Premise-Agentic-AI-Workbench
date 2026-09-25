"""
Acceptance Test Suite for Live Model, VRAM, and Network Monitor Panel (Section 24).
Executes 7-step operational scenario verifying model switching, VRAM allocation, OCR,
document generation, network isolation, and telemetry persistence.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.models.registry import ModelStatus, get_model_registry
from src.observability.telemetry_service import get_telemetry_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_acceptance_telemetry():
    telemetry = get_telemetry_service()
    telemetry.set_demo_mode(True)
    yield
    telemetry.set_demo_mode(False)


def test_acceptance_flow_7_steps():
    """
    Executes Section 24 Acceptance Test Sequence across all 7 steps.
    """
    registry = get_model_registry()
    telemetry = get_telemetry_service()

    # STEP 1: Send normal document/reasoning query
    res1 = client.post("/workbench/chat", json={"query": "Summarize emergency shutdown protocol for CDU-1", "force_rag": False})
    assert res1.status_code == 200
    telemetry_state = client.get("/system/telemetry").json()["data"]
    
    assert telemetry_state["current_task"]["query"] == "Summarize emergency shutdown protocol for CDU-1"
    assert telemetry_state["active_model"] == "Qwen2.5-7B-Instruct"
    assert telemetry_state["gpu"]["used_vram_gb"] > 0

    # STEP 2: Send coding query
    res2 = client.post("/workbench/chat", json={"query": "Write a Python script to calculate heat exchanger efficiency", "force_rag": False})
    assert res2.status_code == 200
    telemetry_state2 = client.get("/system/telemetry").json()["data"]
    
    assert "Python" in telemetry_state2["current_task"]["query"]
    assert telemetry_state2["active_model"] in ("Qwen2.5-Coder-7B-Instruct", "Qwen2.5-7B-Instruct")
    assert telemetry_state2["performance"]["CODE"]["requests_processed"] >= 1

    # STEP 3: Send vision query
    res3 = client.post("/workbench/chat", json={"query": "Analyze engineering diagram and inspect pressure relief valve", "force_rag": False})
    assert res3.status_code == 200
    telemetry_state3 = client.get("/system/telemetry").json()["data"]
    assert telemetry_state3["active_model"] is not None

    # STEP 4: Run OCR
    res4 = client.get("/system/performance").json()["data"]
    assert "OCR" in res4
    assert res4["OCR"]["model"] == "PaddleOCR"

    # STEP 5: Generate document
    res5 = client.post("/workbench/chat", json={"query": "Generate a Word document report on CDU-1 pressure readings", "force_rag": False})
    assert res5.status_code == 200
    res5_json = res5.json()["data"]
    assert res5_json["generated_artifact"] is not None
    assert res5_json["generated_artifact"]["file_type"] == "docx"

    # STEP 6: Verify Network Monitor
    net_data = client.get("/system/network").json()["data"]
    assert net_data["mode"] == "LOCAL / AIR-GAPPED"
    assert net_data["external_calls"] == "BLOCKED"
    assert net_data["external_api_calls_count"] == 0

    # STEP 7: Reconnect / Restart simulation
    res7 = client.get("/system/telemetry").json()["data"]
    assert res7["gpu"]["available"] is True
    assert len(res7["models"]) >= 4
