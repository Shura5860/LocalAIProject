import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.tools.registry import tool_registry
from api_server.app.core.guardrails import is_approval_required


class TestCortenIntegration(unittest.TestCase):
    def setUp(self):
        # Clean state: ensure corten is not loaded initially
        tool_registry.unload_profile("corten")

    def tearDown(self):
        tool_registry.unload_profile("corten")

    def test_corten_profile_lifecycle(self):
        self.assertIsNone(tool_registry.get_tool("corten_window_control"))
        self.assertIsNone(tool_registry.get_tool("corten_system_power"))

        # Load profile
        success = tool_registry.load_profile("corten")
        self.assertTrue(success)

        win_tool = tool_registry.get_tool("corten_window_action")
        self.assertIsNotNone(win_tool)

        power_tool = tool_registry.get_tool("corten_system_power")
        self.assertIsNotNone(power_tool)

        # Unload profile
        unloaded = tool_registry.unload_profile("corten")
        self.assertTrue(unloaded)
        self.assertIsNone(tool_registry.get_tool("corten_window_action"))

    def test_corten_safety_guardrails(self):
        # corten_system_power MUST require Human-In-The-Loop approval
        self.assertTrue(is_approval_required("corten_system_power"))
        # Read-only or normal notifications should not block with HITL
        self.assertFalse(is_approval_required("corten_notify"))

    def test_corten_tools_schema_validity(self):
        tool_registry.load_profile("corten")
        for tool_name in ["corten_window_action", "corten_switch_workspace", "corten_notify", "corten_system_power"]:
            t = tool_registry.get_tool(tool_name)
            self.assertIsNotNone(t, f"Tool {tool_name} not found")
            schema = t.to_schema()
            self.assertEqual(schema["name"], tool_name)
            self.assertIn("description", schema)
            self.assertIn("parameters", schema)


if __name__ == "__main__":
    unittest.main()
