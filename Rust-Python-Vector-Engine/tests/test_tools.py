import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.tools.registry import tool_registry
from api_server.app.services.agent_service import agent_service


class TestTools(unittest.TestCase):
    def test_registered_tools_schema(self):
        tools = tool_registry.get_all_tools()
        self.assertGreaterEqual(len(tools), 5)
        for t in tools:
            schema = t.to_schema()
            self.assertIn("name", schema)
            self.assertIn("description", schema)
            self.assertIn("parameters", schema)

    def test_calculator(self):
        calc_tool = tool_registry.get_tool("calculator")
        self.assertIsNotNone(calc_tool)
        res = calc_tool.execute(expression="250 * 4 + 15")
        self.assertEqual(res, "1015")

    def test_system_info(self):
        sys_tool = tool_registry.get_tool("system_info")
        self.assertIsNotNone(sys_tool)
        res = sys_tool.execute(metric="cpu")
        self.assertIn("cpu_percent", res)

    def test_python_interpreter(self):
        py_tool = tool_registry.get_tool("python_interpreter")
        self.assertIsNotNone(py_tool)
        res = py_tool.execute(code="a = [x**2 for x in range(5)]; print('Kareler:', a)")
        self.assertIn("Kareler:", res)

    def test_corten_profile_modular_lifecycle(self):
        # 1. Başlangıçta Corten araçları çekirdeğe zorunlu yüklenmemeli
        initial_tools = {t.name for t in tool_registry.get_all_tools()}
        
        # 2. Corten profilini dinamik olarak yükle
        loaded_count = tool_registry.load_corten_profile()
        self.assertGreater(loaded_count, 0)
        
        corten_vol = tool_registry.get_tool("corten_set_volume")
        self.assertIsNotNone(corten_vol)
        
        # 3. Güvenlik: corten_system_power onay gerektirmeli
        from api_server.app.core.guardrails import is_approval_required
        self.assertTrue(is_approval_required("corten_system_power"))

        # 4. Profili güvenle kaldır
        tool_registry.unload_corten_profile()
        self.assertIsNone(tool_registry.get_tool("corten_set_volume"))


if __name__ == "__main__":
    unittest.main()
