import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.services.memory_service import memory_service

def test_memory_system():
    print("=" * 70)
    print("🧠 FAZ 4 TESTİ: Çok Katmanlı Kişiselleştirilmiş Hafıza (Profile & Episodic)")
    print("=" * 70)

    # 1. Profil Testi
    print("\n[1] Kullanıcı Profili Okuma & Güncelleme:")
    profile = memory_service.get_profile()
    print(f"  • Mevcut Profil: {profile}")
    assert profile.get("name") == "Shura"

    updated = memory_service.update_profile({"favorite_editor": "Neovim & Antigravity IDE"})
    print(f"  • Güncellenen Profil: {updated}")
    assert updated.get("favorite_editor") == "Neovim & Antigravity IDE"

    # 2. Epizodik Hafıza (Remember Fact)
    print("\n[2] Önemli Bilgiyi Kalıcı Hafızaya Kaydetme:")
    fact1 = "Ben kahvemi daima sütsüz ve şekersiz içerim."
    fact2 = "Projelerimde asenkron mimari ve SIMD donanım optimizasyonu kullanırım."
    
    res1 = memory_service.remember_fact(fact1, topic="habits")
    res2 = memory_service.remember_fact(fact2, topic="tech")
    print(f"  • Kaydedildi (1): {res1}")
    print(f"  • Kaydedildi (2): {res2}")
    assert res1["status"] == "success"

    # 3. Geri Çağırma (Recall Facts)
    print("\n[3] Hafızadan İlgili Bilgiyi Geri Çağırma:")
    recalled = memory_service.recall_facts("Kahve nasıl hazırlanmalı?", top_k=1)
    print(f"  • 'Kahve nasıl hazırlanmalı?' sorgusu sonucu geri çağrılan:\n    {recalled}")
    assert len(recalled) >= 1
    assert "sütsüz" in recalled[0]["fact"]

    # 4. Kişiselleştirilmiş Prompt Üretimi
    print("\n[4] Sisteme Enjekte Edilen Kişiselleştirilmiş Prompt:")
    prompt_ctx = memory_service.build_memory_prompt("Bana kahve öner")
    print(prompt_ctx)
    assert "Shura" in prompt_ctx
    assert "sütsüz" in prompt_ctx

    print("=" * 70)
    print("✅ FAZ 4 KİŞİSELLEŞTİRİLMİŞ HAFIZA TESTİ BAŞARIYLA TAMAMLANDI!")
    print("=" * 70)

if __name__ == "__main__":
    test_memory_system()
