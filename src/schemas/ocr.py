"""
OCR & Vision request and response schema models.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.schemas.document import DocumentChunkSchema


class OCRRequest(BaseModel):
    """OCR and vision analysis request schema."""

    image_path: str = Field(..., description="File path to target input image")
    prompt: Optional[str] = Field(default="Extract all text and describe visual elements", description="Vision prompt instructions")


class OCRResponse(BaseModel):
    """OCR and vision analysis response schema."""

    extracted_text: str = Field(..., description="Extracted textual content")
    analysis: Optional[str] = Field(default=None, description="Detailed visual analysis summary")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Image dimensions and format metadata")


class OCRPageResultSchema(BaseModel):
    """Extracted OCR result for an individual document page."""

    page_number: int = Field(..., description="1-based page index")
    page_type: str = Field(..., description="Detected page classification: TEXT, SCANNED_IMAGE, or MIXED")
    ocr_applied: bool = Field(..., description="Flag indicating whether OCR/vision was applied")
    extracted_text: str = Field(..., description="Clean text extracted from page")
    word_count: int = Field(..., description="Word count in extracted text")
    char_count: int = Field(..., description="Character count in extracted text")
    extraction_method: str = Field(..., description="Method used: text_parser, vision_llm, or hybrid")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Page metadata specs")


class OCRProcessResponse(BaseModel):
    """Response model for POST /ocr/process endpoint."""

    status: str = Field(default="SUCCESS", description="Processing execution status")
    filename: str = Field(..., description="Original document or image filename")
    document_id: str = Field(..., description="Assigned document ID")
    total_pages: int = Field(..., description="Total pages processed")
    ocr_pages_count: int = Field(..., description="Number of pages requiring OCR/Vision processing")
    extracted_text: str = Field(default="", description="Combined extracted text from document")
    total_characters: int = Field(default=0, description="Total characters extracted across all pages")
    page_type: str = Field(default="MIXED", description="Primary page type classification")
    extraction_mode: str = Field(default="TEXT", description="Primary extraction method used")
    confidence: float = Field(default=1.0, description="OCR confidence score")
    pages: List[OCRPageResultSchema] = Field(default_factory=list, description="Per-page OCR results")
    chunks: List[DocumentChunkSchema] = Field(default_factory=list, description="Phase 5-compatible chunks ready for RAG")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Consolidated document metadata")


class OCRHealthResponse(BaseModel):
    """Response model for GET /ocr/health endpoint."""

    status: str = Field(default="healthy", description="OCR subsystem health status")
    ocr_enabled: bool = Field(default=True, description="OCR feature toggle setting")
    ocr_engine: str = Field(..., description="Active OCR engine provider")
    vision_enabled: bool = Field(default=True, description="Vision LLM analysis toggle setting")
    vision_model: str = Field(..., description="Configured vision model tag")
