from typing import Dict, List, Optional
from api_server.app.tools.base import Tool
from api_server.app.tools.builtin import calculator, system_info, web_search, python_interpreter
from api_server.app.tools.devops import (
    read_file,
    write_file,
    list_files,
    git_status,
    git_diff,
    run_terminal_command
)
from api_server.app.tools.stealth_web import read_web_page

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self.register_default_tools()

    def register(self, tool_instance: Tool):
        self._tools[tool_instance.name] = tool_instance

    def register_default_tools(self):
        self.register(calculator)
        self.register(system_info)
        self.register(web_search)
        self.register(python_interpreter)
        self.register(read_file)
        self.register(write_file)
        self.register(list_files)
        self.register(git_status)
        self.register(git_diff)
        self.register(run_terminal_command)
        self.register(read_web_page)

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_all_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def get_tools_prompt_description(self) -> str:
        lines = []
        for t in self._tools.values():
            schema = t.to_schema()
            lines.append(f"- {schema['name']}: {schema['description']} (Parametreler: {schema['parameters']})")
        return "\n".join(lines)

tool_registry = ToolRegistry()
