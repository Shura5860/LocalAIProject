from typing import Dict, List, Optional
from pydantic import BaseModel

class InsertBatchRequest(BaseModel):
    ids: List[int]
    vectors: List[List[float]]
    metadatas: List[Dict[str, str]]

class UpdateVectorRequest(BaseModel):
    vector: List[float]
    metadata: Dict[str, str]

class SearchRequest(BaseModel):
    query_vector: List[float]
    top_k: int = 5
    filter_key: Optional[str] = None
    filter_value: Optional[str] = None
    operator: Optional[str] = "=="
