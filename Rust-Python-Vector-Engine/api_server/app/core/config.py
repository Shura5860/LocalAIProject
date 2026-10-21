import os
import vector_engine

# Singleton VectorIndex Nesnesi ve Konfigürasyonu
DB_FILE = "my_vector_db.bin"
WAL_FILE = "vector_db.wal"

db = vector_engine.VectorIndex()
db.enable_wal(WAL_FILE)

def init_database():
    if os.path.exists(DB_FILE):
        db.load_from_disk(DB_FILE)
        print(f"✅ İndeks Yüklendi! Aktif Doküman Sayısı: {db.len()}")
    else:
        print("ℹ️ Henüz kaydedilmiş veritabanı bulunamadı, sıfır indeks ile başlandı.")
