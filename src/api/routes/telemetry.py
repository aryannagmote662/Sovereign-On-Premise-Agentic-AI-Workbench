"""
Telemetry & Monitoring API Router.
Exposes REST, WebSocket, and SSE endpoints for real-time model, VRAM, network, and performance visualization.
"""

import asyncio
import json
import logging
from typing import Any, Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.responses.standard_response import StandardResponse, success_response
from src.observability.telemetry_service import get_telemetry_service
from src.models.registry import get_model_registry

logger = logging.getLogger("MRPL.API.Telemetry")

router = APIRouter(prefix="/system", tags=["System Telemetry"])


class DemoModeRequest(BaseModel):
    enabled: bool


@router.get(
    "/telemetry",
    response_model=StandardResponse[Dict[str, Any]],
    summary="Get Consolidated Live Telemetry",
    description="Retrieve live GPU VRAM usage, active model, model loading history, network security posture, and capability performance.",
)
async def get_telemetry() -> StandardResponse[Dict[str, Any]]:
    telemetry_svc = get_telemetry_service()
    data = telemetry_svc.get_full_telemetry()
    return success_response(data=data, message="Telemetry retrieved successfully")


@router.get(
    "/system-models",
    response_model=StandardResponse[Dict[str, Any]],
    summary="List Model Registry & Discovery",
    description="List all registered open-weight models, operational status, quantization, VRAM requirement, and capabilities.",
)
async def get_system_models() -> StandardResponse[Dict[str, Any]]:
    registry = get_model_registry()
    data = {
        "models": registry.list_models(),
        "total": len(registry.list_models()),
    }
    return success_response(data=data, message="Registered models retrieved successfully")


@router.get(
    "/gpu",
    response_model=StandardResponse[Dict[str, Any]],
    summary="Get GPU & VRAM Physical Telemetry",
    description="Query VRAM allocation, total capacity, hardware device status, or telemetry status notice.",
)
async def get_gpu_telemetry() -> StandardResponse[Dict[str, Any]]:
    telemetry_svc = get_telemetry_service()
    data = telemetry_svc.get_gpu_telemetry()
    return success_response(data=data, message="GPU telemetry retrieved successfully")


@router.get(
    "/network",
    response_model=StandardResponse[Dict[str, Any]],
    summary="Get Air-Gapped Network Posture",
    description="Query network isolation status, blocked external call count, and local Ollama endpoint reachability.",
)
async def get_network_telemetry() -> StandardResponse[Dict[str, Any]]:
    telemetry_svc = get_telemetry_service()
    data = telemetry_svc.get_network_telemetry()
    return success_response(data=data, message="Network telemetry retrieved successfully")


@router.get(
    "/performance",
    response_model=StandardResponse[Dict[str, Any]],
    summary="Get 4 AI Capabilities Performance Metrics",
    description="Query latency, request count, tokens/sec, and status for CODE, OCR, VISION, and DOCUMENT GENERATION.",
)
async def get_performance_telemetry() -> StandardResponse[Dict[str, Any]]:
    telemetry_svc = get_telemetry_service()
    data = telemetry_svc.get_full_telemetry().get("performance", {})
    return success_response(data=data, message="Performance telemetry retrieved successfully")


@router.post(
    "/telemetry/demo-mode",
    response_model=StandardResponse[Dict[str, Any]],
    summary="Toggle Presentation Demo Mode",
    description="Switch between real hardware telemetry and simulated demo telemetry for presentation/testing.",
)
async def toggle_demo_mode(req: DemoModeRequest) -> StandardResponse[Dict[str, Any]]:
    telemetry_svc = get_telemetry_service()
    active_mode = telemetry_svc.set_demo_mode(req.enabled)
    return success_response(
        data={"demo_mode": active_mode, "mode_label": "DEMO TELEMETRY" if active_mode else "REAL TELEMETRY"},
        message=f"Telemetry mode set to {'DEMO MODE' if active_mode else 'REAL MODE'}",
    )


@router.websocket("/telemetry/stream")
async def telemetry_websocket_stream(websocket: WebSocket) -> None:
    """
    WebSocket endpoint streaming live system telemetry events and updates at ~1s interval.
    """
    await websocket.accept()
    telemetry_svc = get_telemetry_service()
    queue = telemetry_svc.subscribe()
    logger.info("Telemetry WebSocket client connected")

    try:
        # Initial state send
        initial_data = telemetry_svc.get_full_telemetry()
        await websocket.send_text(json.dumps({"type": "TELEMETRY_FULL", "data": initial_data}))

        while True:
            # Send periodic tick or queued event
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                current_full = telemetry_svc.get_full_telemetry()
                await websocket.send_text(json.dumps({"type": "TELEMETRY_UPDATE", "event": event, "data": current_full}))
            except asyncio.TimeoutError:
                current_full = telemetry_svc.get_full_telemetry()
                await websocket.send_text(json.dumps({"type": "TELEMETRY_TICK", "data": current_full}))

    except WebSocketDisconnect:
        logger.info("Telemetry WebSocket client disconnected")
    except Exception as exc:
        logger.warning(f"Telemetry WebSocket error: {exc}")
    finally:
        telemetry_svc.unsubscribe(queue)


@router.get("/telemetry/stream-sse")
async def telemetry_sse_stream() -> StreamingResponse:
    """
    Server-Sent Events (SSE) streaming endpoint for live telemetry updates.
    """
    telemetry_svc = get_telemetry_service()
    queue = telemetry_svc.subscribe()

    async def event_generator():
        try:
            initial = telemetry_svc.get_full_telemetry()
            yield f"data: {json.dumps({'type': 'TELEMETRY_FULL', 'data': initial})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.5)
                    full = telemetry_svc.get_full_telemetry()
                    payload = json.dumps({'type': 'TELEMETRY_UPDATE', 'event': event, 'data': full})
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    full = telemetry_svc.get_full_telemetry()
                    payload = json.dumps({'type': 'TELEMETRY_TICK', 'data': full})
                    yield f"data: {payload}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            telemetry_svc.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
