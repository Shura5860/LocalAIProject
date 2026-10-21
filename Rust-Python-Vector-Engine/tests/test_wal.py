import os
import sys
import numpy as np
from sentence_transformers import SentenceTransformer
from vector_engine import VectorIndex

DB_FILE = "my_vector_db.bin"
WAL_FILE = "my_vector_db.wal"

def simulate_crash():
    print("--- 1. BÖLÜM: Veri Ekleniyor ve Çökme (Crash) Simüle Ediliyor ---")
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    
    index = VectorIndex()
    index.enable_wal(WAL_FILE)
    
    # Sıfırdan veri ekliyoruz
    vec = model.encode("Çökme öncesi kritik veri", convert_to_numpy=True).astype(np.float32)
    index.add_batch_with_metadata([999], vec, [{"status": "critical"}])
    index.build_hnsw_index()
    
    print("✍️ ID: 999 verisi eklendi. (Diske kaydetmeden 'save_to_disk()' ÇÖKÜŞ SİMÜLE EDİLİYOR...)")
    # save_to_disk ÇAĞRILMADI! 
    # Kod burada aniden kapanıyor!

def recovery_phase():
    print("\n--- 2. BÖLÜM: Veritabanı Yeniden Başlatılıyor (WAL Recovery) ---")
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    
    index = VectorIndex()
    index.enable_wal(WAL_FILE)
    
    # Kurtarma başlatılır
    index.load_from_disk(DB_FILE)
    print(f"✅ Otomatik Kurtarma Tamamlandı! Aktif Doküman Sayısı: {index.len()}")
    
    # Kaybolduğu sanılan veriyi arayalım
    q_vec = model.encode("kritik veri", convert_to_numpy=True).astype(np.float32)
    results = index.search_filtered(q_vec, top_k=1)
    
    for doc_id, dist, meta in results:
        print(f"🎉 KURTARILAN DOKÜMAN: ID: {doc_id} | Metadata: {meta}")

def main():
    simulate_crash()
    recovery_phase()

    # Temizlik
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    if os.path.exists(WAL_FILE): os.remove(WAL_FILE)

if __name__ == "__main__":
    main()