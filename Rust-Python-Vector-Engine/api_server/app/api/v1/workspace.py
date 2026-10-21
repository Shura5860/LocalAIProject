from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from api_server.app.services.workspace_service import workspace_service

router = APIRouter(prefix="/workspace", tags=["Project Workspace Hub"])

class BindWorkspaceRequest(BaseModel):
    path: str

@router.get("/status")
def get_workspace_status():
    """Mevcut çalışma alanının durumunu (proje bağlı mı, hangi klasör vb.) döner."""
    return workspace_service.get_status()

@router.post("/bind")
def bind_workspace(req: BindWorkspaceRequest):
    """Belirtilen bir proje klasörünü aktif çalışma alanına bağlar."""
    try:
        res = workspace_service.bind_workspace(req.path)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/unbind")
def unbind_workspace():
    """Proje bağlantısını kaldırır ve genel amaçlı kişisel AI moduna döner."""
    return workspace_service.unbind_workspace()

@router.get("/tree")
def get_file_tree(max_depth: int = 3):
    """Aktif projenin dosya ve dizin hiyerarşisini döner."""
    return workspace_service.get_file_tree(max_depth=max_depth)

@router.post("/index")
def index_project():
    """Aktif projedeki kaynak kodları HNSW vektör veritabanına indeksler."""
    try:
        res = workspace_service.index_project_to_rag()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"İndeksleme hatası: {str(e)}")
