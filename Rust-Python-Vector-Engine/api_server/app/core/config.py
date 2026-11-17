import os
import threading
from typing import List
import vector_engine

# Veri dosyaları için mutlak dizin (Çalışma dizininden bağımsız kararlılık)
BASE_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
DB_FILE = os.path.join(BASE_DATA_DIR, "my_vector_db.bin")
WAL_FILE = os.path.join(BASE_DATA_DIR, "vector_db.wal")
BM25_FILE = os.path.join(BASE_DATA_DIR, "bm25_sparse_index.json")

db = vector_engine.VectorIndex()
db.enable_wal(WAL_FILE)

_id_lock = threading.Lock()
_next_doc_id = 0


def allocate_doc_ids(count: int = 1) -> List[int]:
    """
    Monotonik artan, çakışmasız doküman ID üreteci.
    Kayıt silinse veya vacuum yapılsa dahi eski ID'lerin üzerine yazılmasını engeller.
    """
    global _next_doc_id
    with _id_lock:
        current_len = db.len()
        if _next_doc_id < current_len:
            _next_doc_id = current_len
        allocated = list(range(_next_doc_id, _next_doc_id + count))
        _next_doc_id += count
        return allocated


def init_database():
    global _next_doc_id
    if os.path.exists(DB_FILE):
        db.load_from_disk(DB_FILE)
        _next_doc_id = max(_next_doc_id, db.len())
        print(f"✅ İndeks Yüklendi! Aktif Doküman Sayısı: {db.len()}")
    else:
        print("ℹ️ Henüz kaydedilmiş veritabanı bulunamadı, sıfır indeks ile başlandı.")

    # BM25 Sparse İndeksini diskten geri yükle
    try:
        from api_server.app.services.rag_service import rag_service
        rag_service.load_sparse_index(BM25_FILE)
    except Exception:
        pass


def save_database_and_checkpoint():
    """
    Vektör veritabanını ve BM25 indeksini diske yazar, ardından WAL dosyasını
    sıfırlayarak (Checkpoint / Truncate) disk şişmesini önler.
    """
    db.save_to_disk(DB_FILE)
    if os.path.exists(WAL_FILE):
        try:
            with open(WAL_FILE, "w", encoding="utf-8"):
                pass
        except Exception:
            pass
    try:
        from api_server.app.services.rag_service import rag_service
        rag_service.save_sparse_index(BM25_FILE)
    except Exception:
        pass

