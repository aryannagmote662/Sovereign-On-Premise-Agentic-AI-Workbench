"""
Workbench unified request and response Pydantic schema models.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.schemas.rag import SourceCitationSchema


class WorkbenchChatRequest(BaseModel):
    """Payload for POST /workbench/chat endpoint."""

    query: str = Field(..., description="User prompt or question text", min_length=1)
    document_id: Optional[str] = Field(default=None, description="Optional document ID filter for RAG")
    force_rag: Optional[bool] = Field(default=False, description="Explicitly require RAG context retrieval")
    top_k: Optional[int] = Field(default=None, description="Optional top_k chunks limit", ge=1, le=20)


class WorkbenchChatResponse(BaseModel):
    """Response model for POST /workbench/chat endpoint."""

    request_id: str = Field(..., description="Unique request turn tracking ID")
    query: str = Field(..., description="Original user prompt")
    intent: str = Field(..., description="Classified intent tag (e.g. GENERAL_CHAT, CODING, DOCUMENT)")
    selected_model: str = Field(..., description="Target model tag (e.g. qwen2.5:7b, deepseek-coder:6.7b)")
    answer: str = Field(..., description="Model response text")
    sources: List[SourceCitationSchema] = Field(default_factory=list, description="Source citations if RAG was used")
    grounded_in_docs: bool = Field(default=False, description="Flag indicating if answer was grounded in RAG context")
    execution_time_seconds: float = Field(default=0.0, description="Total turn processing time in seconds")
    status: str = Field(default="SUCCESS", description="Execution status tag")
    generated_artifact: Optional[Dict[str, Any]] = Field(default=None, description="Generated document artifact metadata if a document was created")



class WorkbenchDocumentUploadResponse(BaseModel):
    """Response model for POST /workbench/documents endpoint."""

    status: str = Field(default="SUCCESS", description="Document ingestion status")
    filename: str = Field(..., description="Original filename")
    document_id: str = Field(..., description="Assigned unique document ID")
    total_pages: int = Field(..., description="Total document pages processed")
    indexed_chunks_count: int = Field(..., description="Total vector chunks indexed in RAG store")
    extraction_mode: str = Field(..., description="Extraction mode used: text_parser or ocr_vision")
    message: str = Field(default="Document processed and indexed into RAG store successfully", description="Status message")


class WorkbenchImageRequest(BaseModel):
    """Payload for POST /workbench/images JSON request."""

    image_path: Optional[str] = Field(default=None, description="File path to target input image")
    prompt: Optional[str] = Field(default="Analyze engineering diagram and extract key text", description="Vision prompt instructions")


class WorkbenchImageResponse(BaseModel):
    """Response model for POST /workbench/images endpoint."""

    filename: str = Field(..., description="Target image filename")
    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")
    visual_analysis: str = Field(..., description="Multimodal visual analysis output text")
    model_used: str = Field(default="minicpm-v:8b", description="Vision LLM model tag used")
    status: str = Field(default="SUCCESS", description="Execution status")


class WorkbenchHealthResponse(BaseModel):
    """Response model for GET /workbench/health endpoint."""

    status: str = Field(default="healthy", description="Overall workbench system status")
    workbench_enabled: bool = Field(default=True, description="Workbench system active status")
    router_status: Dict[str, Any] = Field(default_factory=dict, description="Model router status and intent rules")
    rag_status: Dict[str, Any] = Field(default_factory=dict, description="Local RAG subsystem status and collection count")
    ocr_status: Dict[str, Any] = Field(default_factory=dict, description="OCR & Vision subsystem status")
    memory_status: Dict[str, Any] = Field(default_factory=dict, description="Memory diagnostic and VRAM load metrics")
    offline_status: Optional[Dict[str, Any]] = Field(default=None, description="Consolidated air-gapped security and offline posture telemetry")
