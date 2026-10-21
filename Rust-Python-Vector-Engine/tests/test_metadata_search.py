import sys
import time
import numpy as np
from sentence_transformers import SentenceTransformer
from vector_engine import VectorIndex

sys.stdout.reconfigure(encoding='utf-8')


def main():
    print("--- 🏷️ Metadata Filtreli Anlamsal Vektör Araması ---")

    # 1. Model Yükleme
    print("\n[1] Yapay zeka modeli yükleniyor...")
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    # 2. Veri Seti (Metin + Metadata)
    documents = [
        {"text": "Python ve Rust ile yüksek performanslı sistemler geliştirilir.", "meta": {"category": "yazilim", "year": "2026"}},
        {"text": "Yapay zeka modelleri vektör veritabanları ile desteklenir.", "meta": {"category": "yazilim", "year": "2025"}},
        {"text": "Sokak kedileri ve köpekler soğukta barınak arar.", "meta": {"category": "evcil_hayvan", "year": "2026"}},
        {"text": "İtalyan restoranlarında Napoliten pizza ve makarna meşhurdur.", "meta": {"category": "mutfak", "year": "2024"}},
        {"text": "Espresso ve demleme kahve çeşitleri güne hızlı başlatır.", "meta": {"category": "mutfak", "year": "2026"}}
    ]

    texts = [doc["text"] for doc in documents]
    metadatas = [doc["meta"] for doc in documents]

    # 3. Vektörleştirme
    print("\n[2] Vektörler üretiliyor...")
    embeddings = model.encode(texts, convert_to_numpy=True).astype(np.float32)

    # 4. Rust Motoruna Yükleme
    index = VectorIndex()
    ids = list(range(len(documents)))
    index.add_batch_with_metadata(ids, embeddings, metadatas)
    index.build_hnsw_index()

    # 5. TEST 1: Filtresiz Arama
    query_text = "Hangi sistemler ve diller kullanılır?"
    print(f"\n❓ Sorgu: \"{query_text}\" (FİLTRESİZ)")
    query_vector = model.encode(query_text, convert_to_numpy=True).astype(np.float32)
    
    results = index.search_filtered(query_vector, top_k=2, filter_key=None, filter_value=None)
    for doc_id, dist, meta in results:
        print(f"   • [{documents[doc_id]['text']}] | Metadata: {meta}")

    # 6. TEST 2: Sadece 'yazilim' Kategorisi Filtresi
    print(f"\n❓ Sorgu: \"Geliştirme ve yemekler\" -> 🎯 FİLTRE: category='mutfak'")
    results_filtered = index.search_filtered(
        query_vector, 
        top_k=2, 
        filter_key="category", 
        filter_value="mutfak"
    )
    for doc_id, dist, meta in results_filtered:
        print(f"   • [{documents[doc_id]['text']}] | Metadata: {meta}")

if __name__ == "__main__":
    main()