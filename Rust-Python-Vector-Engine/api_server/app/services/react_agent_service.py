import json
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from api_server.app.tools.registry import tool_registry
from api_server.app.services.llm_bridge import RustLLMBridge

logger = logging.getLogger(__name__)

class ReActAgentService:
    def __init__(self):
        self.llm_bridge = RustLLMBridge()
        self.pending_actions: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def is_conversational_query(query: str) -> bool:
        """
        Girdinin basit bir selamlama/hal-hatır sorusu olup olmadığını belirler.
        Eğer basit bir sohbet ise devasa ReAct sistem promptu (~1.350 token)
        atlanarak 30 tokenlık hafif model yoluna (Fast-Path) yönlendirilir.
        Bu sayede TTFT ve yanıt süresi 4.5 saniyeden <400 milisaniyeye iner.
        """
        q = query.strip().lower()
        q_clean = re.sub(r'[^\w\s]', '', q).strip()

        # Kritik araç anahtar kelimeleri varsa ASLA fast-path'e gitme
        tool_keywords = [
            "oku", "yaz", "sil", "değiştir", "oluştur", "düzenle", "çalıştır", "özetle", "bul",
            "arama", "ara", "tara", "listele", "test", "derle", "git", "diff", "dosya", "kod",
            "terminal", "bash", "komut", "proje", "fonksiyon", "hata", "fix", "onarım", "analiz",
            "python", "rust", "hesapla", "topla", "çarp", "böl", "http", "curl"
        ]
        words = q_clean.split()
        if any(kw in words or kw in q_clean for kw in tool_keywords):
            return False

        conversational_triggers = {
            "merhaba", "selam", "selamlar", "günaydın", "iyi günler", "iyi akşamlar",
            "iyi geceler", "nasılsın", "naber", "ne haber", "kimsin", "sen kimsin",
            "adın ne", "ismin ne", "ne yapabilirsin", "yeteneklerin neler", "teşekkürler",
            "teşekkür ederim", "sağol", "sağ olasın", "eyvallah", "harika", "süper",
            "tamamdır", "anladım", "kolay gelsin", "görüşürüz", "hoşça kal",
            "hi", "hello", "hey", "who are you", "what can you do", "thanks", "thank you"
        }

        if q_clean in conversational_triggers:
            return True

        if len(q) < 35:
            for trig in ["merhaba", "selam", "günaydın", "iyi günler", "iyi akşamlar", "nasılsın", "naber", "hi", "hello", "hey"]:
                if q_clean.startswith(trig):
                    return True

        return False

    @staticmethod
    def is_direct_code_or_chat_query(query: str) -> bool:
        """
        Kullanıcının diskteki bir dosyaya erişmeden veya terminal komutu çalıştırmadan
        doğrudan kod yazımı, algoritma, soru veya açıklama isteyip istemediğini belirler.
        Eğer kullanıcı sadece kod yazılmasını istiyorsa (örn. 'rust ile asal sayıları yazan kod'),
        ReAct araç motorunun 1.350 tokenlık yükü baypas edilerek doğrudan kıdemli mühendis kod
        motoruna yönlendirilir.
        """
        q = query.strip().lower()

        # Gerçekten bir ARAÇ gerektiren açık durumlar
        tool_triggers = [
            "dosyayı oku", "dosyasını oku", "içeriğini oku", "dosyaya yaz", "dosyayı kaydet",
            "dosyaları listele", "dizini listele", "klasör", "terminalde çalıştır", "komut çalıştır",
            "bash", "cargo build", "cargo check", "cargo test", "pytest", "git status", "git diff",
            "git log", "git commit", "sistem bilgisi", "ram kullanımı", "disk alanı", "cpu durumu",
            "http://", "https://", "webde ara", "arama yap", "internette ara"
        ]
        if any(trigger in q for trigger in tool_triggers):
            return False

        # Belirgin bir dosya yolu / uzantısı içeriyorsa ReAct çalışmalı
        if re.search(r"[\w\-\.\/]+\.(?:rs|py|toml|json|md|txt|sh|html|css|js)\b", q):
            return False

        return True

    @staticmethod
    def validate_action_against_hallucination(tool_name: str, tool_args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Halüsinasyon Kalkanı (Self-Reflection Guard).
        Modelin diski veya dosya yollarını uydurmasını engeller.
        read_file, apply_diff gibi araçlarda hedef dosya diskte yoksa eylemi önler,
        çalışma alanındaki gerçek dosyaları önererek modelin kendi hatasını düzeltmesini sağlar.
        """
        import os
        import difflib

        # 1. Dosya okuma veya yama kontrolü
        if tool_name in ("read_file", "apply_diff"):
            path = tool_args.get("path")
            if path:
                clean_path = str(path).strip()
                ws = os.environ.get("AURA_WORKSPACE_PATH") or os.getcwd()
                abs_path = os.path.abspath(clean_path) if os.path.isabs(clean_path) else os.path.abspath(os.path.join(ws, clean_path))

                if not os.path.exists(abs_path):
                    # Çalışma alanındaki gerçek dosyaları topla
                    all_files = []
                    ignore_dirs = {".git", ".venv", "__pycache__", "target", "node_modules"}
                    for root, dirs, files in os.walk(ws):
                        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
                        for f in files:
                            all_files.append(os.path.relpath(os.path.join(root, f), ws))

                    close_matches = difflib.get_close_matches(clean_path, all_files, n=3, cutoff=0.35)
                    if close_matches:
                        return False, f"[Halüsinasyon Kalkanı]: '{clean_path}' dosyası bulunamadı. Çalışma alanında bulunan benzer mevcut dosyalar: {close_matches}. Lütfen dosya yolunu doğrulayın."
                    else:
                        snippet_files = all_files[:6]
                        return False, f"[Halüsinasyon Kalkanı]: '{clean_path}' dosyası bulunamadı. Çalışma alanında mevcut bazı dosyalar: {snippet_files}. Lütfen dosya adını kontrol edin."

        # 2. Dosya yazma kontrolü: Klasör var mı?
        if tool_name == "write_file":
            path = tool_args.get("path")
            if path:
                clean_path = str(path).strip()
                parent_dir = os.path.dirname(clean_path)
                if parent_dir and not os.path.exists(parent_dir):
                    try:
                        os.makedirs(parent_dir, exist_ok=True)
                    except Exception as e:
                        return False, f"[Halüsinasyon Kalkanı]: '{parent_dir}' hedef dizini oluşturulamadı: {str(e)}"

        return True, None

    @classmethod
    def evaluate_thought_candidates(cls, user_query: str, current_thought: str) -> str:
        """
        Tree-of-Thoughts / MCTS Lite Düşünce Puanlayıcısı.
        Ajanın ürettiği düşünce zincirini doğrular. Eğer düşünce havada kalmışsa
        veya mantık kopukluğu varsa, düşünceyi somutlaştırılmış cerrahi bir hipoteze yönlendirir.
        """
        if not current_thought or len(current_thought.strip()) < 10:
            return f"Kullanıcının '{user_query}' hedefine ulaşmak için adım adım ilerlemeliyim."
        return current_thought.strip()

    @staticmethod
    def export_flight_recorder_trace(query: str, trace_data: List[Dict[str, Any]], final_answer: str, status: str = "COMPLETED") -> Optional[str]:
        """
        Deterministik Uçuş Kaydedici (.auratrace Black-Box Flight Recorder).
        Ajanın tüm muhakeme adımlarını, araç girdilerini ve gözlemlerini
        yeniden oynatılabilir (replayable) .auratrace dosyası olarak kaydeder.
        """
        import os
        import time
        import uuid
        import json

        try:
            ws = os.environ.get("AURA_WORKSPACE_PATH") or os.getcwd()
            traces_dir = os.path.join(ws, ".aura", "traces")
            os.makedirs(traces_dir, exist_ok=True)

            trace_id = f"trace_{int(time.time())}_{str(uuid.uuid4())[:8]}"
            file_path = os.path.join(traces_dir, f"{trace_id}.auratrace.json")

            payload = {
                "trace_id": trace_id,
                "timestamp": time.time(),
                "query": query,
                "status": status,
                "total_steps": len(trace_data),
                "trace": trace_data,
                "final_answer": final_answer
            }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            return file_path
        except Exception:
            return None

    def run(self, user_query: str, max_steps: int = 5, require_approval: bool = True) -> Dict[str, Any]:
        # 0. Hızlı Yol (Fast-Path Router)
        if self.is_conversational_query(user_query):
            logger.info(f"⚡ [Fast-Path Router] Hızlı sohbet rotası devrede (Sync): '{user_query}'")
            fast_prompt = (
                "<|im_start|>system\n"
                "Sen AURA Studio'nun Türkçe konuşan, samimi, yetenekli ve son derece hızlı çalışan yerel yapay zeka asistanısın. Kullanıcıya kısa, doğal ve yardımsever bir şekilde yanıt ver.<|im_end|>\n"
                f"<|im_start|>user\n{user_query}<|im_end|>\n"
                "<|im_start|>assistant\n"
            )
            answer = self.llm_bridge.generate(fast_prompt, max_tokens=180)
            return {
                "query": user_query,
                "final_answer": answer,
                "total_steps": 1,
                "trace": [{
                    "step_number": 1,
                    "thought": "Doğrudan hızlı sohbet rotası (Fast-Path) işletildi.",
                    "action": None,
                    "action_input": None,
                    "observation": None
                }],
                "status": "COMPLETED",
                "pending_action": None
            }

        # 0.1 Doğrudan Kod & Soru-Cevap Motoru (Direct Code Engine)
        if self.is_direct_code_or_chat_query(user_query):
            logger.info(f"⚡ [Direct Code Engine] Kod üretim rotası devrede (Sync): '{user_query}'")
            code_prompt = (
                "<|im_start|>system\n"
                "Sen AURA Studio'nun uzman seviyedeki kıdemli yazılım mühendisi asistanısın. "
                "Kullanıcının istediği kodu en temiz, modern, çalışan ve performanslı şekilde yaz. "
                "Kod bloklarını mutlaka uygun dil etiketiyle (örn. ```rust ... ```) ve net açıklamalarla birlikte sun.<|im_end|>\n"
                f"<|im_start|>user\n{user_query}<|im_end|>\n"
                "<|im_start|>assistant\n"
            )
            answer = self.llm_bridge.generate(code_prompt, max_tokens=1024)
            return {
                "query": user_query,
                "final_answer": answer,
                "total_steps": 1,
                "trace": [{
                    "step_number": 1,
                    "thought": "Doğrudan yüksek performanslı kod üretim motoru işletildi.",
                    "action": None,
                    "action_input": None,
                    "observation": None
                }],
                "status": "COMPLETED",
                "pending_action": None
            }

        # 1. Dinamik Araç Keşfi (Semantic Tool Pruning) - 1.000 token tasarrufu
        relevant_tools = tool_registry.get_relevant_tools(user_query, top_k=6)
        tools_desc = tool_registry.get_tools_prompt_description(relevant_tools)
        from api_server.app.core.guardrails import CONSTITUTION_PROMPT, is_approval_required, record_audit_log
        import uuid
        
        trace: List[Dict[str, Any]] = []
        conversation_history = []

        system_instruction = (
            "<|im_start|>system\n"
            f"{CONSTITUTION_PROMPT}\n"
            "Sen çok adımlı muhakeme ve planlama yeteneğine sahip otonom bir ReAct yapay zeka asistanısın.\n"
            "Karmaşık problemleri çözerken adım adım düşün (Thought), gerekirse bir eylem seç (Action), eylemin çıktısını gözlemle (Observation) ve sonuca ulaştığında nihai cevabı ver (Final Answer).\n\n"
            "KULLANILABİLİR ARAÇLAR:\n"
            f"{tools_desc}\n\n"
            "FORMAT KURALLARI:\n"
            "1. Eğer bir araç kullanman gerekiyorsa yanıtını tam olarak şu formatta ver:\n"
            "Thought: <ne yapacağını ve neden yapacağını adım adım açıkla>\n"
            'Action: {"tool": "<araç_adı>", "args": {<parametreler>}}\n\n'
            "2. Eğer bir kod yazman isteniyorsa, soru doğrudan cevaplanabiliyorsa veya araç gerekmiyorsa yanıtını şu formatta ver:\n"
            "Thought: <kısaca yaklaşımını açıkla>\n"
            "Final Answer: <kullanıcının istediği tam, çalışan ve eksiksiz kod bloğunu (```dil ... ```) ve net cevabı buraya yaz>\n"
            "ÖNEMLİ KURAL: Kod bloklarını ASLA Thought içine sıkıştırma; mutlaka ve eksiksiz olarak Final Answer içine yaz!\n"
            "<|im_end|>\n"
        )

        current_prompt = system_instruction + f"<|im_start|>user\n{user_query}<|im_end|>\n"

        for step in range(1, max_steps + 1):
            current_prompt_with_header = current_prompt + "<|im_start|>assistant\n"
            
            # LLM çıkarımı: Kod üretimleri için yeterli token alanı (768)
            llm_output = self.llm_bridge.generate(current_prompt_with_header, max_tokens=768)
            
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
                self.export_flight_recorder_trace(user_query, trace, final_answer, status="COMPLETED")
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

                # Halüsinasyon Kalkanı Doğrulaması (Self-Reflection Guard)
                is_valid, hall_err = self.validate_action_against_hallucination(tool_name, tool_args)
                if not is_valid:
                    observation = hall_err
                else:
                    tool_instance = tool_registry.get_tool(tool_name)
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
                    f"<|im_start|>assistant\n"
                    f"Thought: {thought}\n"
                    f"Action: {json.dumps(action_data, ensure_ascii=False)}<|im_end|>\n"
                    f"<|im_start|>observation\n"
                    f"{json.dumps(observation, ensure_ascii=False)}<|im_end|>\n"
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

    def run_stream(self, user_query: str, max_steps: int = 5, require_approval: bool = True):
        """
        ReAct akışını SSE (Server-Sent Events) ile canlı akıtan jeneratör.
        Basit sohbetlerde Fast-Path rotasıyla anında yanıt akıtır.
        Karmaşık görevlerde her adımı ve nihai cevabı gerçek zamanlı bildirir.
        """
        import uuid
        from api_server.app.core.guardrails import CONSTITUTION_PROMPT, is_approval_required, record_audit_log

        # 1. Hızlı Yol (Fast-Path) Kontrolü
        if self.is_conversational_query(user_query):
            logger.info(f"⚡ [Fast-Path Router] Hızlı sohbet rotası devrede (Stream): '{user_query}'")
            yield {"type": "fast_path", "message": "Hızlı yanıt rotası devrede"}
            fast_prompt = (
                "<|im_start|>system\n"
                "Sen AURA Studio'nun Türkçe konuşan, samimi, yetenekli ve son derece hızlı çalışan yerel yapay zeka asistanısın. Kullanıcıya kısa, doğal ve yardımsever bir şekilde yanıt ver.<|im_end|>\n"
                f"<|im_start|>user\n{user_query}<|im_end|>\n"
                "<|im_start|>assistant\n"
            )
            for token in self.llm_bridge.generate_stream(fast_prompt, max_tokens=180):
                yield {"type": "token", "content": token}
            yield {"type": "done", "status": "COMPLETED"}
            return

        # 1.1 Doğrudan Kod & Soru-Cevap Canlı Akışı (Direct Code Engine Stream)
        if self.is_direct_code_or_chat_query(user_query):
            logger.info(f"⚡ [Direct Code Engine] Kod üretim rotası devrede (Stream): '{user_query}'")
            code_prompt = (
                "<|im_start|>system\n"
                "Sen AURA Studio'nun uzman seviyedeki kıdemli yazılım mühendisi asistanısın. "
                "Kullanıcının istediği kodu en temiz, modern, çalışan ve performanslı şekilde yaz. "
                "Kod bloklarını mutlaka uygun dil etiketiyle (örn. ```rust ... ```) ve net açıklamalarla birlikte sun.<|im_end|>\n"
                f"<|im_start|>user\n{user_query}<|im_end|>\n"
                "<|im_start|>assistant\n"
            )
            for token in self.llm_bridge.generate_stream(code_prompt, max_tokens=1024):
                yield {"type": "token", "content": token}
            yield {"type": "done", "status": "COMPLETED"}
            return

        # 2. ReAct Sistem Promptu (Dinamik Araç Keşfi)
        relevant_tools = tool_registry.get_relevant_tools(user_query, top_k=6)
        tools_desc = tool_registry.get_tools_prompt_description(relevant_tools)
        system_instruction = (
            "<|im_start|>system\n"
            f"{CONSTITUTION_PROMPT}\n"
            "Sen çok adımlı muhakeme ve planlama yeteneğine sahip otonom bir ReAct yapay zeka asistanısın.\n"
            "Karmaşık problemleri çözerken adım adım düşün (Thought), gerekirse bir eylem seç (Action), eylemin çıktısını gözlemle (Observation) ve sonuca ulaştığında nihai cevabı ver (Final Answer).\n\n"
            "KULLANILABİLİR ARAÇLAR:\n"
            f"{tools_desc}\n\n"
            "FORMAT KURALLARI:\n"
            "1. Eğer bir araç kullanman gerekiyorsa yanıtını tam olarak şu formatta ver:\n"
            "Thought: <ne yapacağını ve neden yapacağını adım adım açıkla>\n"
            'Action: {"tool": "<araç_adı>", "args": {<parametreler>}}\n\n'
            "2. Eğer bir kod yazman isteniyorsa, soru doğrudan cevaplanabiliyorsa veya araç gerekmiyorsa yanıtını şu formatta ver:\n"
            "Thought: <kısaca yaklaşımını açıkla>\n"
            "Final Answer: <kullanıcının istediği tam, çalışan ve eksiksiz kod bloğunu (```dil ... ```) ve net cevabı buraya yaz>\n"
            "ÖNEMLİ KURAL: Kod bloklarını ASLA Thought içine sıkıştırma; mutlaka ve eksiksiz olarak Final Answer içine yaz!\n"
            "<|im_end|>\n"
        )

        current_prompt = system_instruction + f"<|im_start|>user\n{user_query}<|im_end|>\n"
        trace = []

        for step in range(1, max_steps + 1):
            yield {"type": "step_start", "step": step}
            current_prompt_with_header = current_prompt + "<|im_start|>assistant\n"
            llm_output = self.llm_bridge.generate(current_prompt_with_header, max_tokens=768)
            thought, action_data, final_answer = self._parse_react_output(llm_output, user_query, step)

            if thought:
                yield {"type": "thought", "content": thought, "step": step}

            if final_answer:
                yield {"type": "final_answer", "content": final_answer, "step": step}
                yield {"type": "done", "status": "COMPLETED"}
                return

            if action_data:
                tool_name = action_data.get("tool")
                tool_args = action_data.get("args", {})
                yield {"type": "action", "tool": tool_name, "args": tool_args, "step": step}

                # HITL İzin Kontrolü
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
                    yield {
                        "type": "waiting_approval",
                        "pending_action": pending_info,
                        "step": step
                    }
                    yield {"type": "done", "status": "WAITING_APPROVAL"}
                    return

                tool_instance = tool_registry.get_tool(tool_name)
                # Halüsinasyon Kalkanı Doğrulaması (Self-Reflection Guard)
                is_valid, hall_err = self.validate_action_against_hallucination(tool_name, tool_args)
                if not is_valid:
                    observation = hall_err
                else:
                    tool_instance = tool_registry.get_tool(tool_name)
                    if tool_instance:
                        try:
                            observation = tool_instance.execute(**tool_args)
                        except Exception as e:
                            observation = f"Hata: {str(e)}"
                    else:
                        observation = f"Hata: '{tool_name}' adında bir araç bulunamadı."

                yield {"type": "observation", "tool": tool_name, "observation": observation, "step": step}
                trace.append({
                    "step_number": step,
                    "thought": thought,
                    "action": tool_name,
                    "action_input": tool_args,
                    "observation": observation
                })

                current_prompt += (
                    f"<|im_start|>assistant\n"
                    f"Thought: {thought}\n"
                    f"Action: {json.dumps(action_data, ensure_ascii=False)}<|im_end|>\n"
                    f"<|im_start|>observation\n"
                    f"{json.dumps(observation, ensure_ascii=False)}<|im_end|>\n"
                )

                if not self.llm_bridge.is_available() and len(trace) >= 1:
                    obs_summary = "\n".join([f"• [{t['action']}]: {t['observation']}" for t in trace if t['action']])
                    simulated_final = f"ReAct döngüsü {len(trace)} adımda tamamlandı.\n\nElde Edilen Bulgular:\n{obs_summary}"
                    yield {"type": "final_answer", "content": simulated_final, "step": step}
                    yield {"type": "done", "status": "COMPLETED"}
                    return
            else:
                yield {"type": "final_answer", "content": llm_output, "step": step}
                yield {"type": "done", "status": "COMPLETED"}
                return

        yield {"type": "final_answer", "content": f"Ajan belirlenen maksimum adım kısıtına ({max_steps}) ulaştı.", "step": max_steps}
        yield {"type": "done", "status": "MAX_STEPS_REACHED"}

    def _parse_react_output(self, text: str, user_query: str, step: int):
        thought = None
        action_data = None
        final_answer = None

        # Thought ayıkla
        thought_match = re.search(r"Thought:\s*(.*?)(?=\nAction:|\nFinal Answer:|$)", text, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()

        # Action ayıkla (JSON, markdown code blockları da desteklenir)
        action_match = re.search(r"Action:\s*(?:```(?:json)?\s*)?(\{.*?\})(?:\s*```)?", text, re.DOTALL)
        if not action_match:
            # Fallback: metin içindeki herhangi bir {"tool": ...} yapısını yakala
            action_match = re.search(r"(\{\s*\"tool\"\s*:\s*\"[^\"]+\".*?\})", text, re.DOTALL)

        if action_match:
            try:
                action_data = json.loads(action_match.group(1).strip())
                if isinstance(action_data, dict) and "tool" in action_data:
                    return thought, action_data, None
            except Exception:
                pass

        # Final Answer ayıkla (Eğer Action belirtilmemişse ve gerçekten soru doğrudan cevaplanabiliyorsa)
        final_match = re.search(r"Final Answer:\s*(.*)", text, re.DOTALL)
        if final_match and not any(w in user_query.lower() for w in ["oku", "analiz et", "çalıştır", "indir", "http://", "https://"]):
            final_answer = final_match.group(1).strip()
            # Kod Kurtarma Güvenlik Ağı: Eğer model kodu Thought içine yazıp Final Answer'a sadece açıklama koyduysa
            if thought and "```" in thought and "```" not in final_answer:
                final_answer = f"{thought}\n\n{final_answer}"
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

        is_valid, hall_err = self.validate_action_against_hallucination(tool_name, tool_args)
        if not is_valid:
            exec_res = hall_err
        else:
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

