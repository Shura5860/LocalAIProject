"""
Anthropic Model Context Protocol (MCP) Client Bridge for AURA-CORE.
Allows AURA to connect to external MCP servers (stdio JSON-RPC 2.0),
discover their tools dynamically, and register them into ToolRegistry.
"""

import os
import json
import logging
import subprocess
from typing import Dict, Any, List, Optional
from api_server.app.tools.base import Tool

logger = logging.getLogger(__name__)


class MCPToolWrapper(Tool):
    """Wraps an external MCP tool definition into AURA's native Tool class."""
    def __init__(self, server_name: str, tool_def: Dict[str, Any], invoker_fn):
        self.server_name = server_name
        self.mcp_name = tool_def.get("name", "unknown")
        name = f"mcp_{server_name}_{self.mcp_name}"
        description = f"[{server_name.upper()} MCP] {tool_def.get('description', '')}"

        # Build parameters schema from inputSchema
        input_schema = tool_def.get("inputSchema", {})
        properties = input_schema.get("properties", {})
        required = set(input_schema.get("required", []))

        self.parameters = {}
        for p_name, p_info in properties.items():
            self.parameters[p_name] = {
                "type": p_info.get("type", "string"),
                "description": p_info.get("description", ""),
                "required": p_name in required,
                "default": p_info.get("default", None)
            }

        self.name = name
        self.description = description
        self.invoker_fn = invoker_fn

    def to_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

    def execute(self, **kwargs) -> Any:
        return self.invoker_fn(self.server_name, self.mcp_name, kwargs)


class MCPBridge:
    """
    Manages connections and lifecycle for external Model Context Protocol servers.
    """
    def __init__(self):
        self._servers: Dict[str, Dict[str, Any]] = {}
        self._registered_tools: Dict[str, Tool] = {}

    def register_server_config(self, name: str, command: str, args: List[str], env: Optional[Dict[str, str]] = None):
        """Registers an MCP server definition in config."""
        self._servers[name] = {
            "command": command,
            "args": args,
            "env": env or {}
        }

    def call_mcp_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Executes a tool on an external MCP server via stdio JSON-RPC."""
        server = self._servers.get(server_name)
        if not server:
            return f"Hata: '{server_name}' adında bir MCP sunucusu kayıtlı değil."

        cmd = [server["command"]] + server["args"]

        request_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        proc_env = {**os.environ, **(server.get("env") or {})}
        try:
            proc = subprocess.run(
                cmd,
                input=json.dumps(request_payload) + "\n",
                capture_output=True,
                text=True,
                env=proc_env,
                timeout=10
            )
            if proc.returncode != 0 and not proc.stdout:
                return f"MCP Sunucu Hatası ({server_name}): {proc.stderr}"

            for line in proc.stdout.splitlines():
                try:
                    resp = json.loads(line)
                    if "result" in resp:
                        content = resp["result"].get("content", [])
                        texts = [c.get("text", "") for c in content if isinstance(c, dict)]
                        return "\n".join(texts) or str(resp["result"])
                    elif "error" in resp:
                        return f"MCP Hatası: {resp['error']}"
                except Exception:
                    continue
            return proc.stdout or "İşlem tamamlandı."
        except subprocess.TimeoutExpired:
            return f"Zaman aşımı: MCP sunucusu ({server_name}) 10 saniye içinde yanıt vermedi."
        except Exception as e:
            return f"MCP çağrı hatası: {str(e)}"

    def load_tools_from_server(self, server_name: str, mock_tools: Optional[List[Dict[str, Any]]] = None) -> List[Tool]:
        """Loads tool definitions from an MCP server and returns AURA Tool instances."""
        tools = []
        if mock_tools:
            for t in mock_tools:
                wrapped = MCPToolWrapper(server_name, t, self.call_mcp_tool)
                tools.append(wrapped)
                self._registered_tools[wrapped.name] = wrapped
            return tools

        server = self._servers.get(server_name)
        if not server:
            return []

        # JSON-RPC tools/list
        import os
        cmd = [server["command"]] + server["args"]
        proc_env = {**os.environ, **(server.get("env") or {})}
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        try:
            proc = subprocess.run(cmd, input=json.dumps(req) + "\n", capture_output=True, text=True, env=proc_env, timeout=5)
            for line in proc.stdout.splitlines():
                try:
                    resp = json.loads(line)
                    if "result" in resp and "tools" in resp["result"]:
                        for t_def in resp["result"]["tools"]:
                            wrapped = MCPToolWrapper(server_name, t_def, self.call_mcp_tool)
                            tools.append(wrapped)
                            self._registered_tools[wrapped.name] = wrapped
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"MCP sunucusundan araçlar yüklenemedi ({server_name}): {e}")

        return tools


mcp_bridge = MCPBridge()

