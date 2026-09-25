"""
OCR Service Module for MRPL AI Workbench.
Business logic layer providing OCR document processing, vision image analysis, and health monitoring.
FastAPI route handlers delegate exclusively to this service.
"""

import logging
from typing import Any, Dict, Optional

from config.settings import settings
from src.ocr.image_processor import ImageProcessor
from src.ocr.ocr_pipeline import OCRPipeline
from src.ocr.text_ocr import TextOCREngine
from src.ocr.vision_analyzer import VisionAnalyzer
from src.schemas.ocr import OCRProcessResponse

logger = logging.getLogger("MRPL.OCR.Service")


class OCRService:
    """
    OCR Service business layer orchestrating OCR pipeline execution,
    diagram visual inspection, and subsystem health telemetry.
    """

    def __init__(
        self,
        pipeline: Optional[OCRPipeline] = None,
        vision_analyzer: Optional[VisionAnalyzer] = None,
        image_processor: Optional[ImageProcessor] = None,
    ) -> None:
        self.image_processor = image_processor or ImageProcessor()
        self._vision_analyzer = vision_analyzer
        text_ocr = TextOCREngine(
            image_processor=self.image_processor,
            vision_analyzer=self.vision_analyzer,
        )
        self.pipeline = pipeline or OCRPipeline(
            image_processor=self.image_processor,
            text_ocr=text_ocr,
        )

    @property
    def vision_analyzer(self) -> VisionAnalyzer:
        if self._vision_analyzer is None:
            self._vision_analyzer = VisionAnalyzer(image_processor=self.image_processor)
        return self._vision_analyzer

    def process_document(
        self,
        filename: str,
        content_bytes: bytes,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        document_id: Optional[str] = None,
    ) -> OCRProcessResponse:
        """
        Process document or scanned image payload through OCR Pipeline.

        Args:
            filename: Name of file.
            content_bytes: Raw document byte payload.
            chunk_size: Optional custom chunk character limit.
            chunk_overlap: Optional custom chunk overlap.
            document_id: Optional custom document ID.

        Returns:
            OCRProcessResponse container object.
        """
        return self.pipeline.process_document(
            filename=filename,
            content_bytes=content_bytes,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            document_id=document_id,
        )

    def process_image(
        self,
        image_bytes: bytes,
        filename: str = "image.png",
        prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process single image for visual inspection and component analysis.

        Args:
            image_bytes: Raw image byte payload.
            filename: Image filename.
            prompt: Optional visual analysis prompt instructions.

        Returns:
            Dict containing visual analysis breakdown and image metadata.
        """
        processed = self.image_processor.process_image_bytes(image_bytes, filename=filename)
        return self.vision_analyzer.analyze_diagram(processed, prompt=prompt)

    def health(self) -> Dict[str, Any]:
        """
        Query OCR and Vision subsystem health status.
        """
        return {
            "status": "healthy" if settings.OCR_ENABLED else "disabled",
            "ocr_enabled": settings.OCR_ENABLED,
            "ocr_engine": settings.OCR_ENGINE,
            "vision_enabled": settings.VISION_ENABLED,
            "vision_model": settings.DEFAULT_VISION_MODEL,
            "local": True,
            "offline_safe": not getattr(settings, "ALLOW_REMOTE_OCR", False),
            "max_image_size_mb": settings.OCR_MAX_IMAGE_SIZE_MB,
            "max_page_pixels": settings.OCR_MAX_PAGE_PIXELS,
        }
