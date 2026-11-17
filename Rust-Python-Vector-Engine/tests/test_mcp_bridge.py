import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.tools.mcp_bridge import mcp_bridge, MCPToolWrapper
from api_server.app.tools.registry import tool_registry


class TestMCPBridge(unittest.TestCase):
    def test_mcp_tool_wrapping_and_schema(self):
        sample_mcp_tool = {
            "name": "query_db",
            "description": "SQL veritabanında sorgu çalıştırır",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Çalıştırılacak SQL sorgusu"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maksimum satır sayısı",
                        "default": 10
                    }
                },
                "required": ["sql"]
            }
        }

        mock_invoker_called = {}
        def mock_invoker(server_name, tool_name, args):
            mock_invoker_called["server"] = server_name
            mock_invoker_called["tool"] = tool_name
            mock_invoker_called["args"] = args
            return "1 rows returned"

        tool = MCPToolWrapper("sqlite", sample_mcp_tool, mock_invoker)
        self.assertEqual(tool.name, "mcp_sqlite_query_db")
        self.assertIn("SQL veritabanında sorgu çalıştırır", tool.description)

        schema = tool.to_schema()
        self.assertEqual(schema["name"], "mcp_sqlite_query_db")
        self.assertIn("sql", schema["parameters"])
        self.assertTrue(schema["parameters"]["sql"]["required"])

        # Execute
        res = tool.execute(sql="SELECT * FROM users", limit=5)
        self.assertEqual(res, "1 rows returned")
        self.assertEqual(mock_invoker_called["server"], "sqlite")
        self.assertEqual(mock_invoker_called["tool"], "query_db")
        self.assertEqual(mock_invoker_called["args"]["sql"], "SELECT * FROM users")

    def test_mcp_bridge_registry_integration(self):
        mock_tools_data = [
            {
                "name": "list_containers",
                "description": "Docker konteynerlerini listeler",
                "inputSchema": {
                    "type": "object",
                    "properties": {"all": {"type": "boolean", "default": False}}
                }
            }
        ]

        tools = mcp_bridge.load_tools_from_server("docker", mock_tools=mock_tools_data)
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "mcp_docker_list_containers")

        # Register in tool registry
        tool_registry.register(tools[0])
        self.assertIsNotNone(tool_registry.get_tool("mcp_docker_list_containers"))


if __name__ == "__main__":
    unittest.main()

