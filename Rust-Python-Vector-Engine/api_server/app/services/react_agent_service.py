import json
import re
import logging
from typing import Dict, Any, List, Optional
from api_server.app.tools.registry import tool_registry
from api_server.app.services.llm_bridge import RustLLMBridge

logger = logging.getLogger(__name__)

class ReActAgentService:
    def __init__(self):
        self.llm_bridge = RustLLMBridge()
        self.pending_actions: Dict[str, Dict[str, Any]] = {}

    def run(self, user_query: str, max_steps: int = 5, require_approval: bool = True) -> Dict[str, Any]:
        tools_desc = tool_registry.get_tools_prompt_description()
        from api_server.app.core.guardrails import CONSTITUTION_PROMPT, is_approval_required, record_audit_log
        import uuid
        
        trace: List[Dict[str, Any]] = []
        conversation_history = []

        system_instruction = (
            "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
            f"{CONSTITUTION_PROMPT}\n"
            "Sen çok adımlı muhakeme ve planlama yeteneğine sahip otonom bir ReAct yapay zeka asistanısın.\n"
            "Karmaşık problemleri çözerken adım adım düşün (Thought), gerekirse bir eylem seç (Action), eylemin çıktısını gözlemle (Observation) ve sonuca ulaştığında nihai cevabı ver (Final Answer).\n\n"
            "KULLANILABİLİR ARAÇLAR:\n"
            f"{tools_desc}\n\n"
            "FORMAT KURALLARI:\n"
            "1. Eğer bir araç kullanman gerekiyorsa yanıtını tam olarak şu formatta ver:\n"
            "Thought: <ne yapacağını ve neden yapacağını adım adım açıkla>\n"
            'Action: {"tool": "<araç_adı>", "args": {<parametreler>}}\n\n'
            "2. Eğer soruyu cevaplamak için tüm bilgilere ulaştıysan veya araç gerekmiyorsa yanıtını şu formatta ver:\n"
            "Thought: <nihai sonuca nasıl ulaştığını açıkla>\n"
            "Final Answer: <kullanıcıya verilecek net ve tam cevap>\n"
            "<|eot_id|>\n"
        )

        current_prompt = system_instruction + f"<|start_header_id|>user<|end_header_id|>\n{user_query}<|eot_id|>\n"

        for step in range(1, max_steps + 1):
            current_prompt_with_header = current_prompt + f"<|start_header_id|>assistant<|end_header_id|>\n"
            
            # LLM çıkarımı
            llm_output = self.llm_bridge.generate(current_prompt_with_header, max_tokens=350)
            
            thought, action_data, final_answer = self._parse_react_output(llm_output, user_query, step)

            # Eğer LLM nihai cevaba ulaştıysa
            if final_answer:
                trace.append({
                    "step_number": step,
                    "thought": thought or "Nihai sonuca ulaşıldı.",
                    "action": None,
                    "action_input": None,
                    "observation": None
                })
                return {
                    "query": user_query,
                    "final_answer": final_answer,
                    "total_steps": step,
                    "trace": trace,
                    "status": "COMPLETED",
                    "pending_action": None
                }

            # Eğer bir action tespiti yapıldıysa
            if action_data:
                tool_name = action_data.get("tool")
                tool_args = action_data.get("args", {})
                tool_instance = tool_registry.get_tool(tool_name)

                # HUMAN-IN-THE-LOOP (HITL) Güvenlik & İzin Kontrolü
                if require_approval and is_approval_required(tool_name, tool_args):
                    action_id = str(uuid.uuid4())
                    pending_desc = f"'{tool_name}' aracı parametrelerle çalıştırılmak isteniyor: {json.dumps(tool_args, ensure_ascii=False)}"
                    
                    pending_info = {
                        "action_id": action_id,
                        "tool": tool_name,
                        "args": tool_args,
                        "description": pending_desc,
                        "user_query": user_query,
                        "step": step,
                        "thought": thought,
                        "trace": trace
                    }
                    self.pending_actions[action_id] = pending_info
                    
                    trace.append({
                        "step_number": step,
                        "thought": thought or f"'{tool_name}' aracını çalıştırmak için kullanıcıdan onay bekleniyor.",
                        "action": tool_name,
                        "action_input": tool_args,
                        "observation": "⏳ [ONAY BEKLENİYOR] Bu işlem diski veya sistemi etkilediği için kullanıcının açık onayı bekleniyor."
                    })
                    
                    return {
                        "query": user_query,
                        "final_answer": f"⚠️ Güvenlik & İnsan Onayı: Ajan **[{tool_name}]** aracını çalıştırmak istiyor ancak bu eylem kritik kategorisindedir. Devam etmek için onayınız gerekiyor.",
                        "total_steps": step,
                        "trace": trace,
                        "status": "WAITING_APPROVAL",
                        "pending_action": {
                            "action_id": action_id,
                            "tool": tool_name,
                            "args": tool_args,
                            "description": pending_desc
                        }
                    }

                if tool_instance:
                    try:
                        observation = tool_instance.execute(**tool_args)
                    except Exception as e:
                        observation = f"Hata: {str(e)}"
                else:
                    observation = f"Hata: '{tool_name}' adında bir araç bulunamadı."

                step_record = {
                    "step_number": step,
                    "thought": thought or f"{tool_name} aracı çalıştırılıyor.",
                    "action": tool_name,
                    "action_input": tool_args,
                    "observation": observation
                }
                trace.append(step_record)

                # Prompt geçmişini güncelle (ReAct Loop append)
                current_prompt += (
                    f"<|start_header_id|>assistant<|end_header_id|>\n"
                    f"Thought: {thought}\n"
                    f"Action: {json.dumps(action_data, ensure_ascii=False)}<|eot_id|>\n"
                    f"<|start_header_id|>observation<|end_header_id|>\n"
                    f"{json.dumps(observation, ensure_ascii=False)}<|eot_id|>\n"
                )

                # Simülasyon modunda (Model henüz yüklü değilse) 2. adımdan sonra fallback yanıtı üret
                if not self.llm_bridge.is_available() and len(trace) >= 1:
                    # Simülasyon döngüsünü sonlandır
                    obs_summary = "\n".join([f"• [{t['action']}]: {t['observation']}" for t in trace if t['action']])
                    simulated_final = f"ReAct döngüsü {len(trace)} adımda tamamlandı.\n\nElde Edilen Bulgular:\n{obs_summary}"
                    return {
                        "query": user_query,
                        "final_answer": simulated_final,
                        "total_steps": len(trace),
                        "trace": trace,
                        "status": "COMPLETED",
                        "pending_action": None
                    }
            else:
                # Ne action ne de final answer bulunamadıysa metni nihai cevap kabul et
                trace.append({
                    "step_number": step,
                    "thought": "Doğrudan yanıt üretildi.",
                    "action": None,
                    "action_input": None,
                    "observation": None
                })
                return {
                    "query": user_query,
                    "final_answer": llm_output,
                    "total_steps": step,
                    "trace": trace
                }

        # Max steps aşıldığında
        return {
            "query": user_query,
            "final_answer": f"Ajan belirlenen maksimum adım kısıtına ({max_steps}) ulaştı. Elde edilen son bilgi: {trace[-1]['observation'] if trace else 'Yok'}",
            "total_steps": max_steps,
            "trace": trace
        }

    def _parse_react_output(self, text: str, user_query: str, step: int):
        thought = None
        action_data = None
        final_answer = None

        # Thought ayıkla
        thought_match = re.search(r"Thought:\s*(.*?)(?=\nAction:|\nFinal Answer:|$)", text, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()

        # Action ayıkla (JSON)
        action_match = re.search(r"Action:\s*(\{.*\})", text, re.DOTALL)
        if action_match:
            try:
                action_data = json.loads(action_match.group(1).strip())
                return thought, action_data, None
            except Exception:
                pass

        # Final Answer ayıkla (Eğer Action belirtilmemişse ve gerçekten soru doğrudan cevaplanabiliyorsa)
        final_match = re.search(r"Final Answer:\s*(.*)", text, re.DOTALL)
        if final_match and not any(w in user_query.lower() for w in ["oku", "analiz et", "çalıştır", "indir", "http://", "https://"]):
            final_answer = final_match.group(1).strip()
            return thought, None, final_answer

        # Simülasyon / Fallback Mantığı (Model henüz yerel mmap yüklemesinde varsayılan simülasyon çıktısı veriyorsa)
        q = user_query.lower()

        # Karmaşık çok adımlı soru örneği: hem sistem hem hesaplama
        if step == 1:
            if "http://" in user_query or "https://" in user_query:
                url_match = re.search(r"https?://[^\s<>\"']+", user_query)
                if url_match:
                    thought = f"'{url_match.group(0)}' web sayfasının içeriğini bot korumalarını atlatıp okumalıyım."
                    action_data = {"tool": "read_web_page", "args": {"url": url_match.group(0)}}
                    return thought, action_data, None
            elif any(w in q for w in ["dosyayı oku", "içeriğini oku", "oku"]) and any(ext in q for ext in [".rs", ".py", ".toml", ".json", ".md"]):
                match = re.search(r"[\w\-\.\/]+\.(?:rs|py|toml|json|md|txt)", user_query)
                if match:
                    thought = f"'{match.group(0)}' dosyasının içeriğini okumalıyım."
                    action_data = {"tool": "read_file", "args": {"path": match.group(0)}}
                    return thought, action_data, None
            elif any(w in q for w in ["cargo check", "cargo build", "pytest"]):
                cmd = re.search(r"(cargo check|cargo build|pytest[^\n]*)", user_query)
                if cmd:
                    thought = f"Terminalde derleme/test komutunu çalıştırmalıyım: {cmd.group(0)}"
                    action_data = {"tool": "run_terminal_command", "args": {"command": cmd.group(0)}}
                    return thought, action_data, None
            elif "git" in q and ("status" in q or "durum" in q or "değişiklik" in q):
                thought = "Git sürüm kontrolü durumunu kontrol etmeliyim."
                action_data = {"tool": "git_status", "args": {}}
                return thought, action_data, None
            elif any(w in q for w in ["dosyaları listele", "dosya listesi", "neler var", "klasör"]):
                thought = "Proje dizinindeki dosyaları listelemeliyim."
                action_data = {"tool": "list_files", "args": {"directory": "."}}
                return thought, action_data, None
            elif any(w in q for w in ["ram", "cpu", "disk", "sistem"]):
                thought = "Önce sistem metriklerini okumalıyım."
                action_data = {"tool": "system_info", "args": {"metric": "all"}}
                return thought, action_data, None
            elif any(w in q for w in ["kaçtır", "hesapla", "*", "+"]) and re.search(r"\d", q):
                thought = "Matematiksel işlemi çözmek için hesap makinesini kullanmalıyım."
                expr = re.sub(r"[^0-9\+\-\*\/\.\(\)\s]", "", q).strip()
                action_data = {"tool": "calculator", "args": {"expression": expr or "1+1"}}
                return thought, action_data, None
            elif any(w in q for w in ["arama", "hava durumu", "haber"]):
                thought = "İnternette güncel arama yapmalıyım."
                action_data = {"tool": "web_search", "args": {"query": user_query}}
                return thought, action_data, None
            elif any(w in q for w in ["cargo check", "cargo build", "pytest"]):
                cmd = re.search(r"(cargo check|cargo build|pytest[^\n]*)", user_query)
                if cmd:
                    thought = f"Terminalde derleme/test komutunu çalıştırmalıyım: {cmd.group(0)}"
                    action_data = {"tool": "run_terminal_command", "args": {"command": cmd.group(0)}}
                    return thought, action_data, None

        return thought, None, text

    def execute_decision(self, action_id: str, approved: bool, rejection_reason: Optional[str] = None) -> Dict[str, Any]:
        """Kullanıcının bekleyen eylem için verdiği kararı (Onay/Red) yürütür."""
        from api_server.app.core.guardrails import record_audit_log

        if action_id not in self.pending_actions:
            return {
                "action_id": action_id,
                "status": "ERROR",
                "result": None,
                "message": "Bekleyen eylem bulunamadı veya süresi dolmuş."
            }

        pending = self.pending_actions.pop(action_id)
        tool_name = pending["tool"]
        tool_args = pending["args"]

        if not approved:
            record_audit_log(tool_name, tool_args, approved=False, reason=rejection_reason or "Kullanıcı tarafından reddedildi.")
            return {
                "action_id": action_id,
                "status": "CANCELLED",
                "result": None,
                "message": f"'{tool_name}' eylemi kullanıcı tarafından iptal edildi. Gerekçe: {rejection_reason or 'Belirtilmedi'}"
            }

        # Onaylandıysa eylemi yürüt
        record_audit_log(tool_name, tool_args, approved=True, reason="Kullanıcı onay verdi.")
        tool_instance = tool_registry.get_tool(tool_name)
        
        try:
            if tool_instance:
                exec_res = tool_instance.execute(**tool_args)
            else:
                exec_res = f"Hata: '{tool_name}' aracı bulunamadı."
        except Exception as e:
            exec_res = f"Çalıştırma hatası: {str(e)}"

        return {
            "action_id": action_id,
            "status": "EXECUTED",
            "result": exec_res,
            "message": f"'{tool_name}' aracı kullanıcı onayıyla başarıyla çalıştırıldı."
        }

react_agent_service = ReActAgentService()

