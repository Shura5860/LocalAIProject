import os
import shutil
import subprocess
from typing import Dict, Any, List, Optional
from api_server.app.tools.base import tool
from api_server.app.core.guardrails import backup_file_before_write, assess_command_risk


def _get_base_workspace() -> str:
    try:
        from api_server.app.services.workspace_service import workspace_service
        return workspace_service.get_effective_workspace()
    except Exception:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))


def _validate_safe_path(path: str) -> str:
    """Yapay zekanın proje klasörü dışına çıkmasını engelleyen güvenlik sandbox'ı."""
    base_ws = os.path.abspath(_get_base_workspace())
    full_path = os.path.abspath(os.path.join(base_ws, path)) if not os.path.isabs(path) else os.path.abspath(path)
    try:
        common = os.path.commonpath([base_ws, full_path])
    except ValueError:
        common = ""
    if common != base_ws:
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


@tool(
    name="write_file",
    description="Proje dizininde yeni bir dosya oluşturur veya mevcut bir dosyayı tamamen sıfırdan yazar. Parametreler: 'path', 'content'."
)
def write_file(path: str, content: str) -> str:
    try:
        safe_path = _validate_safe_path(path)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        backup_file_before_write(safe_path)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Dosya başarıyla kaydedildi (Otomatik yedek alındı): {path} ({len(content)} karakter)"
    except Exception as e:
        return f"Dosya yazma hatası: {str(e)}"


@tool(
    name="apply_diff",
    description=(
        "Dosyayı baştan yazmak yerine sadece değişecek hedef bloğu cerrahi olarak değiştirir (Aider/Cursor stili). "
        "Parametreler: 'path' (str), 'search_block' (değiştirilecek eski kod parçası), 'replace_block' (yerine geçecek yeni kod)."
    )
)
def apply_diff(path: str, search_block: str, replace_block: str) -> str:
    try:
        safe_path = _validate_safe_path(path)
        if not os.path.exists(safe_path):
            return f"Hata: Dosya bulunamadı: {path}"

        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            original = f.read()

        # 1. Birebir eşleşme ara
        if search_block in original:
            occurrences = original.count(search_block)
            if occurrences > 1:
                return (
                    f"Hata: 'search_block' dosya içinde {occurrences} kez bulundu. "
                    "Belirsizliği önlemek için lütfen etrafındaki birkaç satırı da ekleyerek bloğu genişletin."
                )
            new_content = original.replace(search_block, replace_block, 1)
        else:
            # 2. Satır sonu (\r\n vs \n) normalizasyonu ile dene
            norm_orig = original.replace("\r\n", "\n")
            norm_search = search_block.replace("\r\n", "\n")
            norm_replace = replace_block.replace("\r\n", "\n")

            if norm_search in norm_orig:
                if norm_orig.count(norm_search) > 1:
                    return "Hata: 'search_block' dosya içinde birden fazla bulundu. Lütfen daha fazla bağlam satırı ekleyin."
                new_content = norm_orig.replace(norm_search, norm_replace, 1)
            else:
                # 3. Fuzzy Matching (Boşluk/Girinti ve Benzerlik Toleransı - Aider stili)
                import difflib
                search_lines = [l.strip() for l in norm_search.splitlines() if l.strip()]
                orig_lines = norm_orig.splitlines()
                window_size = len(norm_search.splitlines())

                best_match_idx = -1
                best_ratio = 0.0

                for idx in range(max(1, len(orig_lines) - window_size + 1)):
                    candidate_slice = orig_lines[idx : idx + window_size]
                    candidate_clean = [l.strip() for l in candidate_slice if l.strip()]

                    # Girintisiz tam satır eşleşmesi
                    if search_lines == candidate_clean:
                        best_match_idx = idx
                        best_ratio = 1.0
                        break

                    # difflib SequenceMatcher ile oran kontrolü
                    ratio = difflib.SequenceMatcher(None, "\n".join(candidate_clean), "\n".join(search_lines)).ratio()
                    if ratio > best_ratio and ratio >= 0.85:
                        best_ratio = ratio
                        best_match_idx = idx

                if best_match_idx != -1:
                    matched_slice = "\n".join(orig_lines[best_match_idx : best_match_idx + window_size])
                    new_content = norm_orig.replace(matched_slice, norm_replace, 1)
                else:
                    return (
                        f"Hata: 'search_block' dosya içinde bulunamadı (birebir veya toleranslı eşleşme sağlanamadı). "
                        "Lütfen kodun mevcut haliyle eşleştiğinden emin olun."
                    )

        backup_file_before_write(safe_path)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        diff_lines = len(replace_block.splitlines()) - len(search_block.splitlines())
        return f"Yama başarıyla uygulandı: '{path}' (Değişim: {diff_lines:+d} satır)."
    except Exception as e:
        return f"Yama uygulama hatası: {str(e)}"


@tool(
    name="apply_multi_diff",
    description=(
        "Birden fazla dosyayı tek bir atomik transaction içinde cerrahi olarak değiştirir (Aider stili). "
        "Tüm dosyalar doğrulanmadan hiçbir dosya değiştirilmez. Parametre: 'edits' (List[Dict[str, str]] veya JSON string: [{'path': '...', 'search': '...', 'replace': '...'}])."
    )
)
def apply_multi_diff(edits: Any) -> str:
    """
    Atomik Çoklu Dosya Yaması (Multi-File Atomic Transaction).
    1. Tüm dosyalar ve aranan bloklar doğrulanır (All-or-nothing pre-flight check).
    2. Herhangi birinde hata varsa hiçbir dosya değiştirilmez.
    3. Hepsi geçerliyse eşzamanlı yedek (.bak) alınır ve yazılır.
    """
    import json
    if isinstance(edits, str):
        try:
            edits = json.loads(edits)
        except Exception as e:
            return f"Hata: 'edits' geçerli bir JSON listesi olmalıdır: {e}"

    if not isinstance(edits, list) or len(edits) == 0:
        return "Hata: 'edits' boş olmayan bir liste olmalıdır."

    # 1. Aşama: Pre-flight Verification (Hepsi geçerli mi?)
    plan = []
    for idx, item in enumerate(edits):
        path = item.get("path")
        search_block = item.get("search") or item.get("search_block")
        replace_block = item.get("replace") or item.get("replace_block", "")

        if not path or not search_block:
            return f"Hata [Öğe {idx}]: 'path' ve 'search' alanları zorunludur."

        try:
            safe_path = _validate_safe_path(path)
        except Exception as e:
            return f"Güvenlik İhlali [Öğe {idx}]: {str(e)}"

        if not os.path.exists(safe_path):
            return f"Hata: Dosya bulunamadı: '{path}' (Hiçbir dosya değiştirilmedi)."

        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            original = f.read()

        # Birebir veya newline normalized kontrol
        if search_block in original:
            if original.count(search_block) > 1:
                return f"Hata: '{path}' içinde search_block {original.count(search_block)} kez bulundu. Belirsizliği önlemek için daha fazla satır ekleyin."
            new_content = original.replace(search_block, replace_block, 1)
        else:
            norm_orig = original.replace("\r\n", "\n")
            norm_search = search_block.replace("\r\n", "\n")
            norm_replace = replace_block.replace("\r\n", "\n")
            if norm_search not in norm_orig:
                return f"Hata: '{path}' içinde search_block bulunamadı (Hiçbir dosya değiştirilmedi)."
            if norm_orig.count(norm_search) > 1:
                return f"Hata: '{path}' içinde search_block birden fazla bulundu."
            new_content = norm_orig.replace(norm_search, norm_replace, 1)

        plan.append({
            "path": path,
            "safe_path": safe_path,
            "search": search_block,
            "replace": replace_block,
            "new_content": new_content
        })

    # 2. Aşama: Atomik Yazma (All-or-nothing Execution)
    applied_files = []
    try:
        for item in plan:
            backup_file_before_write(item["safe_path"])
            with open(item["safe_path"], "w", encoding="utf-8") as f:
                f.write(item["new_content"])
            diff_lines = len(item["replace"].splitlines()) - len(item["search"].splitlines())
            applied_files.append(f"{item['path']} ({diff_lines:+d} satır)")

        return f"Atomik çoklu yama başarıyla uygulandı ({len(applied_files)} dosya):\n- " + "\n- ".join(applied_files)
    except Exception as e:
        return f"Kritik yazma hatası: {str(e)}"



@tool(
    name="git_checkpoint",
    description="Kod değişiklikleri öncesinde otomatik kurtarma noktası oluşturur veya başarısız denemede eski duruma geri döner. Parametre: 'action' ('create' veya 'rollback')."
)
def git_checkpoint(action: str = "create") -> str:
    ws = _get_base_workspace()
    action = action.lower().strip()
    try:
        if action == "create":
            res = subprocess.run(["git", "stash", "create"], cwd=ws, capture_output=True, text=True)
            stash_hash = res.stdout.strip()
            if stash_hash:
                subprocess.run(["git", "stash", "store", "-m", "AURA_AGENT_AUTO_CHECKPOINT", stash_hash], cwd=ws)
                return f"Kurtarma noktası oluşturuldu: {stash_hash[:8]}"
            return "Kurtarma noktası oluşturuldu (Değişiklik yoktu)."
        elif action == "rollback":
            subprocess.run(["git", "checkout", "."], cwd=ws, check=True)
            subprocess.run(["git", "clean", "-fd"], cwd=ws, check=True)
            return "Çalışma alanı son temiz Git durumuna geri döndürüldü (Rollback başarılı)."
        else:
            return "Desteklenen eylemler: 'create', 'rollback'."
    except Exception as e:
        return f"Git checkpoint hatası: {str(e)}"


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
            cwd=_get_base_workspace(),
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
            cwd=_get_base_workspace(),
            capture_output=True,
            text=True,
            timeout=15
        )
        out = res.stdout.strip()
        return out if out else "Görüntülenecek Git farkı yok."
    except Exception as e:
        return f"Git diff hatası: {str(e)}"


def _execute_sandboxed_command(command: str, cwd: str) -> subprocess.CompletedProcess:
    """
    Çoklu Platform Donanım ve İşletim Sistemi Soyutlama Katmanı (HAL) üzerinden
    Linux (Bubblewrap), macOS (Seatbelt) veya izole subshell ortamında komutu çalıştırır.
    """
    from api_server.app.core.platform_hal import platform_hal
    return platform_hal.execute_sandboxed_command(command, cwd=cwd, timeout=60)


@tool(
    name="run_terminal_command",
    description="Proje çalışma alanında derleme, test ve kontrol komutları çalıştırır (Örn: 'cargo check', 'pytest')."
)
def run_terminal_command(command: str) -> str:
    # Gelişmiş Etik ve Güvenlik Analizi
    is_safe, msg = assess_command_risk(command)
    if not is_safe:
        return f"Güvenlik İhlali Engellendi: {msg}"

    try:
        res = _execute_sandboxed_command(command, cwd=_get_base_workspace())
        output = res.stdout + ("\nHata Çıktısı (stderr):\n" + res.stderr if res.stderr else "")
        return output.strip() if output.strip() else f"Komut başarıyla çalıştı (Çıkış kodu: {res.returncode})."
    except subprocess.TimeoutExpired:
        return "Komut zaman aşımına uğradı (60s)."
    except Exception as e:
        return f"Komut çalıştırma hatası: {str(e)}"
