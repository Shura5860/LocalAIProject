import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.tools.registry import tool_registry
from api_server.app.services.agent_service import agent_service

def test_tools():
    print("=" * 70)
    print("🛠️ FAZ 2 TESTİ: Tool Calling & Autonomous Agent Execution")
    print("=" * 70)

    # 1. Kayıtlı Araçların Doğrulanması
    print("\n[1] Kayıtlı Araçların Şemaları:")
    for t in tool_registry.get_all_tools():
        schema = t.to_schema()
        print(f"  • Araç: {schema['name']} -> {schema['description'][:60]}...")

    # 2. Doğrudan Araç Yürütme Testleri
    print("\n[2] Doğrudan Araç Fonksiyonlarının Yürütülmesi:")
    
    calc_tool = tool_registry.get_tool("calculator")
    calc_res = calc_tool.execute(expression="250 * 4 + 15")
    print(f"  • Calculator ('250 * 4 + 15'): {calc_res}")
    assert calc_res == "1015"

    sys_tool = tool_registry.get_tool("system_info")
    sys_res = sys_tool.execute(metric="cpu")
    print(f"  • System Info ('cpu'): {sys_res}")
    assert "cpu_percent" in sys_res

    py_tool = tool_registry.get_tool("python_interpreter")
    py_res = py_tool.execute(code="a = [x**2 for x in range(5)]; print('Kareler:', a)")
    print(f"  • Python Interpreter: {py_res}")
    assert "Kareler:" in py_res

    # 3. Ajan Döngüsü Testleri (Agent Loop)
    print("\n[3] Ajanın Soru Üzerinden İlgili Aracı Tetiklemesi:")
    
    agent_queries = [
        "125 * 8 kaçtır hesaplar mısın?",
        "Bilgisayarın RAM ve CPU sistem durumu nedir?",
        "Kadıköy hava durumu nasıl arar mısın?"
    ]

    for q in agent_queries:
        print(f"\n❓ Ajan Sorusu: \"{q}\"")
        res = agent_service.run(user_query=q)
        print(f"   🛠️ Tetiklenen Araç: {res['tool_used']}")
        print(f"   📊 Araç Çıktısı: {res['tool_result']}")
        print(f"   🤖 Nihai Yanıt:\n   {res['answer']}")

    print("\n" + "=" * 70)
    print("✅ FAZ 2 TOOL CALLING ENTEGRASYON TESTİ BAŞARIYLA GEÇTİ!")
    print("=" * 70)

if __name__ == "__main__":
    test_tools()
