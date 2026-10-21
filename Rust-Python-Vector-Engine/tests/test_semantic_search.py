import sys
import time
import numpy as np
from sentence_transformers import SentenceTransformer
from vector_engine import VectorIndex

sys.stdout.reconfigure(encoding='utf-8')


def main():
    print("--- 🧠 Türkçe Anlamsal Arama (Semantic Search) ---")

    # 1. Yapay Zeka Modelini Yükleme
    print("\n[1] Yapay zeka modeli yükleniyor (Multilingual MiniLM)...")
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    # 2. Örnek Veri Setimiz (Farklı kategorilerde Türkçe cümleler)
    documents = [
        "Sokak kedileri soğuk havalarda sığınacak sıcak bir yer ararlar.",
        "Köpekler sahiplerine son derece sadık evcil hayvanlardır.",
        "Yapay zeka ve derin öğrenme teknolojileri yazılım dünyasını değiştiriyor.",
        "Python ve Rust dilleri performanslı sistemler geliştirmek için kullanılır.",
        "Kullanılan arabanın motor yağı ve filtreleri düzenli değiştirilmelidir.",
        "Galatasaray ve Fenerbahçe arasındaki derbi maçı büyük heyecana sahne oldu.",
        "İtalyan mutfağının en sevilen lezzetlerinden biri napoliten pizzadır.",
        "Dizüstü bilgisayar alırken işlemci, RAM ve ekran kartı özelliklerine bakılır.",
        "Espresso ve filtre kahve güne zinde başlamak için sıkça tercih edilir.",
        "Uzay araştırmaları Mars üzerinde su ve yaşam izleri aramaya devam ediyor."
    ]

    # 3. Cümleleri Vektörlere (Embeddings) Dönüştürme
    print(f"\n[2] {len(documents)} adet belge yapay zeka ile 384 boyutlu vektörlere dönüştürülüyor...")
    embeddings = model.encode(documents, convert_to_numpy=True).astype(np.float32)

    # 4. Rust HNSW Motoruna Verileri Yükleme
    index = VectorIndex()
    ids = list(range(len(documents)))
    index.add_batch(ids, embeddings)

    print("\n[3] HNSW Graf Yapısı İnşa Ediliyor...")
    index.build_hnsw_index()
    print("HNSW İndeksi Başarıyla Oluşturuldu!")

    # 5. Anlamsal Arama Senaryoları
    print("\n" + "="*60)
    print(" 🔍 ANLAMSAL ARAMA TESTİ")
    print("="*60)

    # Önemli: Sorgu cümlelerimiz belgelerdeki kelimelerle birebir AYNIKELİMELERİ İÇERMEYECEK!
    # Model kelime eşleşmesine değil, ANLAMA bakacak.
    test_queries = [
        "Evcil hayvan bakımı ve beslenmesi",   # Kedi/Köpek cümlelerini bulmalı
        "Yazılım geliştirme ve kodlama",      # Python/Rust/Yapay Zeka cümlelerini bulmalı
        "Otomobil bakımı nasıl yapılır?",     # Motor yağı cümlesini bulmalı
        "Lezzetli yemek tarifleri"             # Pizza/Kahve cümlelerini bulmalı
    ]

    for query in test_queries:
        print(f"\n❓ Sorgu: \"{query}\"")
        
        # Sorguyu vektöre çevir
        start_time = time.time()
        query_vector = model.encode(query, convert_to_numpy=True).astype(np.float32)
        
        # Rust HNSW Motorumuzda milisaniyede arama yap
        results = index.search_hnsw(query_vector, top_k=2)
        duration_ms = (time.time() - start_time) * 1000

        print(f"⚡ Arama Süresi: {duration_ms:.2f} ms")
        print("🎯 En Alakalı Sonuçlar:")
        
        for doc_id, distance in results:
            print(f"   • [{documents[doc_id]}] (Mesafe Skoru: {distance:.4f})")

if __name__ == "__main__":
    main()