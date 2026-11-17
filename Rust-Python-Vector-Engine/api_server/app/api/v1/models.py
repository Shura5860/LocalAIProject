from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json

from api_server.app.services.model_service import model_service
from api_server.app.services.model_downloader_service import model_downloader

router = APIRouter(prefix="/models", tags=["Multi-Model Hub"])

class SwitchModelRequest(BaseModel):
    model_id: str

class PullModelRequest(BaseModel):
    repo: str
    filename: str
    model_id: Optional[str] = None
    expected_sha256: Optional[str] = None

@router.get("")
def list_models():
    """Katalogdaki tüm modelleri, bellek gereksinimlerini ve aktif durumu listeler."""
    return model_service.list_models()

@router.get("/hardware")
def get_hardware_info():
    """Sistem donanımını (RAM, VRAM) okur ve donanıma en uygun modeli önerir."""
    return model_service.get_hardware_info()

@router.get("/active")
def get_active_model():
    """Şu an aktif olan modelin bilgilerini döner."""
    return model_service.get_active_model_info()

@router.post("/switch")
def switch_model(req: SwitchModelRequest):
    """Aktif kullanılan modeli runtime'da anında değiştirir."""
    try:
        res = model_service.set_active_model(req.model_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/verify/{model_id}")
def verify_model(model_id: str):
    """Belirtilen modelin SHA-256 bütünlüğünü resmi HuggingFace hash'i ile doğrular."""
    try:
        return model_service.verify_model_integrity(model_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/hub/search")
def search_hub(query: str = Query(..., min_length=2), limit: int = 10):
    """Hugging Face Hub üzerinde GGUF modelleri arar."""
    return model_downloader.search_hub(query=query, limit=limit)

@router.post("/pull")
def pull_model(req: PullModelRequest):
    """
    Hugging Face üzerinden yeni bir GGUF modelini canlı SSE akışıyla indirir
    ve tamamlandığında doğrudan runtime kataloğuna ekler.
    """
    def sse_event_stream():
        for event in model_downloader.pull_model_stream(
            repo=req.repo,
            filename=req.filename,
            model_id=req.model_id,
            expected_sha256=req.expected_sha256
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(sse_event_stream(), media_type="text/event-stream")
