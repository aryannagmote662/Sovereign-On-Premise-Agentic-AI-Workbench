"""
Workbench Unified REST API Routes for MRPL AI Workbench.
Exposes endpoints orchestrating end-to-end chat routing, document ingestion, vision analysis, and system health.
"""

from pathlib import Path
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from src.api.dependencies import get_workbench_service
from src.api.responses.standard_response import StandardResponse, success_response
from src.services.workbench_service import WorkbenchService
from src.schemas.workbench import (
    WorkbenchChatRequest,
    WorkbenchChatResponse,
    WorkbenchDocumentUploadResponse,
    WorkbenchHealthResponse,
    WorkbenchImageResponse,
)
from src.auth.models import User
from src.security.authorization_gate import get_current_user_optional

router = APIRouter(tags=["Unified Workbench Workflows"])


@router.post(
    "/workbench/chat",
    response_model=StandardResponse[WorkbenchChatResponse],
    summary="Unified Chat & Grounded QA Workflow",
    description="Route user questions via Intelligent Router to Qwen, DeepSeek, or Vision LLMs, grounding answers in RAG document context when required.",
)
async def workbench_chat(
    request: WorkbenchChatRequest,
    workbench_service: Annotated[WorkbenchService, Depends(get_workbench_service)],
    user: User = Depends(get_current_user_optional),
) -> StandardResponse[WorkbenchChatResponse]:
    """
    POST /workbench/chat endpoint executing unified intent routing and RAG grounding with user security context.
    """
    try:
        response = await workbench_service.ask_question(
            query=request.query,
            document_id=request.document_id,
            force_rag=request.force_rag,
            top_k=request.top_k,
            user=user,
        )

        return success_response(
            data=response,
            message="Workbench question processed successfully",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Workbench chat error: {str(exc)}")


@router.post(
    "/workbench/chat/with-attachment",
    response_model=StandardResponse[WorkbenchChatResponse],
    summary="Unified Chat Turn with Attached File",
    description="Route prompt with attached document or image file.",
)
async def workbench_chat_with_attachment(
    query: str = Form(..., description="User question prompt"),
    file: UploadFile = File(..., description="Attached file payload"),
    force_rag: bool = Form(False, description="Force RAG flag"),
    workbench_service: WorkbenchService = Depends(get_workbench_service),
    user: User = Depends(get_current_user_optional),
) -> StandardResponse[WorkbenchChatResponse]:
    """
    POST /workbench/chat/with-attachment endpoint processing prompt along with attached document or photo.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded attachment missing valid filename.")

    try:
        content_bytes = await file.read()
        response = await workbench_service.ask_question_with_attachment(
            query=query,
            filename=file.filename,
            content_bytes=content_bytes,
            force_rag=force_rag,
            user=user,
        )
        return success_response(
            data=response,
            message=f"Workbench question with attachment '{file.filename}' processed successfully",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Workbench attachment chat error: {str(exc)}")


@router.get(
    "/workbench/artifacts/download/{filename}",
    summary="Download Generated Artifact Deliverable",
    description="Download generated Word (.docx), PowerPoint (.pptx), PDF (.pdf), or Excel (.xlsx) file.",
)
async def download_artifact(filename: str):
    """
    GET /workbench/artifacts/download/{filename} serving deliverable files.
    """
    target_dirs = [Path("examples/output"), Path("data/artifacts")]
    target_file = None
    for d in target_dirs:
        possible = d / filename
        if possible.exists() and possible.is_file():
            target_file = possible
            break

    if not target_file:
        raise HTTPException(status_code=404, detail=f"Artifact deliverable '{filename}' not found.")

    return FileResponse(
        path=str(target_file),
        filename=filename,
        media_type="application/octet-stream",
    )



@router.post(
    "/workbench/documents",
    response_model=StandardResponse[WorkbenchDocumentUploadResponse],
    summary="Unified Document Ingestion Workflow",
    description="Upload text or scanned document/image to run PDF page detection, OCR, text chunking, and vector RAG indexing.",
)
async def workbench_upload_document(
    file: UploadFile = File(..., description="Target document file to upload and index"),
    document_id: Optional[str] = Form(None, description="Optional custom document ID override"),
    chunk_size: Optional[int] = Form(None, description="Optional custom chunk size"),
    chunk_overlap: Optional[int] = Form(None, description="Optional custom chunk overlap"),
    workbench_service: WorkbenchService = Depends(get_workbench_service),
    user: User = Depends(get_current_user_optional),
) -> StandardResponse[WorkbenchDocumentUploadResponse]:
    """
    POST /workbench/documents endpoint executing unified ingestion pipeline with workspace isolation.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded document missing valid filename.")

    try:
        content = await file.read()
        res = workbench_service.process_document(
            filename=file.filename,
            content_bytes=content,
            document_id=document_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            workspace_id=user.workspace_id,
            classification_level=user.clearance_level,
        )

        return success_response(
            data=res,
            message=f"Document '{file.filename}' processed via {res.extraction_mode} and indexed into RAG store.",
        )
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Workbench document ingestion failed: {str(exc)}")


@router.post(
    "/workbench/images",
    response_model=StandardResponse[WorkbenchImageResponse],
    summary="Unified Vision Inspection Workflow",
    description="Upload technical image or engineering diagram for multimodal visual inspection via MiniCPM-V 8B.",
)
async def workbench_process_image(
    file: UploadFile = File(..., description="Target engineering diagram or image"),
    prompt: Optional[str] = Form("Analyze engineering diagram and extract key text", description="Vision prompt"),
    workbench_service: WorkbenchService = Depends(get_workbench_service),
) -> StandardResponse[WorkbenchImageResponse]:
    """
    POST /workbench/images endpoint delegating to VisionManager.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded image missing valid filename.")

    try:
        content = await file.read()
        res = workbench_service.process_image(
            image_bytes=content,
            filename=file.filename,
            prompt=prompt,
        )
        return success_response(
            data=res,
            message=f"Vision inspection completed for '{file.filename}'.",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Workbench vision processing failed: {str(exc)}")


@router.get(
    "/workbench/health",
    response_model=StandardResponse[WorkbenchHealthResponse],
    summary="Unified Workbench Health Check",
    description="Query consolidated metrics across Intelligent Router, RAG, OCR, and VRAM memory telemetry.",
)
async def workbench_health(
    workbench_service: Annotated[WorkbenchService, Depends(get_workbench_service)],
) -> StandardResponse[WorkbenchHealthResponse]:
    """
    GET /workbench/health endpoint returning consolidated workbench telemetry.
    """
    health_payload = workbench_service.health()
    return success_response(
        data=health_payload,
        message="Workbench operational health and memory metrics retrieved successfully",
    )


@router.post(
    "/workbench/demo/inspection",
    response_model=StandardResponse[dict],
    summary="Phase 14 Primary Industrial Demonstration Workflow",
    description="Run end-to-end scanned inspection report workflow: OCR -> RAG -> Approval Note -> DOCX artifact.",
)
async def workbench_demo_inspection(
    file: Optional[UploadFile] = File(None, description="Optional uploaded inspection report document"),
    auto_index: bool = Form(True, description="Auto-index into RAG vector store"),
    generate_approval_note: bool = Form(True, description="Generate official .docx approval note"),
    workbench_service: WorkbenchService = Depends(get_workbench_service),
):
    try:
        from pathlib import Path
        sample_path = Path("examples/data/inspection_report.txt")
        content_bytes = sample_path.read_bytes() if sample_path.exists() else b"MRPL AI WORKBENCH DEMO REPORT MRPL-AI-DEMO-001\nRefinery Unit 4 inspection completed."
        filename = "inspection_report.txt"
        if file and file.filename:
            content_bytes = await file.read()
            filename = file.filename

        res = workbench_service.run_inspection_demo(
            content_bytes=content_bytes,
            filename=filename,
            auto_index=auto_index,
            generate_approval_note=generate_approval_note,
        )
        return success_response(data=res, message="Inspection report demonstration executed successfully")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Inspection demonstration error: {str(exc)}")


@router.post(
    "/workbench/demo/coding",
    response_model=StandardResponse[dict],
    summary="Phase 14 Secure Coding Demonstration Workflow",
    description="Run end-to-end coding workflow in sandbox via DeepSeek model.",
)
async def workbench_demo_coding(
    prompt: Optional[str] = Form(None, description="Coding prompt instruction"),
    workbench_service: WorkbenchService = Depends(get_workbench_service),
):
    try:
        res = workbench_service.run_coding_demo(prompt=prompt)
        return success_response(data=res, message="Secure coding sandbox demonstration executed successfully")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Coding demonstration error: {str(exc)}")


@router.post(
    "/workbench/demo/vision",
    response_model=StandardResponse[dict],
    summary="Phase 14 Multimodal Vision Demonstration Workflow",
    description="Run end-to-end vision inspection workflow via MiniCPM-V model.",
)
async def workbench_demo_vision(
    file: Optional[UploadFile] = File(None, description="Target image or engineering diagram"),
    prompt: Optional[str] = Form(None, description="Vision analysis prompt"),
    workbench_service: WorkbenchService = Depends(get_workbench_service),
):
    try:
        filename = file.filename if file and file.filename else "engineering_diagram.png"
        content_bytes = await file.read() if file else None
        res = workbench_service.run_vision_demo(
            image_bytes=content_bytes,
            filename=filename,
            prompt=prompt,
        )
        return success_response(data=res, message="Multimodal vision demonstration executed successfully")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vision demonstration error: {str(exc)}")


@router.get(
    "/workbench/performance",
    response_model=StandardResponse[dict],
    summary="Phase 14 Model Benchmarking & Performance Telemetry",
    description="Return model load times, inference latency, memory/VRAM usage, and switching metrics.",
)
async def workbench_performance():
    from src.observability.benchmark import benchmark_manager
    metrics_data = benchmark_manager.get_latest_metrics()
    return success_response(data=metrics_data, message="Performance telemetry retrieved successfully")


@router.get(
    "/workbench/security/posture",
    response_model=StandardResponse[dict],
    summary="Phase 14 Air-Gapped Security Posture",
    description="Return offline mode, strict mode, network policy, cloud model policy, prohibited tools, and network validation status.",
)
async def workbench_security_posture():
    from src.security.offline_guard import OfflineGuard
    guard = OfflineGuard()
    posture_data = guard.get_status()
    posture_data["network_sovereignty"] = "LOCAL_ONLY_ENFORCED"
    posture_data["prohibited_tools_enforced"] = [
        "shell_tool", "network_tool", "external_api_tool", "remote_http", "cloud_llm", "cloud_embedding", "cloud_ocr"
    ]
    return success_response(data=posture_data, message="Air-gapped security posture retrieved successfully")



