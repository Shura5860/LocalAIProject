#!/usr/bin/env bash
# ==============================================================================
# 🚀 AURA-CORE: Official One-Line Automated Installer & Daemon Setup
# Sets up virtual environment, compiles native Rust engine, creates 'aura' CLI
# symlink in PATH, and optionally registers a systemd user daemon.
# ==============================================================================

set -e

CYAN="\033[96m"
GREEN="\033[92m"
YELLOW="\033[93m"
RED="\033[91m"
BOLD="\033[1m"
RESET="\033[0m"

echo -e "${CYAN}${BOLD}"
cat << "EOF"
    ╔═════════════════════════════════════════════════════════════╗
    ║        █████╗ ██╗   ██╗██████╗  █████╗        CORE          ║
    ║       ██╔══██╗██║   ██║██╔══██╗██╔══██╗       LOCAL AI      ║
    ║       ███████║██║   ██║██████╔╝███████║       SWARM ENGINE  ║
    ║       ██╔══██║██║   ██║██╔══██╗██╔══██║       RUST HNSW     ║
    ║       ██║  ██║╚██████╔╝██║  ██║██║  ██║                     ║
    ╚═════════════════════════════════════════════════════════════╝
EOF
echo -e "${RESET}"
echo -e "${BOLD}AURA-CORE: Yerel AI, Swarm ve Rust Vektör Motoru Kurulumu${RESET}\n"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd )"
cd "$PROJECT_ROOT"

# 1. Python Sürüm Denetimi
echo -e "${YELLOW}⚡ [1/5] Sistem Önkoşulları Denetleniyor...${RESET}"
if command -v python3 >/dev/null 2>&1; then
    PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo -e "   Python tespit edildi: ${GREEN}v$PY_VER${RESET}"
else
    echo -e "${RED}❌ Hata: python3 sistemde bulunamadı. Lütfen Python 3.11+ yükleyin.${RESET}"
    exit 1
fi

if command -v cargo >/dev/null 2>&1; then
    CARGO_VER=$(cargo --version | cut -d' ' -f2)
    echo -e "   Rust/Cargo tespit edildi: ${GREEN}v$CARGO_VER${RESET}"
else
    echo -e "${YELLOW}⚠️ Uyarı: 'cargo' sistemde bulunamadı. Önceden derlenmiş Rust kütüphanesi kullanılacak.${RESET}"
fi

# 2. Sanal Ortam (.venv)
echo -e "\n${YELLOW}📦 [2/5] Python Sanal Ortamı ve Bağımlılıklar Hazırlanıyor...${RESET}"
if [ ! -d ".venv" ]; then
    echo -e "   .venv oluşturuluyor..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet maturin "httpx[http2]" duckduckgo_search sentence-transformers psutil fastapi uvicorn llama-cpp-python

# 3. Rust Vektör Motoru Derleme
echo -e "\n${YELLOW}🦀 [3/5] Rust Süreç-İçi Vektör Motoru (PyO3 + HNSW) Kontrol Ediliyor...${RESET}"
if command -v maturin >/dev/null 2>&1 && command -v cargo >/dev/null 2>&1; then
    if [ -d "Rust-Python-Vector-Engine/vector_engine" ]; then
        echo -e "   Rust kütüphanesi 'maturin develop --release' ile derleniyor..."
        (cd Rust-Python-Vector-Engine/vector_engine && maturin develop --release --quiet)
        echo -e "   ${GREEN}✓ Rust motoru hazır.${RESET}"
    fi
else
    echo -e "   ${GREEN}✓ Mevcut derlenmiş kütüphane kullanılıyor.${RESET}"
fi

# 4. 'aura' CLI Komutunu PATH'e Ekleme
echo -e "\n${YELLOW}🔗 [4/5] 'aura' CLI Evrensel Symlink Yapılandırılıyor...${RESET}"
chmod +x "$PROJECT_ROOT/bin/aura"

BIN_DEST="$HOME/.local/bin"
mkdir -p "$BIN_DEST"
ln -sf "$PROJECT_ROOT/bin/aura" "$BIN_DEST/aura"

if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo -e "   ${YELLOW}İpucu: ~/.local/bin dizini PATH'te değil. ~/.bashrc veya ~/.zshrc içine ekleyin:${RESET}"
    echo -e "   ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
fi
echo -e "   ${GREEN}✓ $BIN_DEST/aura başarıyla bağlandı.${RESET}"

# 5. Systemd Kullanıcı Servisi (Opsiyonel Daemon)
echo -e "\n${YELLOW}⚙️ [5/5] Systemd Kullanıcı Daemon Yapılandırması...${RESET}"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"

cat << EOF > "$SYSTEMD_USER_DIR/aura.service"
[Unit]
Description=AURA-CORE Local AI & Multi-Agent Swarm Daemon
After=network.target

[Service]
Type=simple
WorkingDirectory="$PROJECT_ROOT"
ExecStart="$PROJECT_ROOT/bin/aura" serve --port 8000
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload 2>/dev/null || true

echo -e "   ${GREEN}✓ $SYSTEMD_USER_DIR/aura.service oluşturuldu.${RESET}"
echo -e "   Daemon'ı açılışta başlatmak için:"
echo -e "   ${CYAN}systemctl --user enable --now aura${RESET}"

echo -e "\n${GREEN}${BOLD}═════════════════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}🎉 AURA-CORE KURULUMU BAŞARIYLA TAMAMLANDI!${RESET}"
echo -e "${GREEN}${BOLD}═════════════════════════════════════════════════════════════════${RESET}"
echo -e "Kullanabileceğiniz temel komutlar:"
echo -e "  • ${CYAN}aura status${RESET}               : Donanım ve aktif model durumunu gör"
echo -e "  • ${CYAN}aura run${RESET}                  : Terminalde canlı sohbet başlat"
echo -e "  • ${CYAN}aura swarm \"<görev>\"${RESET}      : Mimar + Coder + Denetçi sürüsünü çalıştır"
echo -e "  • ${CYAN}aura models list${RESET}          : Yerel modelleri listele"
echo -e "  • ${CYAN}aura serve${RESET}                : API sunucusunu manuel başlat\n"

