# AURA-CORE & Corten Desktop (Wayland) Entegrasyon Rehberi

Bu belge, **AURA-CORE** yerel yapay zeka motorunun **Corten Desktop (Wayland Pencere Yöneticisi & Masaüstü Ortamı)** ile nasıl ayrık, modüler ve güvenli bir şekilde entegre edildiğini açıklar.

---

## 🏛️ Mimari Tasarım: Headless Çekirdek & Eklenti Profili

AURA-CORE, varsayılan olarak **her işletim sisteminde çalışabilen bağımsız bir yerel yapay zeka motorudur**. Corten Desktop araçları çekirdeğe gömülü (hardcoded) değildir; isteğe bağlı bir **profil (extension profile)** olarak yüklenir.

```
┌────────────────────────────────────────────────────────┐
│                      AURA-CORE                         │
│  (Bağımsız, Headless Yerel Ajan & Vektör Motoru)       │
│  - FastAPI REST / SSE Sunucusu (Port 8000)             │
│  - In-Process Rust Vektör Veritabanı (HNSW)            │
│  - GGUF Yerel Çıkarım                                  │
│  - Standart Araçlar (Dosya, Terminal, Web, Hesap)      │
└──────────────────────────┬─────────────────────────────┘
                           │ 
          ┌────────────────┴────────────────┐
          ▼                                 ▼
┌───────────────────────┐       ┌───────────────────────────────┐
│ Standalone / Genel    │       │ Corten Desktop Profili        │
│ Kullanım              │       │ (`AURA_TOOL_PROFILE=corten`)  │
│ - Tauri OLED UI       │       │ - cortenctl pencere yönetimi  │
│ - macOS, Windows,     │       │ - Ses (wpctl) & Parlaklık     │
│   standart Linux      │       │ - Ekran yakalama (snipper)    │
│                       │       │ - Güç/Kilit (HITL Korumalı)   │
└───────────────────────┘       └───────────────────────────────┘
```

---

## ⚙️ Yapılandırma ve Profili Aktif Etme

Corten araç setini aktif etmek için iki yöntem bulunur:

### 1. Ortam Değişkeni ile (Tavsiye Edilen)
AURA-CORE sunucusunu başlatırken `AURA_TOOL_PROFILE` veya `CORTEN_ENABLED` değişkenini verin:

```bash
# Seçenek 1:
export AURA_TOOL_PROFILE=corten
./start_assistant.sh

# Seçenek 2:
export CORTEN_ENABLED=true
./start_assistant.sh
```

### 2. Özel İkili Dosya Dizini (İsteğe Bağlı)
Eğer Corten ikili dosyalarınız (`cortenctl`, `corten-snipper`, `corten-lock`) standart `$PATH` dizinlerinde değilse, dizini belirtebilirsiniz:

```bash
export CORTEN_BIN_DIR="/usr/local/bin"
```

---

## 🛠️ Corten Profilinin Sağladığı Araçlar

| Araç Adı | Açıklama | Kullanılan Sistem Komutu | HITL Onayı Gerekli mi? |
| :--- | :--- | :--- | :--- |
| `corten_set_volume` | Ses seviyesini %0-100 arasında ayarlar | `wpctl set-volume` | Hayır (Otomatik) |
| `corten_set_brightness` | Ekran parlaklığını ayarlar | `brightnessctl s` | Hayır (Otomatik) |
| `corten_take_screenshot` | Tam ekran veya bölgesel ekran görüntüsü alır | `corten-snipper` / `grim` | Hayır (Otomatik) |
| `corten_switch_workspace`| Kompozitörde çalışma alanı değiştirir (1-9) | `cortenctl action workspace` | Hayır (Otomatik) |
| `corten_window_action` | Genel bakış (Exposé), masaüstü göster, odak | `cortenctl action` | Hayır (Otomatik) |
| `corten_list_windows` | Açık pencerelerin geometrisi ve başlıklarını listeler | `cortenctl action windows` | Hayır (Otomatik) |
| `corten_toggle_night_light`| Sıcak tonlu gece ışığını açar/kapatır | `wlsunset` | Hayır (Otomatik) |
| `corten_notify` | Masaüstüne akrilik bildirim kartı gönderir | `notify-send` | Hayır (Otomatik) |
| `corten_system_power` | Kilit, uyku, kapatma veya yeniden başlatma | `systemctl` / `corten-lock` | **Evet (HITL Onayı Şart)** |

---

## 🛡️ Güvenlik ve İnsan Onayı (Human-in-the-Loop)

Kritik sistem eylemleri (`corten_system_power` ile kapatma veya yeniden başlatma gibi) doğrudan çalıştırılmaz. AURA-CORE'un **HITL Geçidi (Human-In-The-Loop Gateway)** bu isteği karantinaya alır ve masaüstü arayüzünden veya bildirim kutusundan kullanıcı onayı bekler.

---

## 🚀 Corten Desktop Tarafından Daemon Olarak Başlatma

Corten Desktop (Wayland), AURA-CORE'u bir `systemd` kullanıcı servisi olarak arka planda yönetebilir:

```ini
# ~/.config/systemd/user/aura-core.service
[Unit]
Description=AURA-CORE Local Agentic AI Daemon
After=graphical-session.target

[Service]
Type=simple
Environment="AURA_TOOL_PROFILE=corten"
WorkingDirectory=%h/Projects/AIProject
ExecStart=%h/Projects/AIProject/start_assistant.sh
Restart=on-failure

[Install]
WantedBy=default.target
```
