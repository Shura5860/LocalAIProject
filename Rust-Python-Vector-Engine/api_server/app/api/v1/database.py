from fastapi import APIRouter, HTTPException, Query
from api_server.app.core.config import db, DB_FILE

router = APIRouter(prefix="/db", tags=["Database"])

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
    try:
        db.save_to_disk(file_path)
        return {"message": f"Veritabanı '{file_path}' dosyasına kaydedildi, WAL sıfırlandı."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kaydetme hatası: {str(e)}")

@router.post("/load")
def load_db(file_path: str = Query(DB_FILE)):
    """Diskteki dump'ı yükler ve işlenmemiş WAL loglarını üzerine oynatır."""
    try:
        db.load_from_disk(file_path)
        return {"message": f"Veritabanı '{file_path}' dosyasından yüklendi."}
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
