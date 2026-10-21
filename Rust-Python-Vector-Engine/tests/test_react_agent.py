import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.services.react_agent_service import react_agent_service

def test_react_agent():
    print("=" * 70)
    print("🧠 FAZ 3 TESTİ: ReAct (Reasoning + Acting) Çok Adımlı Ajan Testi")
    print("=" * 70)

    # Test 1: Çok Adımlı / Zincirleme İstek
    q1 = "Sistemdeki disk alanını oku ve bunu 1024 ile çarp."
    print(f"\n❓ Soru 1: \"{q1}\"")
    res1 = react_agent_service.run(user_query=q1, max_steps=5)
    print(f"📊 Toplam Adım Sayısı: {res1['total_steps']}")
    print("🔍 Adım İzi (Trace):")
    for step in res1["trace"]:
        print(f"  • [Adım {step['step_number']}] Thought: {step['thought']}")
        if step.get("action"):
            print(f"    -> Eylem: {step['action']}({step['action_input']})")
            print(f"    -> Gözlem: {step['observation']}")
    print(f"🤖 Nihai Cevap:\n{res1['final_answer']}")
    assert len(res1["trace"]) >= 1

    # Test 2: Doğrudan Hesaplama
    q2 = "450 * 20 kaçtır?"
    print(f"\n❓ Soru 2: \"{q2}\"")
    res2 = react_agent_service.run(user_query=q2, max_steps=3)
    print(f"📊 Toplam Adım Sayısı: {res2['total_steps']}")
    print(f"🤖 Nihai Cevap:\n{res2['final_answer']}")
    assert len(res2["trace"]) >= 1

    print("\n" + "=" * 70)
    print("✅ FAZ 3 ReAct AJAN TESTİ BAŞARIYLA TAMAMLANDI!")
    print("=" * 70)

if __name__ == "__main__":
    test_react_agent()
