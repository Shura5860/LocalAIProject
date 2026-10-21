import sys
import os
import time

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.services.rag_service import rag_service
from api_server.app.core.config import db

def run_rag_test():
    print("=" * 70)
    print("🚀 FAZ 1 TESTİ: Rust Vektör Veritabanı & Rust-LLM RAG Entegrasyonu")
    print("=" * 70)

    # 1. Bilgi Tabanı Belgeleri (Şirket/Kişisel Özel Bilgiler)
    test_docs = [
        "Proje A, Rust dili ve AVX2 SIMD donanım optimizasyonları ile geliştirilmiş yüksek performanslı bir LLM çıkarım motorudur.",
        "Proje B, PyO3 FFI ve instant-distance HNSW grafı kullanan, WAL çökme dayanıklılığına sahip hibrit bir vektör veritabanıdır.",
        "Şirketin 2026 yılı yapay zeka stratejisi, bulut bağımlılığını sıfıra indirip tüm AI modellerini yerel CPU/GPU donanımlarında çalıştırmaktır.",
        "Ofis içindeki kahve makinesinin şifresi 2026'dır ve her ayın ilk pazartesi günü temizlik bakımı yapılır."
    ]
    metas = [
        {"topic": "rust-llm", "category": "tech"},
        {"topic": "vector-engine", "category": "tech"},
        {"topic": "company-strategy", "category": "management"},
        {"topic": "office-info", "category": "general"}
    ]

    print(f"\n[1] {len(test_docs)} adet özel belge sisteme yükleniyor ve vektörleştiriliyor...")
    indexed_count = rag_service.ingest_documents(test_docs, metas)
    print(f"✅ Başarıyla indekslendi! Vektör Veritabanındaki Toplam Belge Sayısı: {db.len()}")

    # 2. RAG Soruları
    test_queries = [
        "Kahve makinesinin şifresi nedir ve bakımı ne zaman yapılır?",
        "Şirketin 2026 yapay zeka ve bulut stratejisi hakkında ne biliyorsun?",
        "Rust LLM motoru hangi donanım optimizasyonlarını kullanıyor?"
    ]

    for q in test_queries:
        print("\n" + "-" * 70)
        print(f"❓ KULLANICI SORUSU: \"{q}\"")
        print("-" * 70)

        start = time.time()
        result = rag_service.query(user_query=q, top_k=2)
        elapsed = (time.time() - start) * 1000

        print(f"⚡ RAG İşlem Süresi: {elapsed:.2f} ms")
        print("🎯 HNSW Grafından Çekilen En Alakalı Bağlamlar (Top-2):")
        for chunk in result["retrieved_chunks"]:
            print(f"   • [ID: {chunk['id']}, Mesafe: {chunk['distance']:.4f}] => {chunk['text']}")

        print(f"\n🤖 LLM YANITI ({result['llm_engine']}):")
        print(f"{result['answer']}")

    print("\n" + "=" * 70)
    print("✅ FAZ 1 RAG PIPELINE ENTEGRASYON TESTİ BAŞARIYLA TAMAMLANDI!")
    print("=" * 70)

if __name__ == "__main__":
    run_rag_test()
