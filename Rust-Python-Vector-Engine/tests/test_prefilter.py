import sys
import numpy as np
from sentence_transformers import SentenceTransformer
from vector_engine import VectorIndex

sys.stdout.reconfigure(encoding='utf-8')


def main():
    print("--- 🎯 Inverted Index Pre-Filtering Testi ---")
    
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    documents = [
        {"id": 1, "text": "Python ve Rust performans karşılaştırması", "meta": {"category": "yazilim"}},
        {"id": 2, "text": "Napoliten Pizza ve İtalyan Mutfağı", "meta": {"category": "mutfak"}},
        {"id": 3, "text": "C++ ile oyun motoru geliştirme", "meta": {"category": "yazilim"}},
        {"id": 4, "text": "Espresso ve filtre kahve demleme teknikleri", "meta": {"category": "mutfak"}}
    ]

    texts = [d["text"] for d in documents]
    metas = [d["meta"] for d in documents]
    ids = [d["id"] for d in documents]
    embeddings = model.encode(texts, convert_to_numpy=True).astype(np.float32)

    index = VectorIndex()
    index.add_batch_with_metadata(ids, embeddings, metas)
    index.build_hnsw_index()

    # TEST 1: Eşleşen Filtre
    query = "Kahve ve kodlama"
    q_vec = model.encode(query, convert_to_numpy=True).astype(np.float32)

    print(f"\n❓ Sorgu: '{query}' -> 🎯 FİLTRE: category = 'mutfak'")
    results = index.search_filtered(q_vec, top_k=2, filter_key="category", filter_value="mutfak", operator="==")
    
    for doc_id, dist, meta in results:
        print(f"   • Bulunan ID: {doc_id} | Metadata: {meta}")

    # TEST 2: Var Olmayan Filtre (Pre-filtering O(1) Hızında Boş Dönecek)
    print(f"\n❓ Sorgu: '{query}' -> 🎯 FİLTRE: category = 'uzay' (Var Olmayan Kategori)")
    results_empty = index.search_filtered(q_vec, top_k=2, filter_key="category", filter_value="uzay", operator="==")
    print(f"   • Bulunan Sonuç Sayısı: {len(results_empty)} (O(1) süreyle saniyesinde elendi!)")

if __name__ == "__main__":
    main()