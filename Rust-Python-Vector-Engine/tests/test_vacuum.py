import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vector_engine import VectorIndex


class TestVectorVacuum(unittest.TestCase):
    def test_vacuum_purges_deleted_records(self):
        dim = 384
        np.random.seed(77)
        vecs = np.random.randn(3, dim).astype(np.float32)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        metas = [{"lang": "python"}, {"lang": "rust"}, {"lang": "js"}]
        ids = [0, 1, 2]

        index = VectorIndex()
        index.add_batch_with_metadata(ids, vecs, metas)
        index.build_hnsw_index()
        self.assertEqual(index.len(), 3)

        # Soft delete ID 1
        index.delete_id(1)
        self.assertEqual(index.len(), 2)

        # Physical vacuum / compaction
        purged = index.vacuum()
        self.assertEqual(purged, 1)
        self.assertEqual(index.len(), 2)

        # Ensure deleted vector cannot be found
        res = index.search_filtered(vecs[1], top_k=2)
        found_ids = [r[0] for r in res]
        self.assertNotIn(1, found_ids)


if __name__ == "__main__":
    unittest.main()
