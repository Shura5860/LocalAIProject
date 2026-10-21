import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.core.guardrails import (
    sanitize_web_query,
    assess_command_risk,
    backup_file_before_write,
    CONSTITUTION_PROMPT
)
from api_server.app.tools.devops import write_file, run_terminal_command
from api_server.app.tools.builtin import web_search

def test_ethics_and_guardrails():
    print("=" * 70)
    print("🛡️ FAZ 6 TESTİ: Yapay Zeka Etik Anayasası, Güvenlik & Gizlilik Kalkanı")
    print("=" * 70)

    # 1. Anayasa Metni Kontrolü
    print("\n[1] Etik Anayasa Prompt Kontrolü:")
    print(CONSTITUTION_PROMPT.strip())
    assert "ZARARSIZLIK" in CONSTITUTION_PROMPT
    assert "MAHREMİYET" in CONSTITUTION_PROMPT
    assert "DÜRÜSTLÜK" in CONSTITUTION_PROMPT

    # 2. Web Araması Gizlilik Maskeleme Testi (Privacy Guard)
    print("\n[2] Dış Web Aramasında Hassas Veri Sızıntısı Engeli:")
    sensitive_query = "Hava durumu İstanbul ve api_key='sk-12345abcdef67890xyz' password='super_secret_123'"
    clean_query = sanitize_web_query(sensitive_query)
    print(f"  • Orijinal Sorgu: {sensitive_query}")
    print(f"  • Maskelenmiş Sorgu: {clean_query}")
    assert "sk-12345" not in clean_query
    assert "super_secret" not in clean_query
    assert "[HASSAS_VERİ_MUNDELENDİ]" in clean_query

    # 3. Yıkıcı / Tehlikeli Komut Engelleme Testi (Command Guard)
    print("\n[3] Yıkıcı Terminal Komutları Risk Analizi:")
    danger_cmds = [
        "rm -rf /",
        "rm -rf ~",
        "mkfs.ext4 /dev/sda1",
        ":(){ :|:& };:",
        "shutdown -h now"
    ]
    for cmd in danger_cmds:
        is_safe, msg = assess_command_risk(cmd)
        print(f"  • Komut: '{cmd}' -> Güvenli mi? {is_safe} ({msg})")
        assert not is_safe

        # run_terminal_command üzerinden de test et
        block_res = run_terminal_command.execute(command=cmd)
        assert "Güvenlik İhlali Engellendi" in block_res

    # Güvenli komuta izin verildiği doğrulanır
    is_safe, _ = assess_command_risk("cargo check")
    assert is_safe

    # 4. Otomatik Dosya Yedekleme Testi (Auto-Backup Guard)
    print("\n[4] Dosya Üzerine Yazarken Otomatik Yedekleme:")
    test_file = "test_guardrail_file.txt"
    test_path = os.path.join(os.path.dirname(__file__), test_file)

    # İlk dosya oluşturulur
    with open(test_path, "w", encoding="utf-8") as f:
        f.write("Versiyon 1 Orijinal İçerik")

    # Üzerine yazma çağrılır
    rel_path = f"Rust-Python-Vector-Engine/tests/{test_file}"
    res = write_file.execute(path=rel_path, content="Versiyon 2 Güncellenmiş İçerik")
    print(f"  • write_file sonucu: {res}")
    
    backup_path = test_path + ".bak"
    assert os.path.exists(backup_path), "Yedek (.bak) dosyası oluşturulmadı!"
    with open(backup_path, "r", encoding="utf-8") as f:
        old_content = f.read()
    print(f"  • Otomatik .bak dosyasındaki korunan orijinal içerik: '{old_content}'")
    assert old_content == "Versiyon 1 Orijinal İçerik"

    # Temizlik
    if os.path.exists(test_path):
        os.remove(test_path)
    if os.path.exists(backup_path):
        os.remove(backup_path)

    print("\n" + "=" * 70)
    print("✅ FAZ 6 ETİK VE GÜVENLİK KALKANI TESTİ BAŞARIYLA TAMAMLANDI!")
    print("=" * 70)

if __name__ == "__main__":
    test_ethics_and_guardrails()
