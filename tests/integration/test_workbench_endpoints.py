"""
Integration tests for unified Workbench REST API endpoints.
"""

import io
from typing import Any, Tuple
from unittest.mock import MagicMock
from PIL import Image
from fastapi.testclient import TestClient
import pytest

from src.api.app import app
from src.api.dependencies import get_workbench_service
from src.models.base_model import BaseModel
from src.models.deepseek_manager import DeepSeekManager
from src.models.qwen_manager import QwenManager
from src.models.vision_manager import VisionManager
from src.rag.embeddings import MockEmbeddingProvider
from src.rag.rag_service import RAGService
from src.rag.vector_store import MockVectorStore
from src.routing.intent_classifier import UserIntent
from src.routing.model_router import ModelRouter
from src.routing.routing_rules import RoutingRules
from src.services.chat_service import ChatService
from src.services.workbench_service import WorkbenchService

client = TestClient(app)


from config.settings import settings


@pytest.fixture(autouse=True)
def override_workbench_dependency() -> None:
    from src.security.request_security import get_security_service
    get_security_service().rate_limiter.reset()

    mock_qwen = MagicMock(spec=QwenManager)
    mock_qwen.model_name = settings.QWEN_MODEL
    mock_qwen.generate.return_value = "CDU pressure is 15 bar based on document context."

    mock_deepseek = MagicMock(spec=DeepSeekManager)
    mock_deepseek.model_name = settings.DEFAULT_CODER_MODEL
    mock_deepseek.generate.return_value = "def sort(): pass"

    mock_vision = MagicMock(spec=VisionManager)
    mock_vision.model_name = settings.DEFAULT_VISION_MODEL
    mock_vision.analyze_image.return_value = "Valve V-1"
    mock_vision.generate.return_value = "Valve V-1"

    rules = RoutingRules(
        custom_mappings={
            UserIntent.GENERAL_CHAT: mock_qwen,
            UserIntent.DOCUMENT: mock_qwen,
            UserIntent.APPROVAL_NOTE: mock_qwen,
            UserIntent.SUMMARIZATION: mock_qwen,
            UserIntent.CODING: mock_deepseek,
            UserIntent.DEBUGGING: mock_deepseek,
            UserIntent.IMAGE: mock_vision,
            UserIntent.OCR: mock_vision,
            UserIntent.DIAGRAM: mock_vision,
            UserIntent.UNKNOWN: mock_qwen,
        }
    )
    router = ModelRouter(rules=rules)
    chat_svc = ChatService(router=router)

    rag = RAGService(
        vector_store=MockVectorStore(),
        embedding_provider=MockEmbeddingProvider(),
        qwen_manager=mock_qwen,
    )
    fake_wb = WorkbenchService(
        router=router,
        chat_service=chat_svc,
        rag_service=rag,
    )

    app.dependency_overrides[get_workbench_service] = lambda: fake_wb
    yield
    app.dependency_overrides.clear()


def test_api_workbench_chat_general() -> None:
    payload = {"query": "Explain what a refinery CDU unit does"}
    headers = {"Authorization": f"Bearer {settings.AUTH_TOKEN}"}
    response = client.post("/workbench/chat", json=payload, headers=headers)
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    data = res["data"]
    assert "request_id" in data
    assert data["intent"] == "GENERAL_CHAT"
    assert data["selected_model"] == settings.QWEN_MODEL


def test_api_workbench_documents_upload() -> None:
    files = {"file": ("manual.txt", b"Operating pressure is 15 bar.", "text/plain")}
    headers = {"Authorization": f"Bearer {settings.AUTH_TOKEN}"}
    response = client.post("/workbench/documents", files=files, headers=headers)
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    data = res["data"]
    assert data["status"] == "SUCCESS"
    assert data["filename"] == "manual.txt"
    assert data["indexed_chunks_count"] > 0


from unittest.mock import patch


def test_api_workbench_images_process() -> None:
    with patch("src.models.runtime.ollama_runtime.OllamaRuntime.generate") as mock_gen:
        mock_gen.return_value = "Schematic analysis complete: Valve V-1 present."
        img = Image.new("RGB", (50, 50), color="yellow")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        files = {"file": ("schematic.png", buf, "image/png")}

        response = client.post("/workbench/images", files=files)
        assert response.status_code == 200
        res = response.json()
        assert res["success"] is True
        assert res["data"]["filename"] == "schematic.png"


def test_api_workbench_health() -> None:
    response = client.get("/workbench/health")
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    data = res["data"]
    assert data["status"] == "healthy"
    assert "memory_status" in data
