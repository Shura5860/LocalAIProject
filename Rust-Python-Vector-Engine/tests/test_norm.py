import sys
import numpy as np
from sentence_transformers import SentenceTransformer
from vector_engine import VectorIndex

sys.stdout.reconfigure(encoding='utf-8')


def main():
    print("--- 📐 Normalization & Cosine Distance Testi ---")
    
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    documents = [
        {"id": 1, "text": "Yapay zeka ve derin öğrenme algoritmaları son derece hızlı gelişiyor."},
        {"id": 2, "text": "Makine öğrenmesi modelleri ve veri analitiği teknikleri."},
        {"id": 3, "text": "Evde lezzetli bir İtalyan makarnası pişirmenin püf noktaları."}
    ]

    texts = [d["text"] for d in documents]
    ids = [d["id"] for d in documents]
    embeddings = model.encode(texts, convert_to_numpy=True).astype(np.float32)

    index = VectorIndex()
    index.add_batch_with_metadata(ids, embeddings, [{} for _ in ids])
    index.build_hnsw_index()

    query = "Yapay zeka ve makine öğrenimi"
    q_vec = model.encode(query, convert_to_numpy=True).astype(np.float32)

    print(f"\n❓ Sorgu: '{query}'")
    results = index.search_filtered(q_vec, top_k=3)
    
    for doc_id, dist, _ in results:
        doc_text = next(d['text'] for d in documents if d['id'] == doc_id)
        # Distance skorunun ne kadar 0'a yakın olduğunu gözlemliyoruz
        print(f"   • [ID: {doc_id}] Distance: {dist:.4f} | Metin: '{doc_text}'")

if __name__ == "__main__":
    main()