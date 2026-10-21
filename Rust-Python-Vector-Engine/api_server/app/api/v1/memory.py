from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from api_server.app.services.memory_service import memory_service

router = APIRouter(prefix="/memory", tags=["Personalized Memory & Profile"])

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    os: Optional[str] = None
    preferred_languages: Optional[List[str]] = None
    tone: Optional[str] = None
    custom_notes: Optional[List[str]] = None

class RememberFactRequest(BaseModel):
    fact: str
    topic: Optional[str] = "personal"

class RecallRequest(BaseModel):
    query: str
    top_k: int = 3

@router.get("/profile")
def get_user_profile():
    """Kullanıcı profilini ve tercihlerini getirir."""
    return memory_service.get_profile()

@router.post("/profile")
def update_user_profile(req: ProfileUpdateRequest):
    """Kullanıcı profilini günceller."""
    data = {k: v for k, v in req.dict().items() if v is not None}
    return memory_service.update_profile(data)

@router.post("/remember")
def remember_fact(req: RememberFactRequest):
    """Yeni bir bilgiyi/anıyı Rust HNSW vektör hafızasına işler."""
    res = memory_service.remember_fact(fact=req.fact, topic=req.topic)
    return res

@router.post("/recall")
def recall_facts(req: RecallRequest):
    """Verilen sorguyla ilişkili geçmiş hafıza parçalarını listeler."""
    return memory_service.recall_facts(query=req.query, top_k=req.top_k)
