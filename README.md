<div align="center">

# AURA-CORE: Local Agentic AI & Native Vector Engine

**A privacy-preserving, on-premise AI assistant combining an in-process Rust vector index, local GGUF inference, tool-augmented ReAct execution, and node-locked licensing.**

[![Rust](https://img.shields.io/badge/Rust-1.80%2B-orange?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![Python](https://img.shields.io/badge/Python-3.14-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Framework-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Tauri](https://img.shields.io/badge/Tauri-2.0-24C8D8?logo=tauri&logoColor=white)](https://tauri.app/)
[![License](https://img.shields.io/badge/License-Commercial%20EULA-purple.svg)](./desktop_app/src/EULA.md)

[English](#english-documentation) • [Türkçe Dokümantasyon](#türkçe-dokümantasyon)

---

</div>

<a name="english-documentation"></a>
## English Documentation

### 1. Overview & Problem Statement

Modern enterprise workflows frequently require LLM reasoning and semantic search over sensitive data (e.g. proprietary codebases, internal documentation, legal contracts). Offloading this workload to external cloud APIs introduces data residency, compliance (GDPR/KVKK), and vendor lock-in concerns.

**AURA-CORE** is designed to address this by running entirely on local consumer- or workstation-grade hardware. It unifies:
- An **in-process Rust vector engine** utilizing Hierarchical Navigable Small World (HNSW) graphs and Write-Ahead Logging (WAL).
- Local **GGUF-based inference** using standard Byte-Pair Encoding (BPE) tokenization with on-demand model allocation (Qwen 2.5 Coder 3B & 7B).
- An autonomous **ReAct agent loop** equipped with deterministic guardrails and sandboxed tools (file I/O, terminal commands, web retrieval).
- A lightweight **Tauri desktop shell** with hardware-bound licensing and strict user liability terms (EULA).

---

### 2. Architecture & Request Lifecycle

```
[User Request]
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│ Tauri Desktop Application (WebKit / Web View)           │
│  - SSE streaming client with real-time token rendering  │
│  - Workspace binding & audit inspection                 │
└──────────────────────────┬──────────────────────────────┘
                           │ Loopback HTTP/2 + SSE (Port 8000)
┌──────────────────────────▼──────────────────────────────┐
│ FastAPI Application Core                                │
│  - Node-Locked License Guard (HMAC-SHA256 time-capsule) │
│  - Ethics & Command Guardrails (pre-execution regex)    │
│  - Human-In-The-Loop (HITL) approval gateway            │
└──────────────┬──────────────────────────┬───────────────┘
               │                          │
┌──────────────▼────────────┐  ┌──────────▼───────────────┐
│ Rust Vector Database      │  │ Local Inference Runtime  │
│  - PyO3 C-FFI bindings    │  │  - llama.cpp AVX2 engine │
│  - In-memory HNSW index   │  │  - Lazy loading (0 MB    │
│  - WAL append-only log    │  │    idle memory footprint)│
│  - Cosine distance SIMD   │  │  - SSE token generator   │
└───────────────────────────┘  └──────────────────────────┘
```

---

### 3. Engineering Decisions & Technical Trade-offs

#### A. Vector Storage: Custom Rust Core vs External Vector Databases
* **Decision:** Implement vector indexing in Rust with PyO3 bindings directly in-process.
* **Rationale:** External vector databases (Pinecone, Qdrant, Milvus) introduce network hops, container management overhead, and complex lifecycle management for a desktop tool. Embedding the HNSW graph directly in-process eliminates network latency and IPC serialization overhead.
* **Trade-off:** Building custom persistence requires implementing our own Write-Ahead Logging (WAL) and compaction/vacuuming mechanisms, increasing internal codebase complexity compared to managed solutions.

#### B. Inference Runtime: Direct Embedded Library vs Ollama Daemon
* **Decision:** Embed local inference directly using `llama-cpp-python` with lazy initialization.
* **Rationale:** External daemons like Ollama run as independent background services, persisting in memory and complicating distribution on target client machines. An embedded approach allows the application to control thread allocation directly and release memory back to the OS when the model is idle.
* **Trade-off:** Model compilation and C++ toolchain compatibility must be managed across target operating systems (e.g., AVX2 on Linux/Windows, Metal on macOS).

#### C. IP Protection: C-Level Native Compilation vs Bytecode Obfuscation
* **Decision:** Use Nuitka to compile the Python server into native machine code.
* **Rationale:** Standard packaging (e.g. PyInstaller) packages `.pyc` bytecode, which is easily decompiled. Nuitka translates Python to C++ and compiles machine binaries, significantly raising the cost of reverse engineering.
* **Trade-off / Honest Limitation:** Native compilation does not make reverse-engineering "impossible"; determined attackers with disassemblers (IDA, Ghidra) can still inspect binary symbols and logic. However, it raises the difficulty level from trivial decompilation to full binary reverse engineering.

---

### 4. Empirical Performance & Methodology

All metrics were gathered on:
- **CPU:** Intel Core i7 (6 physical threads allocated, AVX2 enabled)
- **GPU:** NVIDIA GeForce RTX 3060 Ti (8GB VRAM)
- **OS:** Linux x86_64 (Kernel 6.x)
- **Model:** Qwen 2.5 Coder Instruct (4-bit quantization, `Q4_K_M`)

| Subsystem | Metric | Measured Value | Notes / Methodology |
| :--- | :--- | :--- | :--- |
| **Inference (3B)** | Generation Throughput | **~14.2 tokens/sec** | Measured across 128-token generation runs using greedy sampling (`temp=0.2`). |
| **Inference (7B)** | Generation Throughput | **~5.88 tokens/sec** | Measured across 128-token generation runs with AVX2 thread pooling. |
| **Idle Memory** | VRAM Allocation | **0 MB** | Models load on-demand upon the first query and unload on switch. |
| **Active Memory** | 3B Model Residency | **~1.96 GB VRAM** | Standard context size: 4096 tokens. |
| **Active Memory** | 7B Model Residency | **~4.36 GB VRAM** | Standard context size: 4096 tokens. |
| **Vector Scan** | Cosine Similarity Search | **~19.2 ms** (100k vectors) | Synthetic benchmark: 100,000 vectors (384-d, float32) scanning for Top-10 nearest neighbors. |

> *Note: Vector latency reflects raw mathematical scan and graph traversal times under single-threaded host CPU execution. Real-world end-to-end latency includes embedding model encoding time (~15-30ms depending on batch size).*

---

### 5. Repository Structure

```
├── api_server/                # FastAPI application layer
│   ├── app/
│   │   ├── api/v1/            # Endpoints: vectors, rag, agent, models, license
│   │   ├── core/              # Guardrails, licensing, database configuration
│   │   ├── services/          # ReAct agent loop, inference engine, bridge
│   │   └── tools/             # Sandboxed tools: stealth web, terminal, files
├── desktop_app/               # Tauri 2.0 desktop frontend
│   ├── src/                   # HTML5, Vanilla CSS (OLED dark), client JS
│   └── src-tauri/             # Rust desktop backend & window management
├── Rust-LLM-Engine/           # Native Rust LLM CLI & models directory
├── Rust-Python-Vector-Engine/ # Rust PyO3 HNSW vector database core
├── tests/                     # 22 unit & integration test suites
├── generate_license.py        # Vendor utility for hardware-bound key generation
├── package_distribution.sh    # Packaging pipeline for clean release distribution
└── start_assistant.sh         # One-click launcher script
```

---

### 6. Quickstart & Verification

```bash
# 1. Clone repository
git clone https://github.com/shura/AURA-CORE.git
cd AURA-CORE

# 2. Run automated test suite (22 unit tests)
./.venv/bin/python -m unittest discover tests -v

# 3. Launch application (Starts FastAPI server & opens Desktop UI)
./start_assistant.sh
```

---
---

<a name="türkçe-dokümantasyon"></a>
## 🇹🇷 Türkçe Dokümantasyon

### 1. Genel Bakış ve Problem Tanımı

Kurumsal yapılarda ve teknik iş akışlarında, hassas veriler (kaynak kodlar, iç yazışmalar, hukuki sözleşmeler) üzerinde yapay zeka ve anlamsal arama çalıştırmak kritik bir ihtiyaçtır. Bu verileri harici bulut API'lerine (OpenAI, Anthropic) göndermek; KVKK/GDPR uyumluluğu, veri mahremiyeti ve ticari sırların korunması açısından riskler doğurur.

**AURA-CORE**, tamamen kullanıcının kendi donanımı üzerinde, internet bağlantısına ihtiyaç duymadan (Air-Gapped) çalışacak şekilde tasarlanmış yerel bir yapay zeka asistanıdır:
- **Rust ile geliştirilmiş süreç içi vektör veri tabanı:** HNSW graf indeksleme ve Write-Ahead Logging (WAL) veri güvenliği.
- **Yerel GGUF çıkarım motoru:** Standart BPE tokenizasyonu ve talep edildikçe bellek yükleyen (on-demand) çift model desteği (Qwen 2.5 Coder 3B & 7B).
- **Otonom ReAct ajan döngüsü:** Terminal komutları, dosya düzenleme ve web içeriği okuma için insan onaylı (HITL) güvenlik duvarı.
- **Tauri masaüstü arayüzü:** Düşük bellek tüketimli istemci, donanım kilitli lisanslama ve hukuki sorumluluk sözleşmesi (EULA).

---

### 2. Mimari Kararlar ve Mühendislik Tercihleri

#### A. Vektör Depolama: Özel Rust Çekirdeği vs Hazır Veri Tabanları
* **Karar:** Vektör indeksini Rust ile süreç içi (in-process) olarak yazıp PyO3 ile Python'a bağlamak.
* **Gerekçe:** Pinecone, Milvus veya Qdrant gibi harici sistemler, son kullanıcıya dağıtılan masaüstü uygulamalarında Docker ve ağ yönetimi gerektirir. Süreç içi HNSW grafiği; ağ gecikmesini ortadan kaldırır ve IPC serileştirme yükünü sıfıra indirir.
* **Ödünleşim (Trade-off):** Sıfırdan bir motor yazmak, WAL (Write-Ahead Log) ve veri sıkıştırma (vacuum) algoritmalarını kendimizin geliştirmesini gerektirmiş, kod tabanının bakım maliyetini artırmıştır.

#### B. Çıkarım Motoru: Gömülü Kütüphane vs Ollama Servisi
* **Karar:** Modelleri harici bir daemon yerine doğrudan `llama-cpp-python` kütüphanesi üzerinden çalıştırmak.
* **Gerekçe:** Ollama gibi bağımsız arka plan servisleri, kullanıcı uygulamayı kapatsa bile bellekte kalabilir ve dağıtım paketini karmaşıklaştırır. Gömülü motor sayesinde, model boşta beklerken bellek işletim sistemine geri verilir (**0 MB boşta VRAM**).
* **Ödünleşim:** Hedef işletim sistemlerinde (Windows/Linux için AVX2, Mac için Metal) C++ derleme uyumluluğunun yönetilmesi gerekir.

#### C. Fikri Mülkiyet Koruması: C++ Makine Kodu Derlemesi vs Karıştırma (Obfuscation)
* **Karar:** Python sunucusunu Nuitka ile doğrudan C++ makine koduna derlemek.
* **Gerekçe:** PyInstaller gibi araçlar yalnızca `.pyc` bayt kodunu paketler; bu kodlar `uncompyle6` gibi araçlarla birkaç saniyede geri çözülebilir. Nuitka ise Python AST ağacını C++ koduna çevirip derler.
* **Teknik Sınır / Dürüst Yaklaşım:** Hiçbir derleme yöntemi tersine mühendisliği tamamen "imkansız" kılmaz. Deneyimli bir güvenlik uzmanı disassembler (Ghidra, IDA Pro) araçlarıyla ikili dosyayı inceleyebilir. Ancak bu yöntem, kodu kopyalamanın maliyetini basit bir decompile işleminden karmaşık bir tersine mühendislik seviyesine çıkarır.

---

### 3. Ölçüm Sonuçları ve Test Metodolojisi

Aşağıdaki veriler belirtilen donanım üzerinde ölçülmüştür:
- **İşlemci:** Intel Core i7 (6 fiziksel iş parçacığı, AVX2 aktif)
- **Ekran Kartı:** NVIDIA GeForce RTX 3060 Ti (8GB VRAM)
- **İşletim Sistemi:** Linux x86_64
- **Model:** Qwen 2.5 Coder Instruct (4-bit kuantizasyon, `Q4_K_M`)

| Alt Sistem | Metrik | Ölçülen Değer | Metodoloji ve Detaylar |
| :--- | :--- | :--- | :--- |
| **Çıkarım (3B)** | Üretim Hızı | **~14.2 token/sn** | 128 tokenlik standart kod üretim testi (`temp=0.2`). |
| **Çıkarım (7B)** | Üretim Hızı | **~5.88 token/sn** | 128 tokenlik üretim testi, AVX2 thread havuzu. |
| **Boşta Bellek** | VRAM Tüketimi | **0 MB** | Model yalnızca soru sorulduğunda yüklenir; boşta VRAM tutulmaz. |
| **Aktif Bellek (3B)** | Model Boyutu | **~1.96 GB VRAM** | 4096 token bağlam penceresi. |
| **Aktif Bellek (7B)** | Model Boyutu | **~4.36 GB VRAM** | 4096 token bağlam penceresi. |
| **Vektör Arama** | Kosinüs Benzerliği | **~19.2 ms** (100k vektör) | Sentetik test: 100.000 adet 384-boyutlu float32 vektörde Top-10 en yakın komşu taraması. |

> *Not: Vektör arama süresi saf matematiksel hesaplama ve graf tarama süresini ifade eder. Gerçek dünya senaryolarında uçtan uca süreye metnin embedding modelinden geçirilme süresi (~15-30ms) eklenir.*

---

### 4. Kurulum ve Doğrulama

```bash
# 1. Depoyu klonlayın
git clone https://github.com/shura/AURA-CORE.git
cd AURA-CORE

# 2. Birim test paketini çalıştırın (22 testin tamamı)
./.venv/bin/python -m unittest discover tests -v

# 3. Uygulamayı başlatın (FastAPI sunucusu ve Masaüstü arayüzü)
./start_assistant.sh
```

---

<div align="center">
<b>AURA-CORE: Engineered with rigorous architectural standards.</b>
</div>
