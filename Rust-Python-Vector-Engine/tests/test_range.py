import sys
import numpy as np
from sentence_transformers import SentenceTransformer
from vector_engine import VectorIndex

sys.stdout.reconfigure(encoding='utf-8')


def main():
    print("--- 🔢 Sayısal Aralık (Range) Filtreleme Testi ---")
    
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    documents = [
        {"id": 0, "text": "Python 3.13 performans iyileştirmeleri içerir.", "meta": {"year": "2024", "score": "8.2"}},
        {"id": 1, "text": "Rust 2026 modern sistem programlama standartları.", "meta": {"year": "2026", "score": "9.5"}},
        {"id": 2, "text": "Geleceğin yapay zeka mimarileri ve vektör motorları.", "meta": {"year": "2026", "score": "9.8"}},
        {"id": 3, "text": "Eski yazılım mimarileri ve teknik borç yönetimi.", "meta": {"year": "2020", "score": "6.0"}}
    ]

    texts = [d["text"] for d in documents]
    metas = [d["meta"] for d in documents]
    ids = [d["id"] for d in documents]
    embeddings = model.encode(texts, convert_to_numpy=True).astype(np.float32)

    index = VectorIndex()
    index.add_batch_with_metadata(ids, embeddings, metas)
    index.build_hnsw_index()

    query = "Programlama ve yazılım mimarisi"
    q_vec = model.encode(query, convert_to_numpy=True).astype(np.float32)

    # 1. TEST: Yıl Filtresi (year >= 2026)
    print(f"\n❓ Sorgu: '{query}' -> 🎯 FİLTRE: year >= 2026")
    results_year = index.search_filtered(q_vec, top_k=5, filter_key="year", filter_value="2026", operator=">=")
    for doc_id, dist, meta in results_year:
        print(f"   • [{documents[doc_id]['text']}] | Metadata: {meta}")

    # 2. TEST: Kalite Puanı Filtresi (score > 9.0)
    print(f"\n❓ Sorgu: '{query}' -> 🎯 FİLTRE: score > 9.0")
    results_score = index.search_filtered(q_vec, top_k=5, filter_key="score", filter_value="9.0", operator=">")
    for doc_id, dist, meta in results_score:
        print(f"   • [{documents[doc_id]['text']}] | Metadata: {meta}")

if __name__ == "__main__":
    main()