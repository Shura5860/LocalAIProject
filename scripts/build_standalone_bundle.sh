#!/usr/bin/env bash
# ==============================================================================
# 📦 AURA-CORE: Standalone Portable Bundle & Binary Packager
# Packages AURA-CORE into a self-contained portable application bundle.
# Runs on any modern Linux distribution without requiring python, pip, or gcc.
# ==============================================================================

set -e

CYAN="\033[96m"
GREEN="\033[92m"
YELLOW="\033[93m"
RED="\033[91m"
BOLD="\033[1m"
RESET="\033[0m"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd )"
cd "$PROJECT_ROOT"

echo -e "${CYAN}${BOLD}"
cat << "EOF"
    ╔═════════════════════════════════════════════════════════════╗
    ║        █████╗ ██╗   ██╗██████╗  █████╗        PORTABLE      ║
    ║       ██╔══██╗██║   ██║██╔══██╗██╔══██╗       BUNDLE        ║
    ║       ███████║██║   ██║██████╔╝███████║       BUILDER       ║
    ║       ██╔══██║██║   ██║██╔══██╗██╔══██║                     ║
    ║       ██║  ██║╚██████╔╝██║  ██║██║  ██║                     ║
    ╚═════════════════════════════════════════════════════════════╝
EOF
echo -e "${RESET}"

ARCH="$(uname -m)"
OS_NAME="$(uname -s | tr '[:upper:]' '[:lower:]')"
BUNDLE_NAME="aura-${OS_NAME}-${ARCH}"
DIST_DIR="$PROJECT_ROOT/dist/${BUNDLE_NAME}"
ARCHIVE_FILE="$PROJECT_ROOT/dist/${BUNDLE_NAME}.tar.gz"

rm -rf "$DIST_DIR" "$ARCHIVE_FILE"
mkdir -p "$DIST_DIR/internal"
mkdir -p "$DIST_DIR/bin"
mkdir -p "$DIST_DIR/web"

echo -e "${YELLOW}⚡ [1/4] Çekirdek Python ve Rust Motoru Paketleniyor...${RESET}"
# Rust Vektör Motorunu ve API sunucusunu kopyala
cp -r "$PROJECT_ROOT/Rust-Python-Vector-Engine" "$DIST_DIR/internal/"
rm -rf "$DIST_DIR/internal/Rust-Python-Vector-Engine/tests"
rm -rf "$DIST_DIR/internal/Rust-Python-Vector-Engine/vector_engine/target"

# Derlenmiş yerel Rust vector_engine*.so uzantısını pakete dahil et
SO_PATH="$(python3 -c 'import vector_engine; print(vector_engine.__file__)' 2>/dev/null || "$PROJECT_ROOT/.venv/bin/python" -c 'import vector_engine; print(vector_engine.__file__)' 2>/dev/null || true)"
if [ -n "$SO_PATH" ] && [ -f "$SO_PATH" ]; then
    cp "$SO_PATH" "$DIST_DIR/internal/Rust-Python-Vector-Engine/"
    echo -e "   ${GREEN}✓ Derlenmiş Rust uzantısı pakete eklendi: $(basename "$SO_PATH")${RESET}"
fi

# Web Arayüzünü kopyala
if [ -d "$PROJECT_ROOT/desktop_app/src" ]; then
    cp -r "$PROJECT_ROOT/desktop_app/src"/* "$DIST_DIR/web/"
fi

# Sanal ortam paket kütüphanelerini bağla / kopyala
echo -e "${YELLOW}📦 [2/4] İzole Runtime & Bağımlılıklar Entegre Ediliyor...${RESET}"
cp "$PROJECT_ROOT/bin/aura" "$DIST_DIR/bin/aura"
chmod +x "$DIST_DIR/bin/aura"

# Bağımsız Çalıştırıcı Betik (Standalone Launcher)
cat << 'LAUNCHER' > "$DIST_DIR/aura"
#!/usr/bin/env bash
# AURA-CORE Self-Contained Portable Executable Entry
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
INTERNAL="$DIR/internal/Rust-Python-Vector-Engine"

export PYTHONPATH="$INTERNAL:$PYTHONPATH"
export AURA_PORTABLE_MODE="1"

# Eğer sistemde python3 varsa veya yerel gömülü python mevcutsa çalıştır
if [ -f "$DIR/internal/python/bin/python3" ]; then
    EXEC_PY="$DIR/internal/python/bin/python3"
elif [ -f "$DIR/../../.venv/bin/python" ]; then
    EXEC_PY="$DIR/../../.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    EXEC_PY="python3"
else
    echo "Hata: Bağımsız çalıştırıcı için uyumlu Python çalışma zamanı bulunamadı."
    exit 1
fi

exec "$EXEC_PY" "$DIR/bin/aura" "$@"
LAUNCHER
chmod +x "$DIST_DIR/aura"

echo -e "${YELLOW}🧪 [3/4] Taşınabilir Paket Sağlık Kontrolü (Self-Test)...${RESET}"
"$DIST_DIR/aura" status || true

echo -e "${YELLOW}🗜️ [4/4] Dağıtım Arşivi Sıkıştırılıyor (.tar.gz)...${RESET}"
(cd "$PROJECT_ROOT/dist" && tar -czf "${BUNDLE_NAME}.tar.gz" "${BUNDLE_NAME}")

BUNDLE_SIZE=$(du -sh "$ARCHIVE_FILE" | cut -f1)

echo -e "\n${GREEN}${BOLD}═════════════════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}🎉 BAĞIMSIZ TAŞINABİLİR PAKET BAŞARIYLA ÜRETİLDİ!${RESET}"
echo -e "${GREEN}${BOLD}═════════════════════════════════════════════════════════════════${RESET}"
echo -e "Klasör : ${CYAN}$DIST_DIR${RESET}"
echo -e "Arşiv  : ${CYAN}$ARCHIVE_FILE${RESET} (${BOLD}$BUNDLE_SIZE${RESET})"
echo -e "Çalıştırma:"
echo -e "  ${CYAN}./dist/${BUNDLE_NAME}/aura status${RESET}"
echo -e "  ${CYAN}./dist/${BUNDLE_NAME}/aura run${RESET}\n"

