import os
import sys
import time
import numpy as np
from sentence_transformers import SentenceTransformer
from vector_engine import VectorIndex

sys.stdout.reconfigure(encoding='utf-8')

DB_FILE = "my_vector_db.bin"

def main():
    print("--- 💾 Diske Kaydetme & Yükleme Testi ---")
    
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    # AŞAMA 1: İndeks Oluşturma ve Diske Kaydetme
    print("\n[1] Veriler hazırlanıyor ve HNSW indeksi oluşturuluyor...")
    documents = [
        {"text": "Python ve Rust ile sistem programlama yapılır.", "meta": {"category": "yazilim"}},
        {"text": "Dizüstü bilgisayar seçiminde RAM ve İşlemci önemlidir.", "meta": {"category": "donanim"}},
        {"text": "Kahve çekirdekleri taze öğütüldüğünde lezzeti artar.", "meta": {"category": "mutfak"}}
    ]

    texts = [d["text"] for d in documents]
    metas = [d["meta"] for d in documents]
    embeddings = model.encode(texts, convert_to_numpy=True).astype(np.float32)

    index = VectorIndex()
    index.add_batch_with_metadata(list(range(len(documents))), embeddings, metas)
    index.build_hnsw_index()

    # Diske Kaydetme
    print(f"\n[2] İndeks '{DB_FILE}' dosyasına kaydediliyor...")
    index.save_to_disk(DB_FILE)
    
    file_size_kb = os.path.getsize(DB_FILE) / 1024
    print(f"✅ Başarıyla Kaydedildi! Dosya Boyutu: {file_size_kb:.2f} KB (Neredeyse hiç yer kaplamadı!)")

    # AŞAMA 2: Diskten Sıfırdan Yükleme (Re-building Yapmadan)
    print("\n[3] Yepyeni boş bir motor oluşturulup diskten yükleniyor...")
    new_index = VectorIndex()
    
    start_load = time.time()
    new_index.load_from_disk(DB_FILE)
    load_time_ms = (time.time() - start_load) * 1000
    
    print(f"🚀 İndeks Diskten Yüklendi! Süre: {load_time_ms:.2f} ms | Toplam Veri: {new_index.len()}")

    # AŞAMA 3: Yüklenen İndekste Arama
    print("\n[4] Yüklenen indeks üzerinde test araması yapılıyor...")
    query = "Kodlama ve yazılım geliştirme"
    query_vec = model.encode(query, convert_to_numpy=True).astype(np.float32)
    
    results = new_index.search_filtered(query_vec, top_k=1)
    for doc_id, dist, meta in results:
        print(f"   • Bulunan Belge ID: {doc_id} | Metin: [{documents[doc_id]['text']}] | Metadata: {meta}")

if __name__ == "__main__":
    main()