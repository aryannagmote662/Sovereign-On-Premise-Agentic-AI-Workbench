"""
Model Registry & Configuration System for MRPL AI Workbench.
Data-driven model discovery supporting future open-weight models without redesigning UI or backend.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("MRPL.ModelRegistry")


class ModelStatus(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    AVAILABLE = "AVAILABLE"
    LOADING = "LOADING"
    LOADED = "LOADED"
    ACTIVE = "ACTIVE"
    BUSY = "BUSY"
    UNLOADING = "UNLOADING"
    UNLOADED = "UNLOADED"
    ERROR = "ERROR"


class ModelSpec(BaseModel):
    """
    Model specification metadata for open-weight models.
    """
    model_id: str
    display_name: str
    provider: str = "Open-Weight"
    runtime: str = "ollama"
    ollama_tag: str
    model_size: str = "7B"
    quantization: str = "Q4_K_M"
    task_types: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    vram_requirement_mb: int = 4096
    status: ModelStatus = ModelStatus.UNLOADED
    enabled: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelRegistry:
    """
    Data-driven registry managing configuration, capabilities, and dynamic discovery of local models.
    Allows adding new open-weight models (Llama, Mistral, Gemma, Qwen, DeepSeek, Phi, etc.) at runtime.
    """

    _instance: Optional["ModelRegistry"] = None

    def __init__(self) -> None:
        self._models: Dict[str, ModelSpec] = {}
        self._register_default_models()

    @classmethod
    def get_instance(cls) -> "ModelRegistry":
        if cls._instance is None:
            cls._instance = ModelRegistry()
        return cls._instance

    def _register_default_models(self) -> None:
        """Register default sovereign open-weight models."""
        defaults = [
            ModelSpec(
                model_id="qwen25-instruct-7b",
                display_name="Qwen2.5-7B-Instruct",
                provider="Alibaba / Sovereign Local",
                runtime="ollama",
                ollama_tag="qwen2.5:7b",
                model_size="7B",
                quantization="Q4_K_M",
                task_types=["general", "document", "summarization", "reasoning"],
                capabilities=["general", "documents", "summarization", "reasoning", "document_generation"],
                vram_requirement_mb=5800,
                status=ModelStatus.LOADED,
                enabled=True,
            ),
            ModelSpec(
                model_id="qwen25-coder-7b",
                display_name="Qwen2.5-Coder-7B-Instruct",
                provider="Alibaba / Sovereign Local",
                runtime="ollama",
                ollama_tag="qwen2.5-coder:7b",
                model_size="7B",
                quantization="Q4_K_M",
                task_types=["coding", "debugging", "sql", "refactoring"],
                capabilities=["coding", "debugging", "sql", "code_generation"],
                vram_requirement_mb=5800,
                status=ModelStatus.UNLOADED,
                enabled=True,
            ),
            ModelSpec(
                model_id="qwen25-vl-3b",
                display_name="Qwen2.5-VL-3B-Instruct",
                provider="Alibaba / Sovereign Local",
                runtime="ollama",
                ollama_tag="qwen2.5-vl:3b",
                model_size="3B",
                quantization="Q4_K_M",
                task_types=["vision", "image_analysis", "document_visual_analysis", "ocr"],
                capabilities=["vision", "image_analysis", "document_visual_analysis", "ocr"],
                vram_requirement_mb=3400,
                status=ModelStatus.UNLOADED,
                enabled=True,
            ),
            ModelSpec(
                model_id="deepseek-coder-6.7b",
                display_name="DeepSeek-Coder-6.7B",
                provider="DeepSeek / Sovereign Local",
                runtime="ollama",
                ollama_tag="deepseek-coder:6.7b",
                model_size="6.7B",
                quantization="Q4_K_M",
                task_types=["coding", "debugging", "sandbox_execution"],
                capabilities=["coding", "debugging", "sandbox"],
                vram_requirement_mb=5200,
                status=ModelStatus.UNLOADED,
                enabled=True,
            ),
        ]

        for spec in defaults:
            self.register_model(spec)

    def register_model(self, spec: ModelSpec) -> None:
        """Register a new open-weight model specification."""
        self._models[spec.model_id] = spec
        # Also key by ollama_tag for fast lookup
        self._models[spec.ollama_tag] = spec
        logger.info(f"ModelRegistry: Registered model '{spec.display_name}' (ID: {spec.model_id}, Tag: {spec.ollama_tag})")

    def get_model(self, model_id_or_tag: str) -> Optional[ModelSpec]:
        """Retrieve model specification by ID, tag, display name, or prefix."""
        if not model_id_or_tag:
            return None

        # 1. Exact match
        target = model_id_or_tag.lower().strip()
        if target in self._models:
            return self._models[target]

        # 2. Match by display name or ollama_tag or model_id case-insensitive
        for spec in self._models.values():
            if (
                spec.model_id.lower() == target
                or spec.ollama_tag.lower() == target
                or spec.display_name.lower() == target
            ):
                return spec

        # 3. Match by base prefix (e.g., qwen2.5:7b-instruct -> qwen2.5:7b or coder -> qwen25-coder-7b)
        base = target.split(":")[0].replace("-instruct", "")
        for spec in self._models.values():
            spec_tag_base = spec.ollama_tag.lower().split(":")[0]
            spec_id = spec.model_id.lower()
            if (
                base in spec_id
                or base in spec_tag_base
                or ("coder" in target and "coder" in spec_id)
                or ("vl" in target and "vl" in spec_id)
                or ("vision" in target and "vl" in spec_id)
            ):
                return spec

        return None

    def update_model_status(self, model_id_or_tag: str, status: ModelStatus) -> Optional[ModelSpec]:
        """Update model operational lifecycle status."""
        spec = self.get_model(model_id_or_tag)
        if spec:
            old_status = spec.status
            spec.status = status
            logger.info(f"ModelRegistry: Model '{spec.display_name}' status changed: {old_status.value} -> {status.value}")
            # If ACTIVE, ensure only this model is ACTIVE
            if status == ModelStatus.ACTIVE:
                for k, m in self._models.items():
                    if m.model_id != spec.model_id and m.status == ModelStatus.ACTIVE:
                        m.status = ModelStatus.LOADED
            return spec
        return None

    def list_models(self) -> List[Dict[str, Any]]:
        """List unique registered open-weight models as dictionaries."""
        seen = set()
        result = []
        for spec in self._models.values():
            if spec.model_id not in seen:
                seen.add(spec.model_id)
                result.append(spec.model_dump())
        return result


def get_model_registry() -> ModelRegistry:
    """Factory function for ModelRegistry singleton."""
    return ModelRegistry.get_instance()
