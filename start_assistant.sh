#!/usr/bin/env bash
# ==============================================================================
# 🚀 AURA Studio — One-Click Production Launcher
# Tek tıkla arka plan API motorunu ve masaüstü arayüzünü ayağa kaldırır.
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "⚡ [1/3] Sanal ortam ve bağımlılıklar kontrol ediliyor..."
if [ ! -d ".venv" ]; then
    echo "❌ Hata: .venv dizini bulunamadı!"
    exit 1
fi

echo "🚀 [2/3] AURA-CORE Arka Plan Motoru Başlatılıyor (127.0.0.1:8000)..."
"$DIR/.venv/bin/python" -m uvicorn api_server.app.main:app --host 127.0.0.1 --port 8000 --app-dir "$DIR/Rust-Python-Vector-Engine" > "$DIR/server.log" 2>&1 &
SERVER_PID=$!

cleanup() {
    echo -e "\n🛑 Kapatılıyor... Arka plan sunucusu durduruluyor (PID: $SERVER_PID)..."
    kill "$SERVER_PID" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

echo "⏳ Sunucu hazır olana kadar bekleniyor..."
READY=0
for _ in $(seq 1 30); do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "❌ Sunucu beklenmedik şekilde kapandı! Son loglar:"
        tail -n 20 "$DIR/server.log"
        exit 1
    fi
    if "$DIR/.venv/bin/python" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/db/status', timeout=1)" >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 0.5
done

if [ "$READY" -ne 1 ]; then
    echo "⚠️ Sunucu zamanında yanıt vermedi (server.log dosyasını kontrol edin)."
fi

echo "🖥️ [3/3] AURA Studio Masaüstü Uygulaması Başlatılıyor..."
if [ -f "$DIR/desktop_app/src-tauri/target/release/aura_studio" ]; then
    "$DIR/desktop_app/src-tauri/target/release/aura_studio"
elif [ -f "$DIR/desktop_app/src-tauri/target/debug/aura_studio" ]; then
    "$DIR/desktop_app/src-tauri/target/debug/aura_studio"
elif [ -f "$DIR/desktop_app/src-tauri/target/release/desktop_app" ]; then
    "$DIR/desktop_app/src-tauri/target/release/desktop_app"
elif [ -f "$DIR/desktop_app/src-tauri/target/debug/desktop_app" ]; then
    "$DIR/desktop_app/src-tauri/target/debug/desktop_app"
else
    echo "🌐 Masaüstü binary bulunamadı, tarayıcıda açılıyor..."
    xdg-open "http://127.0.0.1:8000/" 2>/dev/null || python3 -m webbrowser "http://127.0.0.1:8000/"
    wait "$SERVER_PID"
fi
