# 🚀 VectorEngine: High-Performance Hybrid Vector Database System

**VectorEngine**, Rust'ın bellek güvenliği ve ultra yüksek performanslı hesaplama gücünü (PyO3 FFI), Python'ın esnek yapay zeka ekosistemi ve FastAPI Clean Architecture mimarisi ile birleştiren hibrit bir **Vektör Veritabanı Motorudur**.

Bu proje; anlamsal arama (semantic search), LLM RAG (Retrieval-Augmented Generation) sistemleri ve yüksek boyutlu vektör aramaları için **düşük gecikme süresi (low latency)**, **çökme dayanıklılığı (WAL)** ve **gelişmiş filtreleme yetenekleri** sunar.

---

## 🌟 Öne Çıkan Özellikler

- **⚡ HNSW (Hierarchical Navigable Small World) Graf İndeksi:** $O(\log N)$ karmaşıklığında milisaniyeler seviyesinde en yakın komşu (ANN) vektör araması.
- **📐 Vektör Normalizasyonu (Cosine Distance):** Ekleme ve sorgu anında otomatik $L_2$ normalizasyonu ile hassas cosine benzerlik ölçümü.
- **🔒 Tekli Durum Kilit Modeli (Single State Locking):** Tüm indeks ve metadata durumunu tek bir `InnerState` ve `RwLock` altında yöneterek yüksek eşzamanlılıkta (concurrency) kilit çakışmalarını (lock contention) engeller.
- **🛡️ WAL (Write-Ahead Logging) & Tamponlu I/O:** Elektrik kesintisi veya ani çökmelerde veri kaybını önleyen `BufWriter` destekli dayanıklılık (Durability) katmanı.
- **💾 Bincode Binary Serileştirme:** İndeksin diske ultra sıkıştırılmış binary formatta kaydedilmesi ve milisaniyeler içinde sıfırdan yüklenmesi.
- **🔍 Inverted Index Pre-Filtering:** `==` filtrelerinde Inverted Index ile kandidat kümesini $O(1)$ sürede daraltan ve recall skorunu düşürmeyen gelişmiş filtre arama altyapısı (Ayrıca `>`, `<`, `>=`, `<=` sayısal operatör desteği).
- **🧹 Vacuum / Compaction:** Silinen (tombstone) verileri bellekten ve HNSW grafından fiziksel olarak temizleyerek graf boyutunu küçülten `vacuum()` motoru.
- **🏛️ FastAPI Clean Architecture:** Katmanlı, ölçeklenebilir ve otomatik OpenAPI (Swagger) dokümantasyonuna sahip REST API sunucusu.

---

## 📐 Proje Mimarisi ve Klasör Yapısı

Proje; alt seviye sistem kodu (Rust Crate), REST API servisi (FastAPI) ve test paketi olarak **Clean/Layered Architecture** standartlarına uygun şekilde modülerleştirilmiştir:

```text
c:\AI Work/
├── vector_engine/                  # 🦀 RUST CORE ENGINE (PyO3 Extension Crate)
│   ├── Cargo.toml                  # Rust Bağımlılıkları (pyo3, instant-distance, bincode, serde)
│   └── src/
│       ├── lib.rs                  # PyO3 #[pymodule] modül giriş kapısı
│       ├── types.rs                # VectorPoint, Cosine Normalizasyonu & Mesafe Mantığı
│       ├── storage/
│       │   ├── mod.rs
│       │   └── wal.rs              # WalEntry Enum & Tamponlu (Buffered) WAL Loglayıcı
│       └── engine/
│           ├── mod.rs
│           └── index.rs            # InnerState, HNSW İndeks, Search & Vacuum Motoru
│
├── api_server/                     # 🐍 PYTHON FASTAPI REST API (Clean Architecture)
│   └── app/
│       ├── main.py                 # App Factory, Lifespan (Startup/Shutdown) & Router Kayıtları
│       ├── core/
│       │   └── config.py           # Singleton VectorIndex Nesnesi ve Konfigürasyon
│       ├── schemas/
│       │   └── vectors.py          # Pydantic İstek ve Yanıt Şemaları
│       └── api/
│           └── v1/
│               ├── vectors.py      # /vectors/add, /search, /{id} (DELETE/PUT)
│               └── database.py     # /db/status, /db/save, /db/load, /db/vacuum
│
└── tests/                          # 🧪 ENTEGRASYON VE PERFORMANS TEST SUITE
    ├── test_crud.py                # Ekleme, Silme ve Güncelleme Testleri
    ├── test_metadata_search.py     # Metadata Filtreli Arama Testi
    ├── test_norm.py                # Cosine Normalizasyon Testi
    ├── test_persistence.py         # Binary Bincode Disk Kayıt & Yükleme Testi
    ├── test_prefilter.py           # Inverted Index Pre-Filtering Testi
    ├── test_range.py               # Sayısal Karşılaştırma Filtre Testi (>, <, >=, <=)
    ├── test_semantic_search.py     # SentenceTransformers Türkçe Anlamsal Arama Testi
    ├── test_thread.py              # Multi-threading Stres & Concurrency Testi
    ├── test_vacuum.py              # Fiziksel Graf Temizleme (Vacuum) Testi
    └── test_wal.py                 # Çökme Sonrası WAL Recovery Testi
```

---

## 🛠️ Kurulum ve Çalıştırma

### 1. Gereksinimler
- **Python 3.10+**
- **Rust Compiler & Cargo** (`rustc`, `cargo`)
- **Maturin** (PyO3 bindingleri için: `pip install maturin`)

### 2. Sanal Ortamı Oluşturma ve Bağımlılıkları Yükleme
```bash
# Sanal ortam oluşturun
python -m venv .venv

# Ortamı aktifleştirin (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Gerekli kütüphaneleri yükleyin
pip install fastapi uvicorn sentence-transformers numpy pydantic maturin
```

### 3. Rust Vektör Motorunu Derleme (Maturin)
`vector_engine` klasörüne girip `maturin develop` komutunu çalıştırarak Rust kodunu doğrudan Python sanal ortamınıza derleyebilirsiniz:

```bash
cd vector_engine
maturin develop
cd ..
```

---

## 🚀 REST API Sunucusunu Çalıştırma

FastAPI Clean Architecture uygulamasını başlatmak için kök dizinde şu komutu çalıştırın:

```bash
python -m uvicorn api_server.app.main:app --reload
```

Sunucu başladıktan sonra tarayıcınızdan **Swagger UI (İnteraktif API Dokümantasyonu)** sayfasına erişebilirsiniz:
👉 `http://127.0.0.1:8000/docs`

---

## 📡 API Uç Noktaları (Endpoints)

### 1. Vektör Ekleme (`POST /vectors/add`)
```json
{
  "ids": [1, 2],
  "vectors": [
    [0.12, 0.45, -0.89, 0.23],
    [0.98, -0.11, 0.34, 0.55]
  ],
  "metadatas": [
    {"category": "yazilim", "year": "2026"},
    {"category": "mutfak", "year": "2025"}
  ]
}
```

### 2. Filtreli Vektör Araması (`POST /vectors/search`)
```json
{
  "query_vector": [0.10, 0.40, -0.85, 0.20],
  "top_k": 2,
  "filter_key": "category",
  "filter_value": "yazilim",
  "operator": "=="
}
```

### 3. Vacuum / Temizlik (`POST /db/vacuum`)
Soft-delete ile silinmiş tüm dokümanları HNSW grafından ve bellekten fiziksel olarak temizler:
```http
POST /db/vacuum
```

### 4. Diske Kaydetme / Yükleme (`POST /db/save` & `POST /db/load`)
```http
POST /db/save?file_path=db_dump.bin
POST /db/load?file_path=db_dump.bin
```

---

## 🧪 Testleri Çalıştırma

Projede yer alan tüm modüler entegrasyon testlerini çalıştırmak için:

```bash
# Türkçe Anlamsal Arama Testi
python tests/test_semantic_search.py

# Soft-Delete & Vacuum Temizlik Testi
python tests/test_vacuum.py

# Multi-Thread Concurrency Stres Testi
python tests/test_thread.py

# WAL Kurtarma (Crash Recovery) Testi
python tests/test_wal.py
```

---

## 📝 Lisans

Bu proje **MIT Lisansı** ile lisanslanmıştır. Serbestçe kullanılabilir ve geliştirilebilir.
