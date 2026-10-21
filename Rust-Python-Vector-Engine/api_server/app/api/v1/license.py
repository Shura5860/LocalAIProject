from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from api_server.app.core.licensing import license_manager

router = APIRouter(prefix="/license", tags=["Commercial Licensing"])

class ActivateLicenseRequest(BaseModel):
    license_key: str

@router.get("/status")
def get_license_status():
    """Mevcut makinenin donanım kimliği ve lisans durumunu döndürür."""
    return license_manager.get_current_status()

@router.post("/activate")
def activate_license(req: ActivateLicenseRequest):
    """Müşterinin girdiği lisans anahtarını doğrular ve etkinleştirir."""
    success, message, info = license_manager.save_license(req.license_key)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {
        "status": "success",
        "message": message,
        "license_info": info
    }
