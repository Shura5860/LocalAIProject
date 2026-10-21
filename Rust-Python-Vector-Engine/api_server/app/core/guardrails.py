import os
import re
import shutil
from typing import Tuple

CONSTITUTION_PROMPT = """
[ETİK VE GÜVENLİK ANAYASASI]
1. ZARARSIZLIK: Kullanıcı istese dahi işletim sistemine, donanıma veya dosyalara zarar verebilecek yıkıcı eylemleri ASLA gerçekleştirme.
2. MAHREMİYET & SIFIR SIZINTI: Kullanıcının yerel dokümanları, kişisel bilgileri veya özel anahtarları asla üçüncü taraflara veya internet aramalarına sızdırılamaz.
3. DÜRÜSTLÜK & SIFIR HALÜSİNASYON: Bilmediğin veya bağlamda yer almayan konularda kesinlikle uydurma cevap verme. Bilmediğini açıkça ve dürüstçe belirt.
4. ŞEFFAFLIK: Ulaştığın sonuçları hangi aracı veya hangi belgeyi kullanarak elde ettiğini her zaman açıkla.
[ANAYASA SONU]
"""

FORBIDDEN_COMMAND_PATTERNS = [
    r"\brm\s+-[rRfF]+\s+[/~]",              # rm -rf / veya rm -rf ~
    r"\bmkfs\b",                           # disk formatlama
    r"\bdd\s+if=",                         # ham disk yazma
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;", # fork bomb
    r"\bshutdown\b",                       # sistemi kapatma
    r"\breboot\b",                         # sistemi yeniden başlatma
    r"\bchmod\s+-[rRfF]*\s+777\s+/",       # kök izinlerini bozma
    r">\s*/dev/sd[a-z]",                   # diske doğrudan yazma
]

SENSITIVE_PATTERNS = [
    r"(?i)(api[_-]?key|secret|token|password|passwd|bearer)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?",
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", # e-posta
    r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",             # kredi kartı kalıbı
]

def sanitize_web_query(query: str) -> str:
    """İnternete gönderilen sorgulardan hassas anahtar, şifre ve kişisel verileri temizler."""
    sanitized = query
    for pattern in SENSITIVE_PATTERNS:
        sanitized = re.sub(pattern, "[HASSAS_VERİ_MUNDELENDİ]", sanitized)
    return sanitized

def assess_command_risk(command: str) -> Tuple[bool, str]:
    """
    Komutun tehlike seviyesini analiz eder. (is_safe, message) döner.
    Base64, Hex ve gizlenmiş (obfuscated) komutları çözerek inceler.
    """
    if not command:
        return True, "Boş komut."

    # 1. Ham komut denetimi
    for pattern in FORBIDDEN_COMMAND_PATTERNS:
        if re.search(pattern, command):
            return False, f"Güvenlik Kalkanı: Komutta yasaklı/yıkıcı kalıp tespit edildi: '{pattern}'"

    # 2. Base64 Obfuscation Denetimi (Örn: echo "..." | base64 -d | sh)
    if "base64" in command.lower():
        import base64
        # Tırnak içindeki veya pipe öncesindeki potansiyel base64 dizgilerini ara
        b64_matches = re.findall(r"['\"]([A-Za-z0-9+/=]{8,})['\"]", command)
        for b64_str in b64_matches:
            try:
                decoded = base64.b64decode(b64_str).decode("utf-8", errors="ignore")
                for pattern in FORBIDDEN_COMMAND_PATTERNS:
                    if re.search(pattern, decoded):
                        return False, f"Güvenlik Kalkanı: Base64 ile gizlenmiş zararlı komut tespit edildi: '{decoded.strip()}'"
            except Exception:
                pass

    # 3. Tehlikeli Ağ Enjeksiyonları (Remote execution via curl/wget pipe to shell)
    pipe_shell_pattern = r"(curl|wget)\s+[^\n|]+\|\s*(ba|z|k|c)?sh"
    if re.search(pipe_shell_pattern, command, re.IGNORECASE):
        return False, "Güvenlik Kalkanı: Doğrudan internetten kabuğa aktarılan komut (curl | sh) engellendi!"

    return True, "Komut güvenli."

def backup_file_before_write(file_path: str):
    """Mevcut bir dosya güncellenmeden önce otomatik .bak yedeği alır."""
    if os.path.exists(file_path):
        backup_path = file_path + ".bak"
        try:
            shutil.copy2(file_path, backup_path)
        except Exception:
            pass

# Human-In-The-Loop (HITL) İnsan Onay Kuralı
# Bu araçlar sistemi veya dosyaları kalıcı olarak değiştirdiği için onay gerektirir
CRITICAL_TOOLS = ["write_file", "run_terminal_command"]

AUDIT_LOG_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../hitl_audit.log")
)

def is_approval_required(tool_name: str, args: dict = None) -> bool:
    """Belirtilen aracın insan onayı gerektirip gerektirmediğini denetler."""
    return tool_name in CRITICAL_TOOLS

def record_audit_log(tool_name: str, args: dict, approved: bool, reason: str = ""):
    """Kritik eylem onay/red kararlarını zaman damgasıyla denetim günlüğüne yazar."""
    import datetime
    import json
    timestamp = datetime.datetime.now().isoformat()
    status = "APPROVED" if approved else "REJECTED"
    log_entry = {
        "timestamp": timestamp,
        "status": status,
        "tool": tool_name,
        "args": args or {},
        "reason": reason
    }
    try:
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

