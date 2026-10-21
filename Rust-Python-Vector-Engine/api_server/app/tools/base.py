import inspect
from typing import Callable, Any, Dict, get_type_hints

class Tool:
    def __init__(self, fn: Callable, name: str, description: str):
        self.fn = fn
        self.name = name
        self.description = description
        self.signature = inspect.signature(fn)
        self.parameters = self._extract_parameters()

    def _extract_parameters(self) -> Dict[str, Any]:
        params = {}
        type_hints = get_type_hints(self.fn)
        for name, param in self.signature.parameters.items():
            param_type = type_hints.get(name, str).__name__
            default = param.default if param.default != inspect.Parameter.empty else None
            params[name] = {
                "type": param_type,
                "required": param.default == inspect.Parameter.empty,
                "default": default
            }
        return params

    def to_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

    def execute(self, **kwargs) -> Any:
        return self.fn(**kwargs)

def tool(name: str, description: str):
    def decorator(fn: Callable):
        return Tool(fn=fn, name=name, description=description)
    return decorator
