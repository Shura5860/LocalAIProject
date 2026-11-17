import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vector_engine import VectorIndex


class TestVectorCRUD(unittest.TestCase):
    def setUp(self):
        self.dim = 384
        # Deterministic random vectors for fast offline unit testing
        np.random.seed(42)
        v0 = np.random.randn(self.dim).astype(np.float32)
        v0 /= np.linalg.norm(v0)
        v1 = np.random.randn(self.dim).astype(np.float32)
        v1 /= np.linalg.norm(v1)
        v2 = np.random.randn(self.dim).astype(np.float32)
        v2 /= np.linalg.norm(v2)

        self.ids = [0, 1, 2]
        self.vectors = np.vstack([v0, v1, v2])
        self.metas = [{"lang": "rust"}, {"lang": "python"}, {"lang": "js"}]

        self.index = VectorIndex()
        self.index.add_batch_with_metadata(self.ids, self.vectors, self.metas)
        self.index.build_hnsw_index()

    def test_initial_length(self):
        self.assertEqual(self.index.len(), 3)

    def test_delete_id(self):
        self.index.delete_id(1)
        self.assertEqual(self.index.len(), 2)
        results = self.index.search_filtered(self.vectors[1], top_k=2)
        found_ids = [r[0] for r in results]
        self.assertNotIn(1, found_ids)

    def test_update_id(self):
        new_vec = np.random.randn(self.dim).astype(np.float32)
        new_vec /= np.linalg.norm(new_vec)
        new_meta = {"lang": "mojo"}
        self.index.update_id(2, new_vec, new_meta)

        results = self.index.search_filtered(new_vec, top_k=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], 2)
        self.assertEqual(results[0][2], {"lang": "mojo"})


if __name__ == "__main__":
    unittest.main()
