"""
Corten Desktop Wayland Environment Automation Tools for AURA-CORE.
Enables the local LLM agent to optionally query and control desktop hardware,
sound, brightness, screenshots, windows, workspaces, notifications, and system state
when running within a Corten / Wayland desktop session.
"""

import os
import shutil
import subprocess
from typing import Dict, Any, Optional, List
from api_server.app.tools.base import tool, Tool


def _resolve_corten_bin(name: str) -> Optional[str]:
    """
    Finds a Corten or system binary in PATH, CORTEN_BIN_DIR, or standard binary directories.
    Avoids hardcoded user paths to maintain portability across installations.
    """
    # 1. Explicit environment override
    custom_dir = os.environ.get("CORTEN_BIN_DIR")
    if custom_dir:
        candidate = os.path.join(custom_dir, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    # 2. PATH lookup
    which_path = shutil.which(name)
    if which_path:
        return which_path

    # 3. Standard Linux system paths
    for base in ["/usr/local/bin", "/usr/bin", "/bin"]:
        candidate = os.path.join(base, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    return None


@tool(
    name="corten_set_volume",
    description="Corten masaüstü ses seviyesini 0-100 arasında bir yüzdeye ayarlar. Parametre: 'level_pct' (int)."
)
def corten_set_volume(level_pct: int) -> str:
    level = max(0, min(100, int(level_pct)))
    decimal_val = level / 100.0
    wpctl_bin = _resolve_corten_bin("wpctl")
    if not wpctl_bin:
        return "Ses ayarlanamadı: 'wpctl' (WirePlumber/PipeWire) sistemde bulunamadı."
    try:
        subprocess.run([wpctl_bin, "set-volume", "@DEFAULT_AUDIO_SINK@", f"{decimal_val:.2f}"], check=True)
        return f"Corten ses seviyesi %{level} olarak ayarlandı."
    except Exception as e:
        return f"Ses ayarlama hatası: {str(e)}"


@tool(
    name="corten_set_brightness",
    description="Corten masaüstü ekran parlaklığını 1-100 arasında bir yüzdeye ayarlar. Parametre: 'level_pct' (int)."
)
def corten_set_brightness(level_pct: int) -> str:
    level = max(1, min(100, int(level_pct)))
    b_bin = _resolve_corten_bin("brightnessctl")
    if not b_bin:
        return "Parlaklık ayarlanamadı: 'brightnessctl' sistemde bulunamadı."
    try:
        subprocess.run([b_bin, "s", f"{level}%"], check=True)
        return f"Corten ekran parlaklığı %{level} olarak ayarlandı."
    except Exception as e:
        return f"Parlaklık ayarlama hatası: {str(e)}"


@tool(
    name="corten_take_screenshot",
    description="Corten masaüstünde anlık ekran görüntüsü alır. Parametre: 'mode' ('fullscreen' veya 'selection')."
)
def corten_take_screenshot(mode: str = "fullscreen") -> str:
    snipper_bin = _resolve_corten_bin("corten-snipper") or _resolve_corten_bin("grim")
    if not snipper_bin:
        return "Ekran görüntüsü aracı bulunamadı ('corten-snipper' veya 'grim' gerekli)."
    try:
        if "corten-snipper" in snipper_bin:
            cmd = [snipper_bin, "--fullscreen"] if mode == "fullscreen" else [snipper_bin]
        else:
            # Fallback to grim (selection uses slurp geometry)
            if mode == "fullscreen":
                subprocess.Popen([snipper_bin])
            else:
                subprocess.Popen(["bash", "-c", f'{snipper_bin} -g "$(slurp)"'])
            return f"Ekran görüntüsü alma aracı tetiklendi ({mode})."
        subprocess.Popen(cmd)
        return f"Ekran görüntüsü alma aracı tetiklendi ({mode})."
    except Exception as e:
        return f"Ekran görüntüsü alma hatası: {str(e)}"


@tool(
    name="corten_system_power",
    description="Corten masaüstü güç ve kilit eylemlerini yürütür. Parametre: 'action' ('lock', 'sleep', 'poweroff', 'reboot')."
)
def corten_system_power(action: str) -> str:
    action = action.lower().strip()
    lock_bin = _resolve_corten_bin("corten-lock") or _resolve_corten_bin("swaylock")
    try:
        if action == "lock":
            if not lock_bin:
                return "Ekran kilitleyici bulunamadı ('corten-lock' veya 'swaylock' gerekli)."
            subprocess.Popen([lock_bin])
            return "Ekran kilitlendi."
        elif action == "sleep":
            subprocess.run(["systemctl", "suspend"], check=True)
            return "Sistem uyku moduna alındı."
        elif action == "poweroff":
            subprocess.run(["systemctl", "poweroff"], check=True)
            return "Sistem kapatılıyor."
        elif action == "reboot":
            subprocess.run(["systemctl", "reboot"], check=True)
            return "Sistem yeniden başlatılıyor."
        else:
            return f"Bilinmeyen eylem: {action}. Desteklenenler: lock, sleep, poweroff, reboot"
    except Exception as e:
        return f"Güç eylemi hatası: {str(e)}"


@tool(
    name="corten_switch_workspace",
    description="Corten kompozitöründe belirtilen numaralı çalışma alanına (1-9) geçer. Parametre: 'workspace_num' (int)."
)
def corten_switch_workspace(workspace_num: int) -> str:
    ws = max(1, min(9, int(workspace_num)))
    ctl_bin = _resolve_corten_bin("cortenctl")
    if not ctl_bin:
        return "Çalışma alanı değiştirilemedi: 'cortenctl' sistemde bulunamadı."
    try:
        subprocess.run([ctl_bin, "action", "workspace", str(ws)], capture_output=True, text=True, check=True)
        return f"Corten kompozitörü {ws}. çalışma alanına geçirildi."
    except Exception as e:
        return f"Çalışma alanı değiştirme hatası: {str(e)}"


@tool(
    name="corten_window_action",
    description="Corten pencere yöneticisi eylemlerini yürütür. Parametre: 'action' ('toggle-overview', 'toggle-desktop', 'reload', 'focus')."
)
def corten_window_action(action: str, target_id: Optional[str] = None) -> str:
    action = action.lower().strip()
    ctl_bin = _resolve_corten_bin("cortenctl")
    if not ctl_bin:
        return "Pencere eylemi yürütülemedi: 'cortenctl' sistemde bulunamadı."
    try:
        if action == "toggle-overview":
            subprocess.run([ctl_bin, "action", "toggle-overview"], check=True)
            return "Pencere genel bakış modu değiştirildi."
        elif action == "toggle-desktop":
            subprocess.run([ctl_bin, "action", "toggle-desktop"], check=True)
            return "Masaüstü görünümü değiştirildi."
        elif action == "reload":
            subprocess.run([ctl_bin, "action", "reload"], check=True)
            return "Corten kompozitör yapılandırması yeniden yüklendi."
        elif action == "focus" and target_id:
            subprocess.run([ctl_bin, "action", "focus", str(target_id)], check=True)
            return f"{target_id} kimlikli pencereye odaklanıldı."
        else:
            return "Desteklenen eylemler: toggle-overview, toggle-desktop, reload, focus"
    except Exception as e:
        return f"Pencere eylemi hatası: {str(e)}"


@tool(
    name="corten_list_windows",
    description="Corten kompozitöründe o an açık olan tüm pencerelerin listesini (başlık, uygulama kimliği, geometri) JSON formatında getirir."
)
def corten_list_windows() -> str:
    ctl_bin = _resolve_corten_bin("cortenctl")
    if not ctl_bin:
        return "Pencere listesi alınamadı: 'cortenctl' sistemde bulunamadı."
    try:
        res = subprocess.run([ctl_bin, "action", "windows"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception as e:
        return f"Pencere listesi alınamadı: {str(e)}"


@tool(
    name="corten_toggle_night_light",
    description="Corten masaüstünde göz yormayan sıcak tonlu Gece Işığını (wlsunset) açar veya kapatır."
)
def corten_toggle_night_light() -> str:
    wlsunset_bin = _resolve_corten_bin("wlsunset")
    if not wlsunset_bin:
        return "Gece ışığı kontrol edilemedi: 'wlsunset' sistemde bulunamadı."
    try:
        is_running = subprocess.run(["pgrep", "-f", "wlsunset"], capture_output=True).returncode == 0
        if is_running:
            subprocess.run(["pkill", "-f", "wlsunset"])
            return "Gece ışığı devre dışı bırakıldı (Doğal ekran renkleri)."
        else:
            subprocess.Popen([wlsunset_bin, "-t", "4000", "-T", "6500"])
            return "Gece ışığı aktif edildi (Göz yormayan sıcak tonlar)."
    except Exception as e:
        return f"Gece ışığı değiştirilemedi: {str(e)}"


@tool(
    name="corten_notify",
    description="Corten bildirim servisi üzerinden masaüstüne bildirim gönderir. Parametreler: 'title' (str), 'message' (str)."
)
def corten_notify(title: str, message: str) -> str:
    notify_bin = _resolve_corten_bin("notify-send")
    if not notify_bin:
        return f"Bildirim gönderilemedi: 'notify-send' sistemde bulunamadı. (Mesaj: {title} - {message})"
    try:
        subprocess.run([notify_bin, title, message], check=True)
        return f"Bildirim masaüstüne gönderildi: '{title}'"
    except Exception as e:
        return f"Bildirim gönderme hatası: {str(e)}"


CORTEN_TOOLS: List[Tool] = [
    corten_set_volume,
    corten_set_brightness,
    corten_take_screenshot,
    corten_system_power,
    corten_switch_workspace,
    corten_window_action,
    corten_list_windows,
    corten_toggle_night_light,
    corten_notify,
]
