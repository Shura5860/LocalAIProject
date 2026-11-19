import os
import json
import numpy as np
import logging
from typing import Dict, Any, List, Optional, Tuple
from sentence_transformers import SentenceTransformer
from api_server.app.core.config import db, allocate_doc_ids

logger = logging.getLogger(__name__)

PROFILE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../user_profile.json"))

class MemoryService:
    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.embedding_model_name = model_name
        self._embedder: Optional[SentenceTransformer] = None
        self._ensure_profile_exists()

    @property
    def embedder(self):
        if self._embedder is None:
            from api_server.app.services.rag_service import rag_service
            self._embedder = rag_service.embedder
        return self._embedder

    def _ensure_profile_exists(self):
        if not os.path.exists(PROFILE_FILE):
            default_profile = {
                "name": "Shura",
                "os": "Arch Linux",
                "preferred_languages": ["Rust", "Python"],
                "tone": "teknik, samimi, net ve doğrudan",
                "custom_notes": [
                    "Performans ve bellek optimizasyonuna (SIMD, HNSW) çok önem verir.",
                    "Sisteminde Rust LLM ve Rust Vektör Veritabanı motorlarını kullanır."
                ]
            }
            with open(PROFILE_FILE, "w", encoding="utf-8") as f:
                json.dump(default_profile, f, ensure_ascii=False, indent=2)

    def get_profile(self) -> Dict[str, Any]:
        try:
            with open(PROFILE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def update_profile(self, new_data: Dict[str, Any]) -> Dict[str, Any]:
        profile = self.get_profile()
        profile.update(new_data)
        with open(PROFILE_FILE, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        return profile

    def sanitize_memory_fact(self, fact: str) -> Tuple[bool, str]:
        """
        Hafıza Zehirlenmesi Kalkanı (Memory Poisoning Prevention).
        Uzun vadeli hafızaya güvenlik kurallarını, HITL onaylarını veya anayasayı
        devre dışı bırakacak manipülatif tercihlerin işlenmesini engeller.
        """
        import re
        poison_patterns = [
            r"(?i)(disable|bypass|ignore|kaldır|devre\s+dışı|unut).*(hitl|approval|onay|guardrail|güvenlik|anayas|ethics|constitution)",
            r"(?i)(hitl|approval|onay|guardrail|güvenlik|anayas|ethics|constitution).*(disable|bypass|ignore|kaldır|devre\s+dışı|unut)",
            r"(?i)(onaysız|doğrudan|unapproved|without\s+approval).*(çalıştır|execute|run)",
            r"(?i)(her\s+zaman|otomatik|always).*(onaysız|doğrudan|without\s+approval)",
            r"(?i)(never|asla).*(ask|sor|onay\s+iste|approval)",
            r"(?i)system\s+prompt\s+override",
            r"(?i)kullanıcı\s+tüm\s+yetkilere\s+sahiptir"
        ]
        for pattern in poison_patterns:
            if re.search(pattern, fact):
                return False, f"Güvenlik Kalkanı: Hafıza zehirleme veya güvenlik kuralı manipülasyonu tespit edildi: '{pattern}'"
        return True, "Güvenli."

    def remember_fact(self, fact: str, topic: str = "personal", importance: float = 1.0) -> Dict[str, Any]:
        """Kullanıcı hakkındaki önemli bir anıyı veya bilgiyi Rust HNSW vektör indeksine kalıcı olarak işler."""
        if not fact.strip():
            return {"status": "error", "message": "Boş bilgi kaydedilemez."}

        is_safe, msg = self.sanitize_memory_fact(fact)
        if not is_safe:
            logger.warning(f"🛡️ [AI Security] Hafıza zehirleme girişimi engellendi: {fact}")
            return {"status": "error", "message": msg}

        import time
        embeddings = self.embedder.encode([fact], convert_to_numpy=True).astype(np.float32)
        doc_id = allocate_doc_ids(1)[0]
        meta = {
            "text": str(fact),
            "category": "user_memory",
            "topic": str(topic),
            "importance": str(float(importance)),
            "created_at": str(float(time.time()))
        }

        db.add_batch_with_metadata([doc_id], embeddings, [meta])
        db.build_hnsw_index()
        return {"status": "success", "id": doc_id, "fact": fact}

    def recall_facts(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Soruyla veya durumla ilgili geçmiş anıları HNSW ve zamansal çürüme (decay) skoruyla çeker."""
        if db.len() == 0:
            return []

        import time
        import math
        now = time.time()
        query_vec = self.embedder.encode(query, convert_to_numpy=True).astype(np.float32)
        try:
            results = db.search_filtered(
                query_vec,
                top_k=top_k * 2,
                filter_key="category",
                filter_value="user_memory",
                operator="=="
            )
            recalled = []
            for doc_id, dist, meta in results:
                importance = float(meta.get("importance", 1.0))
                created_at = float(meta.get("created_at", now))
                elapsed_days = (now - created_at) / 86400.0
                decay = math.exp(-0.02 * elapsed_days)
                effective_score = (1.0 / (1.0 + float(dist))) * importance * decay

                recalled.append({
                    "id": doc_id,
                    "distance": float(dist),
                    "decay_score": round(effective_score, 4),
                    "fact": meta.get("text", "")
                })

            recalled.sort(key=lambda x: x["decay_score"], reverse=True)
            return recalled[:top_k]
        except Exception:
            return []

    @staticmethod
    def load_project_rules(workspace_path: Optional[str] = None) -> List[str]:
        """
        Proje kurallarını (.cursorrules, .aura/rules, .aura/rules.md, project_rules.md) tarar ve yükler.
        """
        from api_server.app.tools.devops import _get_base_workspace
        ws = workspace_path or _get_base_workspace()
        candidate_files = [
            os.path.join(ws, ".cursorrules"),
            os.path.join(ws, ".aura", "rules"),
            os.path.join(ws, ".aura", "rules.md"),
            os.path.join(ws, "project_rules.md")
        ]
        rules = []
        for path in candidate_files:
            if os.path.exists(path) and os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read().strip()
                        if content:
                            rules.append(f"[{os.path.basename(path)}]:\n{content}")
                except Exception:
                    pass
        return rules

    def build_memory_prompt(self, user_query: str) -> str:
        """Kullanıcı profilini, proje kurallarını ve alakalı anıları tek bir prompt bağlamı haline getirir."""
        profile = self.get_profile()
        relevant_memories = self.recall_facts(user_query, top_k=2)
        project_rules = self.load_project_rules()

        prompt_lines = ["\n[KULLANICI PROFİLİ VE KİŞİSEL HAFIZA]"]
        if profile.get("name"):
            prompt_lines.append(f"• Kullanıcı Adı: {profile['name']}")
        if profile.get("os"):
            prompt_lines.append(f"• İşletim Sistemi: {profile['os']}")
        if profile.get("preferred_languages"):
            prompt_lines.append(f"• Tercih Ettiği Diller: {', '.join(profile['preferred_languages'])}")
        if profile.get("tone"):
            prompt_lines.append(f"• Asistan İletişim Tarzı: {profile['tone']}")

        if relevant_memories:
            prompt_lines.append("• Hatırlanan İlgili Geçmiş Bilgiler:")
            for m in relevant_memories:
                prompt_lines.append(f"   - {m['fact']}")

        if project_rules:
            prompt_lines.append("\n[PROJE MİMARİ KURALLARI VE DİREKTİFLER]")
            for r in project_rules:
                prompt_lines.append(r)

        prompt_lines.append("[KİŞİSELLEŞTİRME VE KURALLAR SONU]\n")
        return "\n".join(prompt_lines)


class ContextCompactor:
    """
    Intelligent Sliding-Window Context Compactor.
    Bağlam taşması (Context Overflow) hatalarını engeller:
    1. Mesaj listesinin tahmini token büyüklüğünü denetler.
    2. Eşik değer (%75) aşıldığında eski konuşma turlarını otomatik olarak
       süreç içi Rust HNSW veritabanına arşivler ve bağlamı sıkıştırır.
    """
    def __init__(self, max_context_tokens: int = 4096, compact_threshold: float = 0.75):
        self.max_context_tokens = max_context_tokens
        self.compact_threshold = compact_threshold

    def estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        total_chars = sum(len(m.get("content", "")) for m in messages)
        return int(total_chars / 3.5)

    def compact_if_needed(self, messages: List[Dict[str, str]], keep_last: int = 3) -> Tuple[List[Dict[str, str]], bool]:
        if len(messages) <= keep_last + 1:
            return messages, False

        current_tokens = self.estimate_tokens(messages)
        threshold_tokens = int(self.max_context_tokens * self.compact_threshold)

        if current_tokens < threshold_tokens:
            return messages, False

        older_turns = messages[:-keep_last]
        recent_turns = messages[-keep_last:]

        summary_lines = []
        for m in older_turns:
            role = m.get("role", "unknown")
            content = m.get("content", "").strip()
            if content:
                snippet = content[:150] + ("..." if len(content) > 150 else "")
                summary_lines.append(f"{role}: {snippet}")

        compressed_text = "Önceki Seans Özeti:\n" + "\n".join(summary_lines)

        try:
            memory_service.remember_fact(compressed_text, topic="conversation_archive")
        except Exception:
            pass

        compacted_messages = [
            {"role": "system", "content": f"[ARŞİV BAĞLAMI: {compressed_text}]"}
        ] + recent_turns

        return compacted_messages, True


memory_service = MemoryService()
context_compactor = ContextCompactor()

