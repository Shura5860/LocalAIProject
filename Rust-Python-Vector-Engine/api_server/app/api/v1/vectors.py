import numpy as np
from fastapi import APIRouter, HTTPException
from api_server.app.core.config import db
from api_server.app.schemas.vectors import InsertBatchRequest, SearchRequest, UpdateVectorRequest

router = APIRouter(prefix="/vectors", tags=["Vectors"])

@router.post("/add")

def add_vectors(req: InsertBatchRequest):
    """Toplu vektör ve metadata ekler (WAL loglamalı)."""
    try:
        vec_array = np.array(req.vectors, dtype=np.float32)
        db.add_batch_with_metadata(req.ids, vec_array, req.metadatas)
        return {"message": f"{len(req.ids)} adet vektör eklendi."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ekleme hatası: {str(e)}")

@router.post("/search")
def search_vectors(req: SearchRequest):
    """Filtreli / Filtresiz HNSW Vektör Araması yapar."""
    try:
        query_array = np.array(req.query_vector, dtype=np.float32)
        results = db.search_filtered(
            query_array,
            req.top_k,
            req.filter_key,
            req.filter_value,
            req.operator
        )
        formatted_results = [
            {
                "id": res[0],
                "distance": float(res[1]),
                "metadata": res[2]
            }
            for res in results
        ]
        return {"count": len(formatted_results), "results": formatted_results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Arama hatası: {str(e)}")

@router.delete("/{vector_id}")
def delete_vector(vector_id: int):
    """Soft-delete (Tombstone) ile vektör siler."""
    success = db.delete_id(vector_id)
    if not success:
        raise HTTPException(status_code=404, detail="ID bulunamadı veya zaten silinmiş.")
    return {"message": f"ID {vector_id} başarıyla silindi."}

@router.put("/{vector_id}")
def update_vector(vector_id: int, req: UpdateVectorRequest):
    """Vektör ve metadatasını günceller ve HNSW indeksini yeniler."""
    try:
        vec_array = np.array(req.vector, dtype=np.float32)
        db.update_id(vector_id, vec_array, req.metadata)
        return {"message": f"ID {vector_id} başarıyla güncellendi."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Güncelleme hatası: {str(e)}")
