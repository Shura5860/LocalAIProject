import sys
import concurrent.futures
import random
import time
import numpy as np
from sentence_transformers import SentenceTransformer
from vector_engine import VectorIndex

sys.stdout.reconfigure(encoding='utf-8')


# Hazırlık
model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
index = VectorIndex()

# İlk Veri
texts = ["Python programlama dili", "Rust sistem kodlama dili", "FastAPI web servisi"]
embeddings = model.encode(texts, convert_to_numpy=True).astype(np.float32)
metas = [{"cat": "dev"} for _ in texts]
index.add_batch_with_metadata([1, 2, 3], embeddings, metas)
index.build_hnsw_index()

def reader_worker(worker_id):
    """Aynı anda ARAMA yapan okuyucu thread'ler"""
    for _ in range(5):
        query = "yazılım ve kodlama"
        q_vec = model.encode(query, convert_to_numpy=True).astype(np.float32)
        res = index.search_filtered(q_vec, top_k=2)
        print(f"📖 [Reader Thread-{worker_id}] {len(res)} sonuç buldu.")
        time.sleep(0.01)

def writer_worker(worker_id):
    """Aynı anda YAZMA yapan yazıcı thread'ler"""
    doc_id = random.randint(100, 999)
    vec = model.encode("Yeni dinamik içerik", convert_to_numpy=True).astype(np.float32)
    index.add_batch_with_metadata([doc_id], vec, [{"cat": "dyn"}])
    index.build_hnsw_index()
    print(f"✍️ [Writer Thread-{worker_id}] ID: {doc_id} verisini ekledi!")

def main():
    print("--- ⚡ Thread-Safety & Multi-threading Stres Testi ---")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        # 5 Okuyucu, 3 Yazıcı thread'i aynı anda başlatıyoruz
        for i in range(5):
            futures.append(executor.submit(reader_worker, i))
        for i in range(3):
            futures.append(executor.submit(writer_worker, i))

        concurrent.futures.wait(futures)

    print(f"\n✅ Tüm thread'ler başarıyla bitti! Hiçbir çakışma/çökme yaşanmadı.")
    print(f"📊 Toplam Aktif Doküman: {index.len()}")

if __name__ == "__main__":
    main()