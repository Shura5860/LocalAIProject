import json
import re
import logging
from typing import Dict, Any, Optional
from api_server.app.tools.registry import tool_registry
from api_server.app.services.llm_bridge import RustLLMBridge

logger = logging.getLogger(__name__)

class AgentService:
    def __init__(self):
        self.llm_bridge = RustLLMBridge()

    def run(self, user_query: str, max_tokens: int = 300) -> Dict[str, Any]:
        tools_desc = tool_registry.get_tools_prompt_description()
        from api_server.app.core.guardrails import CONSTITUTION_PROMPT

        system_prompt = (
            "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
            f"{CONSTITUTION_PROMPT}\n"
            "Sen gelişmiş araçları (tools) kullanabilen akıllı ve otonom bir yapay zeka asistanısın.\n"
            "Kullanıcının isteğini yerine getirmek için gerekirse aşağıdaki araçlardan birini çağırabilirsin:\n\n"
            f"{tools_desc}\n\n"
            "TALİMATLAR:\n"
            "1. Eğer kullanıcının sorusu bir araç (hesaplama, sistem bilgisi, web araması, kod çalıştırma) gerektiriyorsa, YALNIZCA şu JSON formatında yanıt ver:\n"
            '{"action": "tool_call", "tool": "<araç_adı>", "args": {<parametreler>}}\n'
            "2. Eğer araç çağırmak gerekmiyorsa doğrudan normal bir asistan gibi kullanıcıya cevap ver.\n"
            "<|eot_id|>\n"
            f"<|start_header_id|>user<|end_header_id|>\n"
            f"{user_query}<|eot_id|>\n"
            "<|start_header_id|>assistant<|end_header_id|>\n"
        )

        # İlk çıkarım (LLM Kararı)
        llm_response = self.llm_bridge.generate(system_prompt, max_tokens=max_tokens)
        
        # Tool Call tespiti (JSON blokları veya doğrudan JSON)
        tool_call_data = self._extract_tool_call(llm_response, user_query)

        if not tool_call_data:
            return {
                "query": user_query,
                "answer": llm_response,
                "tool_used": None,
                "tool_result": None
            }

        tool_name = tool_call_data.get("tool")
        tool_args = tool_call_data.get("args", {})
        tool_instance = tool_registry.get_tool(tool_name)

        if not tool_instance:
            return {
                "query": user_query,
                "answer": f"Model bilinmeyen bir araç çağırmak istedi: '{tool_name}'",
                "tool_used": tool_name,
                "tool_result": None
            }

        # Aracı çalıştır
        try:
            tool_result = tool_instance.execute(**tool_args)
        except Exception as e:
            tool_result = f"Araç çalıştırma hatası: {str(e)}"

        # Model dosyası henüz diskte değilse (Simülasyon/Test ortamı)
        if not self.llm_bridge.is_available():
            formatted_answer = f"🛠️ **[{tool_name}]** aracı başarıyla çalıştırıldı:\nSonuç: `{tool_result}`"
            return {
                "query": user_query,
                "answer": formatted_answer,
                "tool_used": {"name": tool_name, "args": tool_args},
                "tool_result": tool_result
            }

        # Aracı çalıştırdıktan sonra sonucu modele verip son cevabı ürettirme
        followup_prompt = (
            f"{system_prompt}"
            f'{{"action": "tool_call", "tool": "{tool_name}", "args": {json.dumps(tool_args)}}}<|eot_id|>\n'
            f"<|start_header_id|>tool<|end_header_id|>\n"
            f"{json.dumps(tool_result, ensure_ascii=False)}<|eot_id|>\n"
            f"<|start_header_id|>assistant<|end_header_id|>\n"
        )

        final_answer = self.llm_bridge.generate(followup_prompt, max_tokens=max_tokens)

        return {
            "query": user_query,
            "answer": final_answer,
            "tool_used": {"name": tool_name, "args": tool_args},
            "tool_result": tool_result
        }

    def _extract_tool_call(self, text: str, user_query: str) -> Optional[Dict[str, Any]]:
        # 1. JSON metni ara
        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                if data.get("action") == "tool_call" and "tool" in data:
                    return data
        except Exception:
            pass

        # 2. Akıllı Heuristik / Intent Fallback (Model henüz eğitilmemiş veya simülasyon modundaysa)
        q = user_query.lower()
        if any(w in q for w in ["kaçtır", "hesapla", "*", "+", "/", "^", "karekök"]) and re.search(r"\d", q):
            # Matematik ifadesini ayıkla
            expr = re.sub(r"[^0-9\+\-\*\/\.\(\)\s]", "", q).strip()
            if expr:
                return {"action": "tool_call", "tool": "calculator", "args": {"expression": expr}}

        if any(w in q for w in ["ram", "cpu", "işlemci", "disk alanı", "sistem durumu", "bellek"]):
            return {"action": "tool_call", "tool": "system_info", "args": {"metric": "all"}}

        if "http://" in user_query or "https://" in user_query:
            url_match = re.search(r"https?://[^\s<>\"']+", user_query)
            if url_match:
                return {"action": "tool_call", "tool": "read_web_page", "args": {"url": url_match.group(0)}}

        if any(w in q for w in ["hava durumu", "arama yap", "kimdir", "son dakika", "haberler"]):
            return {"action": "tool_call", "tool": "web_search", "args": {"query": user_query}}

        if any(w in q for w in ["sayfayı oku", "linki oku", "web sayfasını"]):
            url_match = re.search(r"https?://[^\s<>\"']+", user_query)
            if url_match:
                return {"action": "tool_call", "tool": "read_web_page", "args": {"url": url_match.group(0)}}

        if "git" in q and ("status" in q or "durum" in q or "değişiklik" in q):
            return {"action": "tool_call", "tool": "git_status", "args": {}}

        if "git diff" in q or "farklar" in q:
            return {"action": "tool_call", "tool": "git_diff", "args": {}}

        if any(w in q for w in ["dosyaları listele", "dosya listesi", "neler var", "klasör"]):
            return {"action": "tool_call", "tool": "list_files", "args": {"directory": "."}}

        if any(w in q for w in ["dosyayı oku", "içeriğini oku", "oku"]) and any(ext in q for ext in [".rs", ".py", ".toml", ".json", ".md"]):
            # Dosya adını ayıkla
            match = re.search(r"[\w\-\.\/]+\.(?:rs|py|toml|json|md|txt)", user_query)
            if match:
                return {"action": "tool_call", "tool": "read_file", "args": {"path": match.group(0)}}

        if any(w in q for w in ["cargo check", "cargo build", "pytest", "python tests"]):
            cmd = re.search(r"(cargo check|cargo build|pytest[^\n]*|python tests[^\n]*)", user_query)
            if cmd:
                return {"action": "tool_call", "tool": "run_terminal_command", "args": {"command": cmd.group(0)}}

        return None

agent_service = AgentService()
