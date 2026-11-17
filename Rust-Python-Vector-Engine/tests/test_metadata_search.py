import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vector_engine import VectorIndex


class TestMetadataSearch(unittest.TestCase):
    def test_filtered_search(self):
        dim = 384
        np.random.seed(101)
        vecs = np.random.randn(5, dim).astype(np.float32)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)

        metadatas = [
            {"category": "yazilim", "year": "2026"},
            {"category": "yazilim", "year": "2025"},
            {"category": "evcil_hayvan", "year": "2026"},
            {"category": "mutfak", "year": "2024"},
            {"category": "mutfak", "year": "2026"}
        ]
        ids = list(range(5))

        index = VectorIndex()
        index.add_batch_with_metadata(ids, vecs, metadatas)
        index.build_hnsw_index()

        # Filtresiz arama
        res_unfiltered = index.search_filtered(vecs[0], top_k=2)
        self.assertEqual(len(res_unfiltered), 2)
        self.assertEqual(res_unfiltered[0][0], 0)

        # Filtreli arama: sadece 'mutfak' kategorisi
        res_filtered = index.search_filtered(
            vecs[0],
            top_k=2,
            filter_key="category",
            filter_value="mutfak"
        )
        self.assertGreaterEqual(len(res_filtered), 1)
        for doc_id, dist, meta in res_filtered:
            self.assertEqual(meta.get("category"), "mutfak")


if __name__ == "__main__":
    unittest.main()
