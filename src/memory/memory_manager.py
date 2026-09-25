"""
Centralized system RAM and VRAM memory orchestration.
"""

from typing import Any, Dict, Optional
from config.settings import settings
from src.memory.gpu_manager import GPUManager
from src.models.runtime.base_runtime import BaseRuntime
from utils.logger import logger
from utils.model_utils import get_runtime


class MemoryManager:
    """
    Centralized controller for managing memory allocation and enforcing single-model residency.
    """

    def __init__(self, ram_limit_mb: Optional[int] = None) -> None:
        self.ram_limit_mb = ram_limit_mb or settings.MAX_RAM_USAGE_MB
        self.gpu_manager = GPUManager()

    def get_system_memory_status(self) -> Dict[str, Any]:
        """
        Query system RAM consumption metrics.
        """
        vram_status = self.gpu_manager.get_vram_usage()
        return {
            "total_ram_mb": self.ram_limit_mb,
            "max_concurrent_models": settings.MAX_CONCURRENT_MODELS,
            "gpu_vram": vram_status,
        }

    def prepare_model_for_execution(self, target_model: str, runtime: Optional[BaseRuntime] = None) -> bool:
        """
        Single-Model Workflow Orchestration:
        1. Check currently loaded model in GPU VRAM
        2. If a different model is loaded, unload previous model from VRAM
        3. Load target model into VRAM
        4. Track active model state
        """
        active_runtime = runtime or get_runtime()
        current_model = self.gpu_manager.currently_loaded_model

        if current_model and current_model != target_model:
            logger.info(f"MemoryManager: Swapping model '{current_model}' -> '{target_model}'. Unloading active model.")
            self.gpu_manager.unload_active_model(runtime=active_runtime)

        if current_model != target_model:
            logger.info(f"MemoryManager: Loading requested model '{target_model}'...")
            try:
                from src.models.registry import ModelStatus, get_model_registry
                from src.observability.telemetry_service import get_telemetry_service
                registry = get_model_registry()
                telemetry = get_telemetry_service()
                registry.update_model_status(target_model, ModelStatus.LOADING)
                telemetry.emit_event("MODEL_LOADING", f"Loading model '{target_model}' into GPU VRAM...")
            except Exception:
                pass

            loaded = active_runtime.load_model(target_model)
            if loaded:
                self.gpu_manager.currently_loaded_model = target_model
                try:
                    registry.update_model_status(target_model, ModelStatus.LOADED)
                    telemetry.emit_event("MODEL_LOADED", f"Model '{target_model}' loaded successfully into VRAM")
                except Exception:
                    pass
                return True
            else:
                try:
                    registry.update_model_status(target_model, ModelStatus.ERROR)
                    telemetry.emit_event("MODEL_ERROR", f"Failed to load model '{target_model}'")
                except Exception:
                    pass
                return False

        return True

    def enforce_single_model_constraint(self, target_model: str, runtime: Optional[BaseRuntime] = None) -> bool:
        """
        Enforce that only target_model resides in memory.
        """
        return self.prepare_model_for_execution(target_model, runtime=runtime)
