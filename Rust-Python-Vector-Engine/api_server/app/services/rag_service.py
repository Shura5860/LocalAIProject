import numpy as np
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
from api_server.app.core.config import db
from api_server.app.services.llm_bridge import RustLLMBridge

class RagService:
    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.embedding_model_name = model_name
        self._embedder: Optional[SentenceTransformer] = None
        self.llm_bridge = RustLLMBridge()

    @property
    def embedder(self) -> SentenceTransformer:
        if self._embedder is None:
            self._embedder = SentenceTransformer(self.embedding_model_name)
        return self._embedder

    def ingest_documents(self, documents: List[str], metadatas: Optional[List[Dict[str, str]]] = None) -> int:
        if not documents:
            return 0

        embeddings = self.embedder.encode(documents, convert_to_numpy=True).astype(np.float32)

        start_id = db.len()
        ids = list(range(start_id, start_id + len(documents)))

        prepared_metas = []
        for i, text in enumerate(documents):
            meta = metadatas[i].copy() if (metadatas and i < len(metadatas)) else {}
            meta["text"] = text
            prepared_metas.append(meta)

        db.add_batch_with_metadata(ids, embeddings, prepared_metas)
        db.build_hnsw_index()
        return len(documents)

    def query(
        self,
        user_query: str,
        top_k: int = 3,
        filter_key: Optional[str] = None,
        filter_value: Optional[str] = None,
        max_tokens: int = 256
    ) -> Dict:
        if db.len() == 0:
            return {
                "query": user_query,
                "answer": "Veritabanında henüz indekslenmiş belge bulunmuyor. Lütfen önce `/rag/ingest` ile belge yükleyin.",
                "retrieved_chunks": [],
                "llm_engine": "Rust-LLM-Engine (AVX2/FMA SIMD CPU)"
            }

        query_vector = self.embedder.encode(user_query, convert_to_numpy=True).astype(np.float32)

        raw_results = db.search_filtered(
            query_vector,
            top_k=top_k,
            filter_key=filter_key,
            filter_value=filter_value,
            operator="==" if filter_key else None
        )

        retrieved_chunks = []
        context_parts = []
        for doc_id, dist, meta in raw_results:
            text = meta.get("text", "")
            retrieved_chunks.append({
                "id": doc_id,
                "distance": float(dist),
                "text": text,
                "metadata": meta
            })
            if text:
                context_parts.append(f"- {text}")

        context_str = "\n".join(context_parts) if context_parts else "İlgili belge bulunamadı."
        
        from api_server.app.services.memory_service import memory_service
        memory_ctx = memory_service.build_memory_prompt(user_query)

        prompt = (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
            f"Sen yüksek performanslı bir yapay zeka asistanısın. Aşağıdaki bağlam ve kullanıcı hafıza bilgilerini dikkatle incele ve kullanıcının sorusunu bu bilgilere dayanarak yanıtla. Eğer cevap bağlamda yoksa uydurma yapma, bunu açıkça belirt.\n\n"
            f"{memory_ctx}\n"
            f"BAĞLAM:\n{context_str}<|eot_id|>\n"
            f"<|start_header_id|>user<|end_header_id|>\n"
            f"{user_query}<|eot_id|>\n"
            f"<|start_header_id|>assistant<|end_header_id|>\n"
        )

        answer = self.llm_bridge.generate(prompt, max_tokens=max_tokens)

        return {
            "query": user_query,
            "answer": answer,
            "retrieved_chunks": retrieved_chunks,
            "llm_engine": "Rust-LLM-Engine (AVX2/FMA SIMD CPU)"
        }

rag_service = RagService()
