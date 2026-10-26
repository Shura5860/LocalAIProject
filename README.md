<div align="center">

# AURA-CORE: Local Agentic AI & Native Vector Engine

**A privacy-preserving, on-premise AI assistant combining an in-process Rust vector index, local GGUF inference, tool-augmented ReAct execution, and dual-licensing (AGPLv3 / Commercial).**

[![Rust](https://img.shields.io/badge/Rust-1.80%2B-orange?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.14-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Framework-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Tauri](https://img.shields.io/badge/Tauri-2.0-24C8D8?logo=tauri&logoColor=white)](https://tauri.app/)
[![License: AGPL v3 / Commercial](https://img.shields.io/badge/License-AGPL%20v3%20%2F%20Commercial-blue.svg)](./LICENSE)
[![CI Test Suite](https://github.com/Shura5860/LocalAIProject/actions/workflows/ci.yml/badge.svg)](https://github.com/Shura5860/LocalAIProject/actions/workflows/ci.yml)

[English](#english-documentation) • [Türkçe Dokümantasyon](#türkçe-dokümantasyon)

<br/>

![AURA-CORE Desktop Interface](docs/assets/aura_desktop_ui.png)
*AURA-CORE OLED Desktop Interface: Real-time ReAct trace reasoning, token streaming, and embedded Rust vector synchronization.*

</div>

---

<a name="english-documentation"></a>
## English Documentation

### 1. Overview & Problem Statement

Modern enterprise workflows frequently require LLM reasoning and semantic search over sensitive data (e.g. proprietary codebases, internal documentation, legal contracts). Offloading this workload to external cloud APIs introduces data residency, compliance (GDPR/KVKK), and vendor lock-in concerns.

**AURA-CORE** is designed to address this by running entirely on local consumer- or workstation-grade hardware:
- An **in-process Rust vector engine** utilizing Hierarchical Navigable Small World (HNSW) graphs and Write-Ahead Logging (WAL).
- Local **GGUF-based inference** using standard Byte-Pair Encoding (BPE) tokenization with on-demand model allocation (Qwen 2.5 Coder 3B & 7B).
- An autonomous **ReAct agent loop** equipped with deterministic guardrails and sandboxed tools (file I/O, terminal execution, stealth web retrieval).
- A lightweight **Tauri desktop shell** with hardware-bound licensing and dual licensing options (AGPLv3 copyleft or Commercial EULA).

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
* **Trade-off & Hardware Reality:** The benchmark below uses a **CPU AVX2 build** (6 host threads). On systems with CUDA-enabled compilation (`GGML_CUDA=1`), throughput scales to 45-80+ tokens/sec on modern GPUs. Without GPU offload flags, inference runs deterministically on AVX2 CPU SIMD cores.

#### C. IP Protection: C-Level Native Compilation vs Bytecode Obfuscation
* **Decision:** Use Nuitka to compile the Python server into native machine code.
* **Rationale:** Standard packaging (e.g. PyInstaller) packages `.pyc` bytecode, which is easily decompiled. Nuitka translates Python to C++ and compiles machine binaries, significantly raising the cost of reverse engineering.
* **Trade-off / Honest Limitation:** Native compilation does not make reverse-engineering "impossible"; determined attackers with disassemblers (IDA, Ghidra) can still inspect binary symbols and logic. However, it raises the difficulty level from trivial decompilation to full binary reverse engineering.

---

### 4. Empirical Performance & Methodology

All metrics were gathered on:
- **CPU:** Intel Core i7 (6 physical threads allocated, AVX2 enabled)
- **Host GPU:** NVIDIA GeForce RTX 3060 Ti (8GB VRAM)
- **Runtime Compilation:** CPU-native AVX2 SIMD (`llama-cpp-python` CPU engine)
- **OS:** Linux x86_64 (Kernel 6.x)
- **Model:** Qwen 2.5 Coder Instruct (4-bit quantization, `Q4_K_M`)

| Subsystem | Metric | Measured Value | Notes / Methodology |
| :--- | :--- | :--- | :--- |
| **Inference (3B)** | Generation Throughput | **~14.2 tokens/sec** | 128-token generation, AVX2 CPU SIMD (6 threads, `temp=0.2`). |
| **Inference (7B)** | Generation Throughput | **~5.88 tokens/sec** | 128-token generation, AVX2 CPU SIMD (6 threads). |
| **Idle Memory** | Host Memory Allocation | **0 MB** | Models load on-demand upon first query; unloaded when switched. |
| **Active Memory (3B)** | System RAM Residency | **~1.96 GB RAM** | 4096 context window, zero idle overhead. |
| **Active Memory (7B)** | System RAM Residency | **~4.36 GB RAM** | 4096 context window. |
| **Vector Scan** | Cosine Similarity Search | **~19.2 ms** (100k vectors) | Synthetic benchmark: 100,000 vectors (384-d, float32) scanning for Top-10 nearest neighbors. |

> *Note on Inference Speeds: The speeds above reflect CPU-bound SIMD AVX2 execution. When compiled with CUDA/cuBLAS (`CMAKE_ARGS="-DGGML_CUDA=on"`), the RTX 3060 Ti achieves 50-85+ tokens/sec.*

---

### 5. Security Architecture, Threat Model & Stealth Web

#### Threat Model & Limitations
Autonomous agents with terminal, file, and network capabilities introduce potential attack surfaces. AURA-CORE adopts a **Defense-in-Depth** model:
1. **Deterministic Pattern Blocking (Regex Guardrails):** Detects obvious destructive commands (e.g., `rm -rf /`, `:(){ :|:& };:`, raw curl-pipe-to-shell, and base64 encoded payloads).
2. **Human-In-The-Loop (HITL) Gateway:** Any action modifying the host system (`write_file`, `run_terminal_command`) is quarantined in a pending state until explicitly approved by the user via the desktop UI.
3. **Known Limitation:** Regex-based sanitization alone is **not an OS sandbox**. Malicious actors or sophisticated prompt injections can craft novel shell invocations that bypass regex filters. For untrusted enterprise code, running AURA-CORE in an isolated container/VM is strongly recommended.

#### Stealth Web Scraper (`read_web_page`)
The agent includes a web extraction tool designed for legitimate technical research and documentation retrieval:
- **Anti-Bot & WAF Handling:** Automatically uses browser-like HTTP/2 headers and rotating desktop user-agents to avoid spurious CAPTCHA/Cloudflare blocks on public documentation.
- **Jina Reader Gateway:** Employs headless markdown conversion for heavy single-page apps (SPA) while retaining clean readable text.

---

### 6. Repository Structure

```
├── desktop_app/               # Tauri 2.0 desktop frontend (HTML5/CSS/JS + Rust)
├── docs/                      # Architectural notes, assets, and FAQ
│   ├── assets/                # Screenshots and UI artifacts
│   └── Question_Ask.md        # Deep-dive design Q&A
├── Rust-LLM-Engine/           # Native Rust LLM CLI & models directory
├── Rust-Python-Vector-Engine/ # In-process Rust vector engine & FastAPI server
│   ├── api_server/            # REST API, ReAct agent loop, tool registry
│   └── tests/                 # Comprehensive test suites (24 test files)
├── scripts/                   # Distribution and licensing utilities
│   ├── build_commercial_binary.sh
│   ├── generate_license.py
│   ├── package_distribution.sh
│   └── license.json
├── LICENSE                    # Dual License (GNU AGPLv3 + Commercial EULA)
├── start_assistant.sh         # One-click launch script
└── .github/workflows/ci.yml   # Continuous Integration test pipeline
```

---

### 7. Quickstart & Verification

```bash
# 1. Clone repository
git clone https://github.com/Shura5860/LocalAIProject.git
cd LocalAIProject

# 2. Run automated test suite (all unit and integration tests)
./.venv/bin/python -m unittest discover Rust-Python-Vector-Engine/tests -v

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
- **Tauri masaüstü arayüzü:** Düşük bellek tüketimli istemci, donanım kilitli lisanslama ve çift lisanslama (AGPLv3 / Ticari EULA).

---

### 2. Güvenlik Mimarisi, Tehdit Modeli ve Stealth Web

#### Tehdit Modeli ve Sınırları
Otonom ajanların terminal, dosya sistemi ve ağ üzerinde işlem yapabilmesi saldırı yüzeyi yaratır. AURA-CORE katmanlı bir savunma yaklaşımı uygular:
1. **Deterministik Kural Filtreleri (Regex Korumaları):** Zararlı olabilecek açık kalıpları (`rm -rf /`, `:(){ :|:& };:`, base64 gizlenmiş kabuk çağrıları vb.) yakalar.
2. **İnsan Onay Mekanizması (HITL Gateway):** Dosya yazma (`write_file`) veya terminal komutu (`run_terminal_command`) gibi sistemi değiştirebilecek kritik tüm eylemler, kullanıcı arayüz üzerinden onay verene kadar bekletilir.
3. **Teknik Sınır / Dürüstlük:** Regex tabanlı kontroller tek başına bir işletim sistemi kum havuzu (sandbox) **değildir**. Gelişmiş prompt injection veya alışılmadık kabuk sözdizimleri kuralları aşabilir. Yüksek riskli ortamlarda AURA-CORE'un izole bir sanal makinede (VM/Container) çalıştırılması önerilir.

#### Stealth Web Aracı (`read_web_page`)
Ajanın teknik dokümantasyon ve web kaynaklarını tarayabilmesi için entegre edilmiştir:
- **Bot/WAF Yönetimi:** Meşru dokümantasyon sitelerinde bot engeline takılmamak için modern masaüstü User-Agent başlıkları ve HTTP/2 kullanır.
- **Jina Reader Gateway:** JavaScript yoğunluklu sayfaları okunaklı markdown formatına dönüştürerek modele temiz girdi sağlar.

---

### 3. Ölçüm Sonuçları ve Test Metodolojisi

Aşağıdaki veriler belirtilen donanım üzerinde ölçülmüştür:
- **İşlemci:** Intel Core i7 (6 fiziksel iş parçacığı, AVX2 aktif)
- **Ekran Kartı:** NVIDIA GeForce RTX 3060 Ti (8GB VRAM)
- **Çıkarım Çalışma Zamanı:** CPU-Native AVX2 SIMD (`llama-cpp-python` CPU derlemesi)
- **İşletim Sistemi:** Linux x86_64
- **Model:** Qwen 2.5 Coder Instruct (4-bit kuantizasyon, `Q4_K_M`)

| Alt Sistem | Metrik | Ölçülen Değer | Metodoloji ve Detaylar |
| :--- | :--- | :--- | :--- |
| **Çıkarım (3B)** | Üretim Hızı | **~14.2 token/sn** | 128 tokenlik kod testi, AVX2 CPU SIMD (6 iş parçacığı, `temp=0.2`). |
| **Çıkarım (7B)** | Üretim Hızı | **~5.88 token/sn** | 128 tokenlik kod testi, AVX2 CPU SIMD (6 iş parçacığı). |
| **Boşta Bellek** | Bellek Ayırma | **0 MB** | Model yalnızca soru sorulduğunda yüklenir; boşta bellek tutulmaz. |
| **Aktif Bellek (3B)** | Sistem RAM Ayak İzi | **~1.96 GB RAM** | 4096 token bağlam penceresi. |
| **Aktif Bellek (7B)** | Sistem RAM Ayak İzi | **~4.36 GB RAM** | 4096 token bağlam penceresi. |
| **Vektör Arama** | Kosinüs Benzerliği | **~19.2 ms** (100k vektör) | Sentetik test: 100.000 adet 384-boyutlu float32 vektörde Top-10 en yakın komşu taraması. |

> *Hız Notu: Yukarıdaki çıkarım hızları doğrudan 6 çekirdekli AVX2 CPU SIMD modunu yansıtmaktadır. CUDA/cuBLAS ile derlenmiş kütüphanelerde RTX 3060 Ti üzerinde bu değerler 50-85+ token/saniyeye ulaşmaktadır.*

---

### 4. Kurulum ve Doğrulama

```bash
# 1. Depoyu klonlayın
git clone https://github.com/Shura5860/LocalAIProject.git
cd LocalAIProject

# 2. Birim test paketini çalıştırın (24 test dosyası)
./.venv/bin/python -m unittest discover Rust-Python-Vector-Engine/tests -v

# 3. Uygulamayı başlatın (FastAPI sunucusu ve Masaüstü arayüzü)
./start_assistant.sh
```

---

<div align="center">
<b>AURA-CORE: Engineered with rigorous architectural standards. Dual licensed under AGPLv3 and Commercial EULA.</b>
</div>
