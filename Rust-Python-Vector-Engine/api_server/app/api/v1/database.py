import os
from fastapi import APIRouter, HTTPException, Query
from api_server.app.core.config import db, DB_FILE

router = APIRouter(prefix="/db", tags=["Database"])

_ALLOWED_DB_DIR = os.path.realpath(os.path.dirname(os.path.abspath(DB_FILE)))


def _validate_db_path(file_path: str) -> str:
    """Veritabanı dosya yolunun izin verilen veri dizini dışına çıkmasını engeller."""
    raw = os.path.join(_ALLOWED_DB_DIR, file_path) if not os.path.isabs(file_path) else file_path
    resolved = os.path.realpath(raw)
    try:
        common = os.path.commonpath([_ALLOWED_DB_DIR, resolved])
    except ValueError:
        common = ""
    if common != _ALLOWED_DB_DIR:
        raise HTTPException(status_code=403, detail="Güvenlik İhlali: Veritabanı yolu izin verilen dizin dışındadır.")
    return resolved

@router.get("/status")
def get_status():
    """Veritabanı durumunu ve aktif doküman sayısını döner."""
    return {
        "status": "online",
        "active_vectors_count": db.len()
    }

@router.post("/build")
def build_hnsw_index():
    """HNSW arama indeksini oluşturur."""
    try:
        db.build_hnsw_index()
        return {"message": "HNSW indeksi başarıyla inşa edildi."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"İndeks hatası: {str(e)}")

@router.post("/save")
def save_db(file_path: str = Query(DB_FILE)):
    """Veritabanını diske binary olarak kaydeder ve WAL'ı temizler."""
    safe_path = _validate_db_path(file_path)
    try:
        db.save_to_disk(safe_path)
        return {"message": f"Veritabanı '{os.path.basename(safe_path)}' dosyasına kaydedildi, WAL sıfırlandı."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kaydetme hatası: {str(e)}")

@router.post("/load")
def load_db(file_path: str = Query(DB_FILE)):
    """Diskteki dump'ı yükler ve işlenmemiş WAL loglarını üzerine oynatır."""
    safe_path = _validate_db_path(file_path)
    try:
        db.load_from_disk(safe_path)
        return {"message": f"Veritabanı '{os.path.basename(safe_path)}' dosyasından yüklendi."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Yükleme hatası: {str(e)}")

@router.post("/vacuum")
def vacuum_db():
    """Silinen dokümanları fiziksel olarak temizler ve grafı yeniler."""
    try:
        purged_count = db.vacuum()
        return {
            "message": f"Vacuum tamamlandı, {purged_count} adet silinmiş doküman fiziksel olarak temizlendi.",
            "active_vectors_count": db.len()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vacuum hatası: {str(e)}")
