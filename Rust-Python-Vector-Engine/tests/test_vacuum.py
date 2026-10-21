import sys
import numpy as np
from sentence_transformers import SentenceTransformer
from vector_engine import VectorIndex

sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("--- 🧹 Vacuum / Compaction Testi ---")
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    documents = [
        {"id": 0, "text": "Python programlama dili", "meta": {"lang": "python"}},
        {"id": 1, "text": "Rust sistem programlama dili", "meta": {"lang": "rust"}},
        {"id": 2, "text": "JavaScript web geliştirme", "meta": {"lang": "js"}}
    ]

    texts = [d["text"] for d in documents]
    metas = [d["meta"] for d in documents]
    ids = [d["id"] for d in documents]
    embeddings = model.encode(texts, convert_to_numpy=True).astype(np.float32)

    index = VectorIndex()
    index.add_batch_with_metadata(ids, embeddings, metas)
    index.build_hnsw_index()

    print(f"[1] Başlangıç Doküman Sayısı: {index.len()}")

    # Silme işlemi (Soft Delete)
    print("\n[2] ID 1 (Rust) siliniyor (Tombstone ekleniyor)...")
    index.delete_id(1)
    print(f"   • Silme sonrası aktif doküman sayısı: {index.len()}")

    # Vacuum çağrısı
    print("\n[3] 'vacuum()' çalıştırılıyor (Fiziksel temizlik & graf yenileme)...")
    purged_count = index.vacuum()
    print(f"   • Temizlenen Silinmiş Doküman Sayısı: {purged_count}")
    print(f"   • Vacuum Sonrası Aktif Doküman Sayısı: {index.len()}")

    # Arama testi
    query = "sistem programlama"
    q_vec = model.encode(query, convert_to_numpy=True).astype(np.float32)
    results = index.search_filtered(q_vec, top_k=2)

    print(f"\n❓ Vacuum Sonrası Sorgu: '{query}'")
    for doc_id, dist, meta in results:
        print(f"   • Bulunan ID: {doc_id} | Metadata: {meta}")

if __name__ == "__main__":
    main()
