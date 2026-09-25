"""
Multimodal Vision local model manager specification.
Inherits from BaseModel and delegates runtime execution.
"""

from typing import Any, Dict, Optional
from config.settings import settings
from src.models.base_model import BaseModel
from src.models.runtime.base_runtime import BaseRuntime


class VisionManager(BaseModel):
    """
    Manager abstraction for local multimodal vision models (e.g., LLaVA, Qwen-VL).
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        runtime: Optional[BaseRuntime] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        target_name = model_name or settings.DEFAULT_VISION_MODEL
        super().__init__(model_name=target_name, runtime=runtime, config=config)

    def analyze_image(self, image_path: str, prompt: str, **kwargs: Any) -> str:
        """
        Analyze an image given an image file path by delegating prompt and image context to runtime.
        """
        images = kwargs.pop("images", [image_path])
        return self.generate(prompt=prompt, images=images, **kwargs)

    def get_metadata(self) -> Dict[str, Any]:
        """Retrieve Vision model architecture metadata."""
        return {
            "model_name": self.model_name,
            "family": "vision_multimodal",
            "context_length": 4096,
            "capabilities": ["ocr", "diagram_analysis", "visual_inspection"],
        }
