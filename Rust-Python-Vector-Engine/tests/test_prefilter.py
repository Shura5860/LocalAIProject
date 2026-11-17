import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vector_engine import VectorIndex


class TestVectorPrefilter(unittest.TestCase):
    def test_prefilter_operators(self):
        dim = 384
        np.random.seed(55)
        vecs = np.random.randn(4, dim).astype(np.float32)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)

        metas = [
            {"category": "yazilim"},
            {"category": "mutfak"},
            {"category": "yazilim"},
            {"category": "mutfak"}
        ]
        ids = [1, 2, 3, 4]

        index = VectorIndex()
        index.add_batch_with_metadata(ids, vecs, metas)
        index.build_hnsw_index()

        # Eşleşen filtre
        res = index.search_filtered(vecs[1], top_k=2, filter_key="category", filter_value="mutfak", operator="==")
        self.assertGreaterEqual(len(res), 1)
        for doc_id, dist, meta in res:
            self.assertEqual(meta.get("category"), "mutfak")

        # Var olmayan filtre
        res_empty = index.search_filtered(vecs[1], top_k=2, filter_key="category", filter_value="uzay", operator="==")
        self.assertEqual(len(res_empty), 0)


if __name__ == "__main__":
    unittest.main()
