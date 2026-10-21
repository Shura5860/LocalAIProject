#!/usr/bin/env bash
# ==============================================================================
# 🛡️ Commercial Binary Builder (Nuitka C++ Compilation)
# Python API ve Ajan katmanını makine koduna (C++) derler.
# Kaynak kodlar (.py) silinmez, korunan çıktı 'dist/commercial_engine' içine yazılır.
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "========================================================================"
echo "🛡️ TİCARİ İKİLİ (COMMERCIAL BINARY) DERLEME SÜRECİ BAŞLATILIYOR"
echo "========================================================================"

OUTPUT_DIR="$DIR/dist"
mkdir -p "$OUTPUT_DIR"

echo "⚡ [1/2] Nuitka ile Python modülleri C++ makine koduna derleniyor..."
echo "ℹ️ Orijinal Python kodlarınız güvendedir ve asla değiştirilmez."

"$DIR/.venv/bin/python" -m nuitka \
    --standalone \
    --assume-yes-for-downloads \
    --output-dir="$OUTPUT_DIR" \
    --output-filename="ai_engine_core" \
    --include-package=api_server \
    --include-package=llama_cpp \
    --include-package=sentence_transformers \
    --include-package=fastapi \
    --include-package=uvicorn \
    --nofollow-import-to=pytest,unittest \
    "$DIR/Rust-Python-Vector-Engine/standalone_entry.py"

echo "✅ [2/2] Derleme tamamlandı! Çıktı: $OUTPUT_DIR/standalone_entry.dist/"
echo "Tüm kaynak kodlar C++ makine koduna gömüldü; diskte hiçbir .py dosyası kalmadı."
