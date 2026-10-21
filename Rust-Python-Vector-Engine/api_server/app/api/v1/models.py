from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from api_server.app.services.model_service import model_service

router = APIRouter(prefix="/models", tags=["Multi-Model Hub"])

class SwitchModelRequest(BaseModel):
    model_id: str

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
