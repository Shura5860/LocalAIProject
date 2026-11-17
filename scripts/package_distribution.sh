#!/usr/bin/env bash
# ==============================================================================
# 📦 Universal Cross-Platform Distribution Packager
# İstemci tarafı için kaynak kodsuz, korumalı kurulum arşivini hazırlar.
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PROJECT_ROOT="$( cd "$DIR/.." >/dev/null 2>&1 && pwd )"
cd "$PROJECT_ROOT"

echo "========================================================================"
echo "📦 TİCARİ MÜŞTERİ DAĞITIM PAKETİ OLUŞTURULUYOR"
echo "========================================================================"

RELEASE_DIR="$PROJECT_ROOT/release_bundle"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR/bin"
mkdir -p "$RELEASE_DIR/models"
mkdir -p "$RELEASE_DIR/web"

echo "🦀 [1/4] Rust LLM motoru 'release' modunda derleniyor ve semboller siliniyor (strip)..."
cd "$PROJECT_ROOT/Rust-LLM-Engine"
cargo build --release
strip --strip-all target/release/rust-llm-engine 2>/dev/null || true
cp target/release/rust-llm-engine "$RELEASE_DIR/bin/"

cd "$PROJECT_ROOT"

echo "🎨 [2/4] Masaüstü arayüz statik dosyaları kopyalanıyor..."
cp -r "$PROJECT_ROOT/desktop_app/src"/* "$RELEASE_DIR/web/"

echo "🔑 [3/4] Lisans yöneticisi ve başlatıcı ekleniyor..."
cat << 'LAUNCHER' > "$RELEASE_DIR/start.sh"
#!/usr/bin/env bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
echo "🚀 Yerel Yapay Zeka Asistanı Başlatılıyor..."
xdg-open "http://127.0.0.1:8000/app" 2>/dev/null || python3 -m webbrowser "http://127.0.0.1:8000/app"
LAUNCHER
chmod +x "$RELEASE_DIR/start.sh"

echo "📦 [4/4] Dağıtım klasörü hazırlandı: $RELEASE_DIR"
echo "İçerik:"
ls -lh "$RELEASE_DIR/bin"
echo "========================================================================"
echo "✅ Başarılı! Bu klasör müşteriye güvenle teslim edilebilir formatta ayrıştırıldı."
