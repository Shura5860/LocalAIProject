import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vector_engine import VectorIndex

TEST_DB_FILE = "test_temp_wal_db.bin"
TEST_WAL_FILE = "test_temp_wal_db.wal"


class TestVectorWAL(unittest.TestCase):
    def tearDown(self):
        for f in [TEST_DB_FILE, TEST_WAL_FILE]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    def test_wal_crash_recovery(self):
        # 1. Veri Ekleniyor ve save_to_disk çağrılmadan çökme simüle ediliyor
        dim = 384
        np.random.seed(99)
        vec = np.random.randn(dim).astype(np.float32)
        vec /= np.linalg.norm(vec)

        index1 = VectorIndex()
        index1.enable_wal(TEST_WAL_FILE)
        index1.add_batch_with_metadata([999], vec.reshape(1, -1), [{"status": "critical"}])
        index1.build_hnsw_index()
        # save_to_disk çağrılmadı! WAL dosyasına yazıldı.
        del index1

        self.assertTrue(os.path.exists(TEST_WAL_FILE))

        # 2. Kurtarma Aşaması (Yeni instance açılıyor)
        index2 = VectorIndex()
        index2.enable_wal(TEST_WAL_FILE)
        # load_from_disk mevcut olmayan base dosya olsa bile WAL replay yapmalıdır
        index2.load_from_disk(TEST_DB_FILE)
        self.assertGreaterEqual(index2.len(), 1)

        results = index2.search_filtered(vec, top_k=1)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0][0], 999)
        self.assertEqual(results[0][2], {"status": "critical"})


if __name__ == "__main__":
    unittest.main()
