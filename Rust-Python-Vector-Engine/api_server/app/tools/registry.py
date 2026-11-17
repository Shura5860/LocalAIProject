import os
import logging
from typing import Dict, List, Optional
from api_server.app.tools.base import Tool
from api_server.app.tools.builtin import calculator, system_info, web_search, python_interpreter
from api_server.app.tools.devops import (
    read_file,
    write_file,
    apply_diff,
    apply_multi_diff,
    git_checkpoint,
    list_files,
    git_status,
    git_diff,
    run_terminal_command
)
from api_server.app.tools.stealth_web import read_web_page

logger = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self.register_core_tools()
        self._auto_load_profiles()

    def register(self, tool_instance: Tool):
        """Registers a single tool instance."""
        self._tools[tool_instance.name] = tool_instance

    def unregister(self, tool_name: str):
        """Unregisters a tool by name."""
        self._tools.pop(tool_name, None)

    def register_core_tools(self):
        """
        Registers platform-agnostic, standalone core tools.
        These are always available regardless of host OS or desktop environment.
        """
        # Built-in Core Tools
        self.register(calculator)
        self.register(system_info)
        self.register(web_search)
        self.register(python_interpreter)

        # DevOps & File Tools
        self.register(read_file)
        self.register(write_file)
        self.register(apply_diff)
        self.register(apply_multi_diff)
        self.register(git_checkpoint)
        self.register(list_files)
        self.register(git_status)
        self.register(git_diff)
        self.register(run_terminal_command)
        self.register(read_web_page)

    def register_default_tools(self):
        """Legacy compatibility method."""
        self.register_core_tools()

    def load_corten_profile(self) -> int:
        """
        Loads the Corten Desktop (Wayland) extension profile tools.
        Returns the count of tools loaded.
        """
        try:
            from api_server.app.tools.corten_desktop import CORTEN_TOOLS
            for t in CORTEN_TOOLS:
                self.register(t)
            logger.info("Loaded Corten Desktop profile with %d tools.", len(CORTEN_TOOLS))
            return len(CORTEN_TOOLS)
        except Exception as e:
            logger.warning("Failed to load Corten Desktop profile: %s", str(e))
            return 0

    def unload_corten_profile(self):
        """Unloads Corten Desktop profile tools."""
        try:
            from api_server.app.tools.corten_desktop import CORTEN_TOOLS
            for t in CORTEN_TOOLS:
                self.unregister(t.name)
        except Exception:
            pass

    def load_profile(self, profile_name: str) -> bool:
        """Loads a named tool profile."""
        profile = profile_name.strip().lower()
        if profile == "corten":
            return self.load_corten_profile() > 0
        logger.warning("Unknown tool profile: %s", profile_name)
        return False

    def unload_profile(self, profile_name: str) -> bool:
        """Unloads a named tool profile."""
        profile = profile_name.strip().lower()
        if profile == "corten":
            self.unload_corten_profile()
            return True
        return False

    def _auto_load_profiles(self):
        """Automatically loads profiles based on environment variables."""
        profile = os.environ.get("AURA_TOOL_PROFILE", "").strip().lower()
        corten_flag = os.environ.get("CORTEN_ENABLED", "").strip().lower() in ("true", "1", "yes")

        if profile == "corten" or corten_flag:
            self.load_corten_profile()

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_all_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def get_relevant_tools(self, query: str, top_k: int = 6) -> List[Tool]:
        """
        Dinamik Araç Keşfi (Semantic Tool Pruning).
        25+ aracın tamamını prompt'a basıp token harcamak yerine sorguyla en alakalı
        araçları dinamik olarak seçer. Temel dosya/terminal araçlarını güvenle önceliklendirir.
        """
        if not query or not self._tools:
            return list(self._tools.values())

        q_lower = query.lower()

        # Temel / vazgeçilmez araçlar (her zaman öncelikli)
        pinned_core_names = {"read_file", "run_terminal_command"}

        # Sorgu alanları ve anahtar kelimeleri
        coding_keywords = {"kod", "yaz", "düzenle", "refactor", "yama", "fonksiyon", "hata", "fix", "rust", "python", "file", "dosya"}
        git_keywords = {"git", "commit", "branch", "diff", "status", "checkpoint", "değişiklik"}
        web_keywords = {"web", "ara", "google", "site", "internet", "url", "haber"}
        math_keywords = {"hesapla", "topla", "böl", "çarp", "matematik", "sayı", "oran"}
        corten_keywords = {"ses", "parlaklık", "pencere", "ekran", "kilit", "masaüstü", "workspace"}

        scored_tools: List[tuple] = []

        for name, tool in self._tools.items():
            score = 0.0
            t_desc = tool.description.lower()
            t_name = name.lower()

            if name in pinned_core_names:
                score += 3.0

            # Kategori bazlı uyum
            if any(k in q_lower for k in coding_keywords) and name in ("apply_diff", "apply_multi_diff", "write_file", "list_files"):
                score += 4.0
            if any(k in q_lower for k in git_keywords) and "git" in t_name:
                score += 5.0
            if any(k in q_lower for k in web_keywords) and any(w in t_name for w in ("web", "search", "page")):
                score += 5.0
            if any(k in q_lower for k in math_keywords) and "calculator" in t_name:
                score += 5.0
            if any(k in q_lower for k in corten_keywords) and "corten" in t_name:
                score += 5.0
            if "mcp" in t_name and any(p in q_lower for p in t_name.split("_")):
                score += 4.0

            # Kelime kesişim skoru
            q_words = set(q_lower.split())
            desc_words = set(t_desc.split()) | set(t_name.split("_"))
            overlap = len(q_words & desc_words)
            score += overlap * 1.5

            scored_tools.append((score, tool))

        # Puana göre sırala ve en yüksek top_k aracı döndür
        scored_tools.sort(key=lambda x: x[0], reverse=True)
        selected = [t for _, t in scored_tools[:top_k]]
        return selected

    def get_tools_prompt_description(self, tools: Optional[List[Tool]] = None) -> str:
        """Belirtilen araçların (veya tüm araçların) prompt şemasını üretir."""
        target_tools = tools if tools is not None else self._tools.values()
        lines = []
        for t in target_tools:
            schema = t.to_schema()
            lines.append(f"- {schema['name']}: {schema['description']} (Parametreler: {schema['parameters']})")
        return "\n".join(lines)


# Singleton Tool Registry Instance
tool_registry = ToolRegistry()
