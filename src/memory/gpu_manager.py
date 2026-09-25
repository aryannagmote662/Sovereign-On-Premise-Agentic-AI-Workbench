"""
GPU VRAM monitoring and single-model eviction specification.
"""

from typing import Any, Dict, Optional
from config.settings import settings
from utils.logger import logger


class GPUManager:
    """
    Controller tracking VRAM telemetry and active loaded model state across the application.
    """

    _active_model: Optional[str] = None

    def __init__(self, vram_limit_mb: Optional[int] = None) -> None:
        self.vram_limit_mb = vram_limit_mb or settings.MAX_VRAM_USAGE_MB

    @property
    def currently_loaded_model(self) -> Optional[str]:
        """Return currently active loaded model tag."""
        return GPUManager._active_model

    @currently_loaded_model.setter
    def currently_loaded_model(self, model_name: Optional[str]) -> None:
        """Update currently active loaded model tag and notify TelemetryService."""
        old_model = GPUManager._active_model
        GPUManager._active_model = model_name

        try:
            from src.models.registry import ModelStatus, get_model_registry
            from src.observability.telemetry_service import get_telemetry_service
            registry = get_model_registry()
            telemetry = get_telemetry_service()

            if old_model and old_model != model_name:
                registry.update_model_status(old_model, ModelStatus.UNLOADED)
                telemetry.emit_event("MODEL_UNLOADED", f"Model '{old_model}' evicted from VRAM")

            if model_name:
                registry.update_model_status(model_name, ModelStatus.ACTIVE)
                telemetry.record_model_switch(old_model, model_name, reason="GPU residency allocation")
        except Exception:
            pass

    def get_vram_usage(self) -> Dict[str, Any]:
        """
        Fetch VRAM budget and currently loaded model state.
        """
        return {
            "vram_limit_mb": self.vram_limit_mb,
            "vram_budget_mb": settings.MAX_VRAM_USAGE_MB,
            "currently_loaded_model": self.currently_loaded_model,
        }

    def unload_active_model(self, runtime: Optional[Any] = None) -> bool:
        """
        Issue unload instruction for currently active model to enforce single-model VRAM loading.
        """
        if self.currently_loaded_model is None:
            return True

        model_to_unload = self.currently_loaded_model
        logger.info(f"GPUManager: Evicting previously loaded model '{model_to_unload}' from VRAM...")

        try:
            from src.models.registry import ModelStatus, get_model_registry
            from src.observability.telemetry_service import get_telemetry_service
            registry = get_model_registry()
            telemetry = get_telemetry_service()
            registry.update_model_status(model_to_unload, ModelStatus.UNLOADING)
            telemetry.emit_event("MODEL_UNLOADING", f"Evicting model '{model_to_unload}' from VRAM...")
        except Exception:
            pass

        if runtime is not None:
            runtime.unload_model(model_to_unload)

        self.currently_loaded_model = None
        return True
