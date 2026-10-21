import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.tools.registry import tool_registry
from api_server.app.services.agent_service import agent_service
from api_server.app.services.react_agent_service import react_agent_service

def test_devops_suite():
    print("=" * 70)
    print("🛠️ FAZ 5 TESTİ: Yerel DevOps & Kod Geliştirme Asistanı")
    print("=" * 70)

    # 1. Dosya Araçları Testi
    print("\n[1] Dosya Araçlarının Test Edilmesi:")
    list_tool = tool_registry.get_tool("list_files")
    files = list_tool.execute(directory=".")
    print(f"  • Proje Kök Dosyaları: {files}")
    assert any("Rust-LLM-Engine" in f for f in files)

    read_tool = tool_registry.get_tool("read_file")
    cargo_content = read_tool.execute(path="Rust-LLM-Engine/Cargo.toml")
    print(f"  • Cargo.toml Okundu ({len(cargo_content)} karakter):\n    {cargo_content[:80]}...")
    assert "rust-llm-engine" in cargo_content

    # Güvenlik Sandbox Testi (Jail Escape Engeli)
    print("\n[2] Güvenlik & Sandbox Koruması Testi:")
    sec_res = read_tool.execute(path="/etc/passwd")
    print(f"  • Güvenlik denetimi sonucu: {sec_res}")
    assert "Güvenlik İhlali" in sec_res

    # 2. Git Araçları Testi
    print("\n[3] Git Sürüm Kontrolü Araçları:")
    git_status_tool = tool_registry.get_tool("git_status")
    status_out = git_status_tool.execute()
    print(f"  • Git Status Çıktısı:\n    {status_out[:120]}...")
    assert isinstance(status_out, str)

    # 3. Terminal & Derleyici Komutu Testi
    print("\n[4] Terminal / Derleyici Komut Testi:")
    term_tool = tool_registry.get_tool("run_terminal_command")
    term_res = term_tool.execute(command="cargo check --manifest-path Rust-LLM-Engine/Cargo.toml")
    print(f"  • 'cargo check' Derleyici Sonucu:\n    {term_res}")
    assert "Finished" in term_res or "Checking" in term_res

    # 4. Ajan & ReAct ile DevOps Görev Yürütme Testi
    print("\n[5] ReAct Ajanının DevOps Görevi Yürütmesi:")
    q = "Projedeki Rust-LLM-Engine/Cargo.toml dosyasını oku"
    print(f"  ❓ Soru: \"{q}\"")
    res = react_agent_service.run(user_query=q, max_steps=2)
    print(f"  📊 Toplam Adım: {res['total_steps']}")
    print(f"  🛠️ Tetiklenen Eylem: {res['trace'][0]['action']} -> Parametre: {res['trace'][0]['action_input']}")
    assert res['trace'][0]['action'] == "read_file"

    print("\n" + "=" * 70)
    print("✅ FAZ 5 DEVOPS & KOD GELİŞTİRME ASİSTANI TESTİ BAŞARIYLA TAMAMLANDI!")
    print("=" * 70)

if __name__ == "__main__":
    test_devops_suite()
