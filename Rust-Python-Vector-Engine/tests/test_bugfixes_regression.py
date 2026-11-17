import sys
import os
import unittest
import tempfile
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.main import app
from api_server.app.core.config import allocate_doc_ids
from api_server.app.tools.devops import _validate_safe_path, _get_base_workspace
from api_server.app.services.rag_service import RagService
from api_server.app.services.inference_engine import ProductionInferenceEngine


class TestBugfixesRegression(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_path_traversal_prefix_bypass_blocked(self):
        base_ws = _get_base_workspace()
        evil_sibling = base_ws + "_EVIL/malicious.py"
        with self.assertRaises(PermissionError):
            _validate_safe_path(evil_sibling)

    def test_monotonic_doc_id_no_collision(self):
        ids_batch_1 = allocate_doc_ids(3)
        ids_batch_2 = allocate_doc_ids(2)
        self.assertEqual(len(ids_batch_1), 3)
        self.assertEqual(len(ids_batch_2), 2)
        self.assertGreater(ids_batch_2[0], ids_batch_1[-1])

    def test_bm25_sparse_index_persistence(self):
        rag = RagService()
        rag.ingest_documents(["Rust HNSW vektör motoru çok hızlıdır."], [{"source": "test"}])

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            rag.save_sparse_index(tmp_path)
            self.assertTrue(os.path.exists(tmp_path))

            rag2 = RagService()
            rag2.load_sparse_index(tmp_path)
            self.assertGreater(len(rag2._doc_store), 0)
            self.assertIn("hnsw", rag2._inverted_index)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_inference_engine_lock_and_sliding_truncation(self):
        engine = ProductionInferenceEngine()
        self.assertIsNotNone(engine._lock)
        long_prompt = "SYSTEM_START " + ("x" * 10000) + " USER_END"
        truncated = engine._truncate_prompt_sliding(long_prompt, max_chars=2000)
        self.assertLessEqual(len(truncated), 2100)
        self.assertTrue(truncated.startswith("SYSTEM_START"))
        self.assertTrue(truncated.endswith("USER_END"))

    def test_health_and_root_endpoints(self):
        res_health = self.client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json()["status"], "online")

        res_root = self.client.get("/")
        self.assertEqual(res_root.status_code, 200)


if __name__ == "__main__":
    unittest.main()

