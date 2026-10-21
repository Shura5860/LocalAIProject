import os
import subprocess
from typing import Dict, Any, List
from api_server.app.tools.base import tool

def _get_base_workspace() -> str:
    try:
        from api_server.app.services.workspace_service import workspace_service
        return workspace_service.get_effective_workspace()
    except Exception:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))

def _validate_safe_path(path: str) -> str:
    """Yapay zekanın proje klasörü dışına çıkmasını engelleyen güvenlik sandbox'ı."""
    base_ws = _get_base_workspace()
    full_path = os.path.abspath(os.path.join(base_ws, path)) if not os.path.isabs(path) else os.path.abspath(path)
    if not full_path.startswith(base_ws):
        raise PermissionError(f"Güvenlik İhlali: Belirtilen yol ('{path}') proje çalışma alanı dışındadır!")
    return full_path

@tool(
    name="read_file",
    description="Proje dizinindeki bir kaynak kod veya metin dosyasının içeriğini okur. Parametre: 'path'."
)
def read_file(path: str) -> str:
    try:
        safe_path = _validate_safe_path(path)
        if not os.path.exists(safe_path):
            return f"Hata: Dosya bulunamadı: {path}"
        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return content
    except Exception as e:
        return f"Dosya okuma hatası: {str(e)}"

from api_server.app.core.guardrails import backup_file_before_write, assess_command_risk

@tool(
    name="write_file",
    description="Proje dizininde yeni bir dosya oluşturur veya mevcut bir dosyanın içeriğini günceller. Parametreler: 'path', 'content'."
)
def write_file(path: str, content: str) -> str:
    try:
        safe_path = _validate_safe_path(path)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        # Etik Kalkanı: Üzerine yazmadan önce otomatik yedek al
        backup_file_before_write(safe_path)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Dosya başarıyla kaydedildi (Otomatik yedek alındı): {path} ({len(content)} karakter)"
    except Exception as e:
        return f"Dosya yazma hatası: {str(e)}"

@tool(
    name="list_files",
    description="Proje dizinindeki veya alt klasörlerdeki dosya ve dizinleri listeler. Parametre: 'directory' (varsayılan: '.')."
)
def list_files(directory: str = ".") -> List[str]:
    try:
        safe_path = _validate_safe_path(directory)
        if not os.path.exists(safe_path):
            return [f"Hata: Dizin bulunamadı: {directory}"]
        items = os.listdir(safe_path)
        # .git, __pycache__, target, .venv gibi devasa klasörleri filtrele
        filtered = [
            item + ("/" if os.path.isdir(os.path.join(safe_path, item)) else "")
            for item in sorted(items)
            if item not in [".git", "__pycache__", ".venv", "target"]
        ]
        return filtered
    except Exception as e:
        return [f"Listeleme hatası: {str(e)}"]

@tool(
    name="git_status",
    description="Proje reposundaki değiştirilmiş, eklenmiş veya silinmiş dosyaların Git durumunu (git status -s) listeler."
)
def git_status() -> str:
    try:
        res = subprocess.run(
            ["git", "status", "-s"],
            cwd=BASE_WORKSPACE,
            capture_output=True,
            text=True,
            timeout=15
        )
        out = res.stdout.strip()
        return out if out else "Çalışma dizini temiz (Hiçbir değişiklik yok)."
    except Exception as e:
        return f"Git status hatası: {str(e)}"

@tool(
    name="git_diff",
    description="Yapılan kod değişikliklerinin satır bazlı Git farkını (git diff) gösterir. Parametre: 'file_path' (isteğe bağlı)."
)
def git_diff(file_path: str = "") -> str:
    try:
        cmd = ["git", "diff"]
        if file_path:
            cmd.append(file_path)
        res = subprocess.run(
            cmd,
            cwd=BASE_WORKSPACE,
            capture_output=True,
            text=True,
            timeout=15
        )
        out = res.stdout.strip()
        return out if out else "Görüntülenecek Git farkı yok."
    except Exception as e:
        return f"Git diff hatası: {str(e)}"

@tool(
    name="run_terminal_command",
    description="Proje çalışma alanında derleme, test ve kontrol komutları çalıştırır (Örn: 'cargo check', 'pytest tests/test_crud.py')."
)
def run_terminal_command(command: str) -> str:
    # Gelişmiş Etik ve Güvenlik Analizi
    is_safe, msg = assess_command_risk(command)
    if not is_safe:
        return f"Güvenlik İhlali Engellendi: {msg}"

    try:
        res = subprocess.run(
            command,
            shell=True,
            cwd=_get_base_workspace(),
            capture_output=True,
            text=True,
            timeout=60
        )
        output = res.stdout + ("\nHata Çıktısı (stderr):\n" + res.stderr if res.stderr else "")
        return output.strip() if output.strip() else f"Komut başarıyla çalıştı (Çıkış kodu: {res.returncode})."
    except subprocess.TimeoutExpired:
        return "Komut zaman aşımına uğradı (60s)."
    except Exception as e:
        return f"Komut çalıştırma hatası: {str(e)}"
