#!/usr/bin/env bash
# ==============================================================================
# 🚀 Personal AI Assistant - One-Click Production Launcher
# Tek tıkla arka plan API motorunu ve OLED Masaüstü Arayüzünü ayağa kaldırır.
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "⚡ [1/3] Sanal ortam ve bağımlılıklar kontrol ediliyor..."
if [ ! -d ".venv" ]; then
    echo "❌ Hata: .venv dizini bulunamadı!"
    exit 1
fi

echo "🚀 [2/3] Yerel AI Arka Plan Motoru Başlatılıyor (Port 8000)..."
# Eğer 8000 portunda eski bir süreç varsa temizle
fuser -k 8000/tcp 2>/dev/null || true

# Arka planda FastAPI sunucusunu başlat
"$DIR/.venv/bin/python" -m uvicorn api_server.app.main:app --host 127.0.0.1 --port 8000 --app-dir "$DIR/Rust-Python-Vector-Engine" > "$DIR/server.log" 2>&1 &
SERVER_PID=$!

# Sunucunun uyanmasını bekle
echo "⏳ Sunucu hazır olana kadar bekleniyor..."
sleep 2

cleanup() {
    echo -e "\n🛑 Kapatılıyor... Arka plan sunucusu durduruluyor (PID: $SERVER_PID)..."
    kill $SERVER_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

echo "🖥️ [3/3] OLED Masaüstü Uygulaması Başlatılıyor..."
if [ -f "$DIR/desktop_app/src-tauri/target/debug/desktop_app" ]; then
    "$DIR/desktop_app/src-tauri/target/debug/desktop_app"
else
    echo "🌐 Masaüstü binary henüz derlenmedi veya bulunamadı, tarayıcıda açılıyor..."
    xdg-open "http://127.0.0.1:8000/app" 2>/dev/null || python3 -m webbrowser "http://127.0.0.1:8000/app"
    wait $SERVER_PID
fi
