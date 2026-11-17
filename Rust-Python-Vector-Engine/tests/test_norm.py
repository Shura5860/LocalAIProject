import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vector_engine import VectorIndex


class TestVectorNorm(unittest.TestCase):
    def test_normalization_and_cosine_distance(self):
        dim = 384
        np.random.seed(42)
        # 1. ve 2. vektörler çok yakın, 3. vektör zıt/uzak
        base = np.random.randn(dim).astype(np.float32)
        base /= np.linalg.norm(base)

        similar = base + 0.05 * np.random.randn(dim).astype(np.float32)
        similar /= np.linalg.norm(similar)

        distant = -base + 0.05 * np.random.randn(dim).astype(np.float32)
        distant /= np.linalg.norm(distant)

        vecs = np.vstack([base, similar, distant])
        ids = [1, 2, 3]

        index = VectorIndex()
        index.add_batch_with_metadata(ids, vecs, [{} for _ in ids])
        index.build_hnsw_index()

        results = index.search_filtered(base, top_k=3)
        self.assertEqual(len(results), 3)
        # İlk sonuç kendisi olmalı (dist ~ 0)
        self.assertEqual(results[0][0], 1)
        self.assertAlmostEqual(results[0][1], 0.0, places=4)
        # İkinci sonuç en yakın vektör olmalı (ID 2)
        self.assertEqual(results[1][0], 2)
        # Üçüncü sonuç en uzak vektör olmalı (ID 3)
        self.assertEqual(results[2][0], 3)
        self.assertGreater(results[2][1], results[1][1])


if __name__ == "__main__":
    unittest.main()
