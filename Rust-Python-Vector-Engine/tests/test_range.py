import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vector_engine import VectorIndex


class TestVectorRangeFilter(unittest.TestCase):
    def test_numeric_range_filtering(self):
        dim = 384
        np.random.seed(88)
        vecs = np.random.randn(4, dim).astype(np.float32)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)

        metas = [
            {"year": "2024", "score": "8.2"},
            {"year": "2026", "score": "9.5"},
            {"year": "2026", "score": "9.8"},
            {"year": "2020", "score": "6.0"}
        ]
        ids = [0, 1, 2, 3]

        index = VectorIndex()
        index.add_batch_with_metadata(ids, vecs, metas)
        index.build_hnsw_index()

        # 1. Yıl Filtresi (year >= 2026) -> IDs 1 ve 2
        results_year = index.search_filtered(vecs[1], top_k=5, filter_key="year", filter_value="2026", operator=">=")
        found_year_ids = {r[0] for r in results_year}
        self.assertTrue(found_year_ids.issubset({1, 2}))
        self.assertNotIn(0, found_year_ids)
        self.assertNotIn(3, found_year_ids)

        # 2. Skor Filtresi (score > 9.0) -> IDs 1 ve 2
        results_score = index.search_filtered(vecs[1], top_k=5, filter_key="score", filter_value="9.0", operator=">")
        found_score_ids = {r[0] for r in results_score}
        self.assertTrue(found_score_ids.issubset({1, 2}))


if __name__ == "__main__":
    unittest.main()
