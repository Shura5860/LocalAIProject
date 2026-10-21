# 🚀 Rust LLM Engine

[![Rust](https://img.shields.io/badge/Language-Rust-orange.svg)](https://www.rust-lang.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Architecture](https://img.shields.io/badge/Architecture-Llama--3%20%7C%20Qwen2-purple.svg)]()
[![Performance](https://img.shields.io/badge/Speed-18%2B%20tok%2Fs%20(CPU)-green.svg)]()

**Rust LLM Engine**, hiçbir harici ağır C/C++ veya Python kütüphanesine (PyTorch, llama.cpp, ONNX vb.) ihtiyaç duymadan, saf **Rust** diliyle sıfırdan geliştirilmiş ultra hızlı, minimalist bellekli ve **AVX2 / FMA SIMD** donanım ivmelendirmeli bir Büyük Dil Modeli (LLM) Çıkarım (Inference) Motorudur.

Proje, **Llama-3** mimarisindeki quantize GGUF modellerini (`Q4_K`, `Q6_K`) saf CPU üzerinde minimalist bellek footprint'i (`~320 MB`) ve yüksek hızla (`18+ tok/s`) çalıştırır. Ayrıca **Ratatui & Crossterm** ile donmayan 60 FPS interaktif bir Terminal Kullanıcı Arayüzü (TUI) sunar.

---

## 🌟 Öne Çıkan Özellikler & Kabiliyetler

- ⚡ **Saf CPU Üzerinde 18+ tok/s Hız:** AVX2 & FMA SIMD vektörleştirmesi ve Rayon çoklu çekirdek paralel matris-vektör çarpımı.
- 💾 **On-the-Fly Quantized GEMV:** Ağırlıklar RAM'de dekuantize edilmeden ham `Q4_K` / `Q6_K` baytları halinde tutulur ve doğrudan kaydedicilerde açılır (~1.2 GB yerine **~320 MB RAM**).
- 🚀 **Anında Açılış (Instant Model Loading):** Mmap (Memory Mapping) altyapısı sayesinde model yükleme süresi 2.5 saniyeden **< 50 ms** seviyesine inmiştir.
- 🔀 **FP16 KV-Cache Sıkıştırması:** Key ve Value matrisleri 16-bit float (`u16`) formatında saklanarak uzun sohbetlerde hafıza tüketimi %50 azaltılır.
- 🔒 **Zero-Allocation ScratchBuffer:** Decode döngüsündeki tüm katman geçişleri önceden ayrılmış tamponlar (`ScratchBuffer`) üzerinde gerçekleşir; işletim sistemi seviyesinde sıfır heap tahsisi yapılır.
- 🎨 **60 FPS Akıcı Terminal Arayüzü (TUI):** `Ratatui` ve `crossterm` ile çift başlıklı (async mpsc channel) mimari sayesinde sohbet ederken dahi donmayan canlı performans göstergeleri ve mesaj penceresi.
- 🎯 **Gelişmiş Örnekleme Pipeline'ı:** `Temperature`, `Top-K`, `Top-P (Nucleus)`, ve `Repetition Penalty` manipülasyonu ile insan benzeri akıcı ve yaratıcı metin üretimi.

---

## ⚡ Performans Metrikleri & Karşılaştırma

Aşağıdaki ölçümler **Llama-3 1B Q4_K_M** modeli ile standart bir tüketici işlemcisinde (CPU) gerçekleştirilmiştir:

| Metrik | Başlangıç (f32 Dekuantize) | On-the-Fly SIMD + Zero-Alloc (Rust LLM) | İyileşme Oranı |
| :--- | :--- | :--- | :--- |
| **Decode Hızı** | `4.32 tok/s` | **`17.91 tok/s`** | **~4.15x Hızlı** ⚡ |
| **Prefill Hızı** | `5.91 tok/s` | **`22.20 tok/s`** | **~3.75x Hızlı** ⚡ |
| **Gecikme (Latency)** | `231.55 ms/tok` | **`55.82 ms/tok`** | **~4.15x Düşük Gecikme** |
| **RAM Bellek Kullanımı** | `~1.2 GB` | **`~320 MB`** | **~3.75x Tasarruf** |
| **Model Yükleme Süresi** | `~2.5 saniye` | **`< 50 ms`** | **Anında Açılış** |

---

## 🦀 Neden Rust Kullandık?

Büyük Dil Modeli motorlarında genellikle C++ tercih edilse de, bu projede **Rust** seçilmesinin kritik mühendislik nedenleri şunlardır:

1. **Sıfır Maliyetli Soyutlamalar (Zero-Cost Abstractions):**
   Rust, yüksek seviyeli ve okunabilir kod yazmanıza izin verirken, derleme aşamasında bunları makine koduna sıfır performans kaybı ile dönüştürür.
2. **Çöp Toplayıcısız (GC-Free) Öngörülebilir Bellek Yönetimi:**
   Java veya Python gibi dillerde Garbage Collector (GC) duraklamaları decode sırasında tok/s dalgalanmalarına yol açar. Rust'ın *Ownership & Borrow Checker* kuralları sayesinde bellek mikro saniye hassasiyetinde yönetilir.
3. **Korkusuz Paralellik (Fearless Concurrency):**
   `Rayon` crate'i ile matris satırlarını CPU çekirdeklerine dağıtırken veri yarışları (data races) derleme zamanında engellenir.
4. **Doğrudan Donanım Kontrolü (SIMD Intrinsics):**
   `std::arch::x86_64` modülü sayesinde derleyicinin otomatik vektörleştirmesine güvenmek yerine doğrudan `_mm256_fmadd_ps` ve `_mm256_fmsub_ps` intrinsics komutları yazılabilir.

---

## 📐 Mimari Yapı (Architecture Overview)

Proje katmanlı ve modüler bir mimariye sahiptir:

```text
rust-llm-engine/
├── src/
│   ├── main.rs            # Giriş noktası (TUI ve Model yükleyici)
│   ├── tui.rs             # Ratatui & Crossterm 60 FPS UI döngüsü
│   ├── engine/
│   │   ├── block.rs       # Transformer katmanı (Attention & SwiGLU FFN)
│   │   ├── runner.rs      # Inference motoru ve mpsc kanal akışı
│   │   └── weights.rs     # QuantizedTensor (Q4_K, Q6_K) ve FP16 KVCache
│   ├── gguf/
│   │   ├── header.rs      # GGUF Binary header parser
│   │   └── loader.rs      # Mmap tensor okuyucu
│   ├── ops/
│   │   ├── norm.rs        # RMSNorm (in-place)
│   │   ├── rope.rs        # Llama-Style RoPE (Pair rotation)
│   │   ├── sampling.rs    # Top-K, Top-P, Temperature & Repetition Penalty
│   │   └── simd.rs        # AVX2 & FMA Donanımsal Vektör Çarpmaları
│   └── quant/
│       ├── f16.rs         # f32 <-> f16 IEEE 754 dönüştürücü
│       ├── q4_k.rs        # Q4_K On-the-Fly SIMD dekuantizasyon ve iç çarpım
│       └── q6_k.rs        # Q6_K On-the-Fly SIMD dekuantizasyon ve iç çarpım
```

---

## 🖼️ TUI Arayüz Tasarımı

```text
┌───────────────────────────┬────────────────────────────────────────────────────────┐
│ 📊 Status & Metrics       │ 💬 Chat Log (Scroll: ↑/↓)                              │
│ 🤖 Model: Llama-3 1B      │                                                        │
│ 📦 Quant: Q4_K/Q6_K SIMD  │ [User]: Write a story about a small village...      │
│ 💾 KV-Cache: FP16         │ [AI]: Once upon a time, in a small village...      │
│ ⚡ Status: Generating...  │                                                        │
│ 🚀 Prefill: 22.20 tok/s   │                                                        │
│ 🔥 Decode: 17.91 tok/s    │                                                        │
│ ⏱️ Latency: 55.82 ms/tok  │                                                        │
├───────────────────────────┴────────────────────────────────────────────────────────┤
│ ⌨️ Mesajınızı yazın (Enter: Gönder, Esc: Çıkış)                                   │
└────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Kurulum ve Çalıştırma

### Gereksinimler
- **Rust Toolchain** (1.75 veya üstü)
- AVX2 & FMA destekli 64-bit x86 İşlemci

### 1. Depoyu Klonlayın
```bash
git clone https://github.com/kullaniciadi/rust-llm-engine.git
cd rust-llm-engine
```

### 2. GGUF Modelini İndirin
Llama-3 1B GGUF formatındaki modeli proje kök dizinine `model.gguf` ismiyle yerleştirin.

### 3. Yerel İşlemci Optimizasyonu İle Çalıştırın
AVX2 / FMA komut setlerinin aktif olması için native CPU bayrağıyla derleyip çalıştırın:

**Windows (PowerShell):**
```powershell
$env:RUSTFLAGS="-C target-cpu=native"; cargo run --release
```

**Linux / macOS:**
```bash
RUSTFLAGS="-C target-cpu=native" cargo run --release
```

---

## 📜 Lisans

Bu proje [MIT Lisansı](LICENSE) altında lisanslanmıştır.
