import os
import sys
import unittest
import concurrent.futures
import random
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vector_engine import VectorIndex


class TestVectorThreadSafety(unittest.TestCase):
    def test_concurrent_readers_and_writers(self):
        dim = 384
        np.random.seed(42)
        base_vecs = np.random.randn(3, dim).astype(np.float32)
        base_vecs /= np.linalg.norm(base_vecs, axis=1, keepdims=True)

        index = VectorIndex()
        index.add_batch_with_metadata([1, 2, 3], base_vecs, [{"cat": "dev"} for _ in range(3)])
        index.build_hnsw_index()

        def reader():
            for _ in range(10):
                q = np.random.randn(dim).astype(np.float32)
                q /= np.linalg.norm(q)
                res = index.search_filtered(q, top_k=2)
                self.assertIsNotNone(res)

        def writer(w_id):
            for i in range(3):
                v = np.random.randn(dim).astype(np.float32)
                v /= np.linalg.norm(v)
                doc_id = w_id * 100 + i + 10
                index.add_batch_with_metadata([doc_id], v.reshape(1, -1), [{"cat": "dyn"}])
                index.build_hnsw_index()

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = []
            for i in range(3):
                futures.append(executor.submit(reader))
            for i in range(3):
                futures.append(executor.submit(writer, i))

            for f in concurrent.futures.as_completed(futures):
                f.result()

        self.assertGreaterEqual(index.len(), 3)


if __name__ == "__main__":
    unittest.main()
