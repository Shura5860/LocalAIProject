from pydantic import BaseModel
from typing import List, Dict, Optional, Any

class IngestDocumentRequest(BaseModel):
    documents: List[str]
    metadatas: Optional[List[Dict[str, str]]] = None

class IngestDocumentResponse(BaseModel):
    indexed_count: int
    total_documents: int
    message: str

class RagQueryRequest(BaseModel):
    query: str
    top_k: int = 3
    filter_key: Optional[str] = None
    filter_value: Optional[str] = None
    max_tokens: int = 256
    temperature: float = 0.7

class RetrievedChunk(BaseModel):
    id: int
    distance: float
    text: str
    metadata: Dict[str, str]

class RagQueryResponse(BaseModel):
    query: str
    answer: str
    retrieved_chunks: List[RetrievedChunk]
    llm_engine: str
