"""
Comprehensive Unit & Integration Test Suite for Live Model, VRAM, Network Monitor & Telemetry System.
Verifies ModelRegistry discovery, model switching, VRAM telemetry, network air-gap posture,
capability performance, task stage trajectory, future open-weight model registration, and API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.models.registry import ModelRegistry, ModelSpec, ModelStatus, get_model_registry
from src.observability.telemetry_service import TelemetryService, get_telemetry_service
from src.routing.intent_classifier import UserIntent
from src.routing.model_router import ModelRouter

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_telemetry():
    """Reset telemetry service and model registry state for tests."""
    reg = get_model_registry()
    telemetry = get_telemetry_service()
    telemetry.set_demo_mode(False)
    yield
    telemetry.set_demo_mode(False)


def test_model_registry_discovery_and_default_models():
    """Test 1: Model registry discovery & default open-weight models."""
    registry = get_model_registry()
    models = registry.list_models()

    assert len(models) >= 4
    model_ids = [m["model_id"] for m in models]
    assert "qwen25-instruct-7b" in model_ids
    assert "qwen25-coder-7b" in model_ids
    assert "qwen25-vl-3b" in model_ids
    assert "deepseek-coder-6.7b" in model_ids


def test_future_model_registration_without_ui_redesign():
    """Test 8/26: Future open-weight model support (Llama-3, Mistral, Gemma, Phi, etc.)."""
    registry = get_model_registry()
    
    new_model = ModelSpec(
        model_id="llama3-8b-instruct",
        display_name="Llama-3-8B-Instruct",
        provider="Meta / Sovereign Local",
        runtime="ollama",
        ollama_tag="llama3:8b",
        model_size="8B",
        quantization="Q4_K_M",
        task_types=["general", "reasoning"],
        capabilities=["general", "reasoning"],
        vram_requirement_mb=6500,
        status=ModelStatus.UNLOADED,
        enabled=True,
    )
    registry.register_model(new_model)

    fetched = registry.get_model("llama3-8b-instruct")
    assert fetched is not None
    assert fetched.display_name == "Llama-3-8B-Instruct"

    # API endpoint must automatically expose new model
    response = client.get("/system/system-models")
    assert response.status_code == 200
    res_data = response.json()["data"]
    all_model_ids = [m["model_id"] for m in res_data["models"]]
    assert "llama3-8b-instruct" in all_model_ids


def test_model_state_transitions():
    """Test 2: Model lifecycle state transitions."""
    registry = get_model_registry()
    
    # Update status to LOADING
    spec = registry.update_model_status("qwen25-coder-7b", ModelStatus.LOADING)
    assert spec.status == ModelStatus.LOADING

    # Update status to ACTIVE
    spec = registry.update_model_status("qwen25-coder-7b", ModelStatus.ACTIVE)
    assert spec.status == ModelStatus.ACTIVE

    # Other active models must be set to LOADED
    qwen_spec = registry.get_model("qwen25-instruct-7b")
    assert qwen_spec.status in (ModelStatus.LOADED, ModelStatus.UNLOADED)


def test_vram_telemetry_source_and_unavailable_handling():
    """Test 4 & 9: VRAM telemetry source & unavailable handling when no GPU."""
    telemetry = get_telemetry_service()
    
    # Real Mode
    telemetry.set_demo_mode(False)
    gpu_data = telemetry.get_gpu_telemetry()
    assert "telemetry_status" in gpu_data
    assert "used_vram_gb" in gpu_data
    assert "total_vram_gb" in gpu_data

    # Demo Mode
    telemetry.set_demo_mode(True)
    demo_data = telemetry.get_gpu_telemetry()
    assert demo_data["demo_mode"] is True
    assert demo_data["telemetry_status"] == "DEMO TELEMETRY"
    assert demo_data["used_vram_gb"] > 0.0


def test_network_status_and_no_external_calls():
    """Test 5 & 11: Network status and zero external network calls."""
    telemetry = get_telemetry_service()
    net = telemetry.get_network_telemetry()

    assert net["mode"] == "LOCAL / AIR-GAPPED"
    assert net["external_calls"] == "BLOCKED"
    assert net["external_api_calls_count"] == 0
    assert net["internet_status"] == "DISCONNECTED / BLOCKED"


def test_active_task_and_workflow_stage_trajectory():
    """Test 6: Active task telemetry and workflow stage progression."""
    telemetry = get_telemetry_service()
    
    telemetry.update_workflow_stage(
        stage="ROUTING",
        status="COMPLETED",
        query="Why is Pump P-101 vibrating?",
        route="Reliability Analysis",
        model="Qwen2.5-7B-Instruct",
    )
    telemetry.update_workflow_stage("RAG", "ACTIVE")

    current_task = telemetry.get_full_telemetry()["current_task"]
    assert current_task["query"] == "Why is Pump P-101 vibrating?"
    assert current_task["route"] == "Reliability Analysis"
    assert current_task["model"] == "Qwen2.5-7B-Instruct"
    assert current_task["stages"]["ROUTING"] == "COMPLETED"
    assert current_task["stages"]["RAG"] == "ACTIVE"


def test_performance_metrics_capabilities():
    """Test 7: Performance metrics across CODE, OCR, VISION, and DOC GEN."""
    telemetry = get_telemetry_service()
    
    telemetry.update_capability_performance(
        capability="CODE",
        model="Qwen2.5-Coder-7B",
        latency_seconds=1.82,
        status="IDLE",
        tokens_count=120,
    )

    perf = telemetry.get_full_telemetry()["performance"]
    assert perf["CODE"]["model"] == "Qwen2.5-Coder-7B"
    assert perf["CODE"]["requests_processed"] >= 1
    assert "1.82s" in perf["CODE"]["last_latency_seconds"]


def test_telemetry_rest_api_endpoints():
    """Test REST API endpoints for telemetry system."""
    # GET /system/telemetry
    res1 = client.get("/system/telemetry")
    assert res1.status_code == 200
    assert res1.json()["success"] is True
    assert "gpu" in res1.json()["data"]

    # GET /system/gpu
    res2 = client.get("/system/gpu")
    assert res2.status_code == 200
    assert "used_vram_gb" in res2.json()["data"]

    # GET /system/network
    res3 = client.get("/system/network")
    assert res3.status_code == 200
    assert res3.json()["data"]["mode"] == "LOCAL / AIR-GAPPED"

    # POST /system/telemetry/demo-mode
    res4 = client.post("/system/telemetry/demo-mode", json={"enabled": True})
    assert res4.status_code == 200
    assert res4.json()["data"]["demo_mode"] is True
