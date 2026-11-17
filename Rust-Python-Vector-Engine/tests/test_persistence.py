import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vector_engine import VectorIndex

TEST_PERSIST_DB = "test_persist_db.bin"


class TestVectorPersistence(unittest.TestCase):
    def tearDown(self):
        if os.path.exists(TEST_PERSIST_DB):
            try:
                os.remove(TEST_PERSIST_DB)
            except Exception:
                pass

    def test_save_and_load_disk(self):
        dim = 384
        np.random.seed(123)
        vecs = np.random.randn(3, dim).astype(np.float32)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        metas = [{"category": "yazilim"}, {"category": "donanim"}, {"category": "mutfak"}]
        ids = [0, 1, 2]

        index = VectorIndex()
        index.add_batch_with_metadata(ids, vecs, metas)
        index.build_hnsw_index()
        self.assertEqual(index.len(), 3)

        # Diske Kaydet
        index.save_to_disk(TEST_PERSIST_DB)
        self.assertTrue(os.path.exists(TEST_PERSIST_DB))

        # Yeni boş index ile diskten yükle
        loaded_index = VectorIndex()
        loaded_index.load_from_disk(TEST_PERSIST_DB)
        self.assertEqual(loaded_index.len(), 3)

        # Sorgu doğrulaması
        res = loaded_index.search_filtered(vecs[0], top_k=1)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0][0], 0)
        self.assertEqual(res[0][2], {"category": "yazilim"})


if __name__ == "__main__":
    unittest.main()
