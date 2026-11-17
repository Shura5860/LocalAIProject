import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vector_engine import VectorIndex


class TestSemanticSearch(unittest.TestCase):
    def test_semantic_search_with_embeddings(self):
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        except Exception as e:
            self.skipTest(f"SentenceTransformer modeli yüklenemedi (çevrimdışı/indirilmemiş): {e}")

        documents = [
            "Sokak kedileri soğuk havalarda sığınacak sıcak bir yer ararlar.",
            "Yapay zeka ve derin öğrenme teknolojileri yazılım dünyasını değiştiriyor.",
            "Espresso ve filtre kahve güne zinde başlamak için sıkça tercih edilir."
        ]

        embeddings = model.encode(documents, convert_to_numpy=True).astype(np.float32)
        index = VectorIndex()
        ids = list(range(len(documents)))
        index.add_batch_with_metadata(ids, embeddings, [{} for _ in ids])
        index.build_hnsw_index()

        query = "Bilgisayarlı öğrenme ve algoritmalar"
        q_vec = model.encode(query, convert_to_numpy=True).astype(np.float32)

        results = index.search_filtered(q_vec, top_k=1)
        self.assertEqual(len(results), 1)
        # 1. indeks ("Yapay zeka ve derin öğrenme...") en yakın olmalı
        self.assertEqual(results[0][0], 1)


if __name__ == "__main__":
    unittest.main()
