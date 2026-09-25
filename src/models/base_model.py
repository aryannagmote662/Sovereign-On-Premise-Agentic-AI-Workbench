"""
Abstract base model interface contract for local language and multimodal models.
Decoupled entirely from specific runtime engines.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, Optional
from src.models.runtime.base_runtime import BaseRuntime
from utils.model_utils import get_runtime


class BaseModel(ABC):
    """
    Abstract Base Class for all local AI model implementations.
    Delegates all execution and lifecycle operations to BaseRuntime.
    """

    def __init__(
        self,
        model_name: str,
        runtime: Optional[BaseRuntime] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.model_name = model_name
        self.runtime: BaseRuntime = runtime or get_runtime()
        self.config = config or {}
        self.is_loaded: bool = False

    def load(self, **kwargs: Any) -> bool:
        """
        Load model weights into memory / GPU VRAM via runtime adapter.
        """
        success = self.runtime.load_model(self.model_name, **kwargs)
        if success:
            self.is_loaded = True
        return success

    def unload(self, **kwargs: Any) -> bool:
        """
        Unload model weights from memory / GPU VRAM via runtime adapter.
        """
        success = self.runtime.unload_model(self.model_name, **kwargs)
        if success:
            self.is_loaded = False
        return success

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Generate text response by delegating to runtime adapter.
        Enforces single-model VRAM residency tracking via MemoryManager.
        """
        try:
            from src.memory.memory_manager import MemoryManager
            mm = MemoryManager()
            mm.prepare_model_for_execution(self.model_name, runtime=self.runtime)
        except Exception:
            pass

        return self.runtime.generate(prompt=prompt, model_name=self.model_name, **kwargs)

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncGenerator[str, None]:
        """
        Async stream contract placeholder for streaming responses.
        """
        response_text = self.generate(prompt, **kwargs)
        yield response_text

    def health(self) -> Dict[str, Any]:
        """
        Query detailed model health metrics (Task 7 requirement).
        Returns:
            loaded: bool
            available: bool
            runtime_status: str/dict
            gpu_available: bool
            model_exists: bool
        """
        runtime_health = self.runtime.health()
        runtime_available = runtime_health.get("available", False)
        installed_models = runtime_health.get("installed_models", [])
        model_exists = self.model_name in installed_models if installed_models else True

        return {
            "model_name": self.model_name,
            "loaded": self.is_loaded,
            "available": runtime_available and model_exists,
            "runtime_status": runtime_health,
            "gpu_available": runtime_health.get("gpu_enabled", True),
            "model_exists": model_exists,
        }

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """
        Retrieve model capability specifications and architecture footprint.
        """
        pass
