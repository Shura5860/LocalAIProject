from fastapi import APIRouter, HTTPException
from api_server.app.schemas.rag import (
    IngestDocumentRequest,
    IngestDocumentResponse,
    RagQueryRequest,
    RagQueryResponse
)
from api_server.app.services.rag_service import rag_service
from api_server.app.core.config import db

router = APIRouter(prefix="/rag", tags=["RAG (Retrieval-Augmented Generation)"])

@router.post("/ingest", response_model=IngestDocumentResponse)
def ingest_documents(req: IngestDocumentRequest):
    """
    Belgeleri parçalayıp yerel embedding modeli ile vektörleştirir ve
    Rust HNSW vektör indeksine ekler.
    """
    try:
        count = rag_service.ingest_documents(req.documents, req.metadatas)
        return IngestDocumentResponse(
            indexed_count=count,
            total_documents=db.len(),
            message=f"{count} adet belge başarıyla vektörleştirildi ve HNSW indeksine işlendi."
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Doküman indeksleme hatası: {str(e)}")

@router.post("/ask", response_model=RagQueryResponse)
def ask_question(req: RagQueryRequest):
    """
    Kullanıcı sorusu için Rust HNSW motorunda anlamsal arama yapar,
    ilgili belgeleri bağlam olarak Rust LLM motoruna ileterek cevap üretir.
    """
    try:
        result = rag_service.query(
            user_query=req.query,
            top_k=req.top_k,
            filter_key=req.filter_key,
            filter_value=req.filter_value,
            max_tokens=req.max_tokens
        )
        return RagQueryResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG sorgu hatası: {str(e)}")
