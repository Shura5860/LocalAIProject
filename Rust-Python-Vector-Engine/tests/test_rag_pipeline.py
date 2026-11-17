import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.services.rag_service import rag_service
from api_server.app.core.config import db


class TestRAGPipeline(unittest.TestCase):
    def test_rag_ingest_and_query(self):
        test_docs = [
            "Proje A, Rust dili ve AVX2 SIMD donanım optimizasyonları ile geliştirilmiş yüksek performanslı bir LLM çıkarım motorudur.",
            "Proje B, PyO3 FFI ve instant-distance HNSW grafı kullanan, WAL çökme dayanıklılığına sahip hibrit bir vektör veritabanıdır.",
            "Ofis içindeki kahve makinesinin şifresi 2026'dır ve her ayın ilk pazartesi günü temizlik bakımı yapılır."
        ]
        metas = [
            {"topic": "rust-llm", "category": "tech"},
            {"topic": "vector-engine", "category": "tech"},
            {"topic": "office-info", "category": "general"}
        ]

        indexed_count = rag_service.ingest_documents(test_docs, metas)
        self.assertEqual(indexed_count, len(test_docs))
        self.assertGreaterEqual(db.len(), len(test_docs))

        q = "Kahve makinesinin şifresi nedir ve bakımı ne zaman yapılır?"
        result = rag_service.query(user_query=q, top_k=2)

        self.assertIn("answer", result)
        self.assertIn("retrieved_chunks", result)
        self.assertGreaterEqual(len(result["retrieved_chunks"]), 1)
        self.assertEqual(result.get("retrieval_mode"), "hybrid_rrf_bm25_hnsw")
        self.assertIn("rrf_score", result["retrieved_chunks"][0])

    def test_structural_code_chunking(self):
        sample_code = (
            "// Top level comment\n\n"
            "struct UserProfile {\n"
            "    name: String,\n"
            "    tier: u32,\n"
            "}\n\n"
            "impl UserProfile {\n"
            "    pub fn new(name: &str) -> Self {\n"
            "        Self { name: name.to_string(), tier: 1 }\n"
            "    }\n"
            "    pub fn upgrade(&mut self) {\n"
            "        self.tier += 1;\n"
            "    }\n"
            "}\n"
        )
        chunks = rag_service.chunk_code(sample_code, filename="user.rs", max_chunk_lines=10)
        self.assertGreaterEqual(len(chunks), 1)
        for c in chunks:
            self.assertEqual(c["filename"], "user.rs")
            self.assertIn("start_line", c)
            self.assertIn("end_line", c)
            self.assertIn("scope", c)


if __name__ == "__main__":
    unittest.main()
