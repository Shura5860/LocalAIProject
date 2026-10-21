import sys
import numpy as np
from sentence_transformers import SentenceTransformer
from vector_engine import VectorIndex

sys.stdout.reconfigure(encoding='utf-8')


def main():
    print("--- 🗑️ Silme (Delete) & ✏️ Güncelleme (Update) Testi ---")
    
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    documents = [
        {"id": 0, "text": "Rust ile yüksek performanslı sistemler yazılır.", "meta": {"lang": "rust"}},
        {"id": 1, "text": "Python veri bilimi ve yapay zeka için harikadır.", "meta": {"lang": "python"}},
        {"id": 2, "text": "JavaScript web geliştirme dünyasının lideridir.", "meta": {"lang": "js"}}
    ]

    texts = [d["text"] for d in documents]
    metas = [d["meta"] for d in documents]
    ids = [d["id"] for d in documents]
    embeddings = model.encode(texts, convert_to_numpy=True).astype(np.float32)

    index = VectorIndex()
    index.add_batch_with_metadata(ids, embeddings, metas)
    index.build_hnsw_index()

    print(f"\n[1] Başlangıçtaki Aktif Doküman Sayısı: {index.len()}")

    # 1. TEST: ID 1 (Python) Silme
    print("\n[2] ID 1 (Python belgesi) siliniyor...")
    index.delete_id(1)
    print(f"   • Silme sonrası aktif doküman sayısı: {index.len()}")

    query = "Yapay zeka ve veri bilimi dili"
    q_vec = model.encode(query, convert_to_numpy=True).astype(np.float32)

    print(f"\n❓ Sorgu: '{query}'")
    results = index.search_filtered(q_vec, top_k=2)
    for doc_id, dist, meta in results:
        print(f"   • Bulunan ID: {doc_id} | Metadata: {meta}")

    # 2. TEST: ID 2 (JavaScript) 'Mojo' Dili İle Güncelleme
    print("\n[3] ID 2 belgesi 'Mojo dili' olarak güncelleniyor...")
    new_text = "Mojo, Python kolaylığında Rust hızında yeni bir yapay zeka dilidir."
    new_vec = model.encode(new_text, convert_to_numpy=True).astype(np.float32)
    new_meta = {"lang": "mojo"}

    index.update_id(2, new_vec, new_meta)

    query_updated = "Mojo ve yapay zeka dilleri"
    q_updated_vec = model.encode(query_updated, convert_to_numpy=True).astype(np.float32)

    print(f"\n❓ Güncelleme Sonrası Sorgu: '{query_updated}'")
    results_updated = index.search_filtered(q_updated_vec, top_k=1)
    for doc_id, dist, meta in results_updated:
        print(f"   • Bulunan ID: {doc_id} | Metadata: {meta}")

if __name__ == "__main__":
    main()