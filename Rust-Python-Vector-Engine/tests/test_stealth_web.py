import unittest
import sys
import os

# Add project root and api_server to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.tools.registry import tool_registry
from api_server.app.tools.stealth_web import get_stealth_headers
from api_server.app.services.agent_service import agent_service
from api_server.app.services.react_agent_service import react_agent_service

class TestStealthWebScraper(unittest.TestCase):
    def test_registry_contains_read_web_page(self):
        tool = tool_registry.get_tool("read_web_page")
        self.assertIsNotNone(tool, "read_web_page tool should be in tool_registry")
        self.assertEqual(tool.name, "read_web_page")

    def test_stealth_headers_generation(self):
        headers = get_stealth_headers()
        self.assertIn("User-Agent", headers)
        self.assertIn("Accept-Language", headers)
        self.assertIn("Upgrade-Insecure-Requests", headers)
        self.assertTrue(headers["User-Agent"].startswith("Mozilla/5.0"))

    def test_execute_read_web_page_direct(self):
        # Test on a reliable public test URL
        tool = tool_registry.get_tool("read_web_page")
        res = tool.execute(url="https://httpbin.org/html", max_chars=1000)
        self.assertIsInstance(res, str)
        self.assertIn("Herman Melville - Moby-Dick", res)

    def test_agent_service_url_intent(self):
        res = agent_service.run("Lütfen https://httpbin.org/html linkindeki sayfayı oku")
        self.assertIsNotNone(res["tool_used"])
        self.assertEqual(res["tool_used"]["name"], "read_web_page")
        self.assertEqual(res["tool_used"]["args"]["url"], "https://httpbin.org/html")

    def test_react_agent_url_intent(self):
        res = react_agent_service.run("https://httpbin.org/html adresindeki içeriği bot korumasını geçerek analiz et", max_steps=2)
        self.assertGreater(len(res["trace"]), 0)
        self.assertEqual(res["trace"][0]["action"], "read_web_page")

if __name__ == "__main__":
    unittest.main()
