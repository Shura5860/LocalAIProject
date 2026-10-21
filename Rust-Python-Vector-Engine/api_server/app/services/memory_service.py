import os
import json
import numpy as np
import logging
from typing import Dict, Any, List, Optional, Tuple
from sentence_transformers import SentenceTransformer
from api_server.app.core.config import db

logger = logging.getLogger(__name__)

PROFILE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../user_profile.json"))

class MemoryService:
    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.embedding_model_name = model_name
        self._embedder: Optional[SentenceTransformer] = None
        self._ensure_profile_exists()

    @property
    def embedder(self) -> SentenceTransformer:
        if self._embedder is None:
            self._embedder = SentenceTransformer(self.embedding_model_name)
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

    def remember_fact(self, fact: str, topic: str = "personal") -> Dict[str, Any]:
        """Kullanıcı hakkındaki önemli bir anıyı veya bilgiyi Rust HNSW vektör indeksine kalıcı olarak işler."""
        if not fact.strip():
            return {"status": "error", "message": "Boş bilgi kaydedilemez."}

        is_safe, msg = self.sanitize_memory_fact(fact)
        if not is_safe:
            logger.warning(f"🛡️ [AI Security] Hafıza zehirleme girişimi engellendi: {fact}")
            return {"status": "error", "message": msg}

        embeddings = self.embedder.encode([fact], convert_to_numpy=True).astype(np.float32)
        doc_id = db.len()
        meta = {
            "text": fact,
            "category": "user_memory",
            "topic": topic
        }

        db.add_batch_with_metadata([doc_id], embeddings, [meta])
        db.build_hnsw_index()
        return {"status": "success", "id": doc_id, "fact": fact}

    def recall_facts(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Soruyla veya durumla ilgili geçmiş anıları HNSW üzerinden çeker."""
        if db.len() == 0:
            return []

        query_vec = self.embedder.encode(query, convert_to_numpy=True).astype(np.float32)
        try:
            results = db.search_filtered(
                query_vec,
                top_k=top_k,
                filter_key="category",
                filter_value="user_memory",
                operator="=="
            )
            recalled = []
            for doc_id, dist, meta in results:
                recalled.append({
                    "id": doc_id,
                    "distance": float(dist),
                    "fact": meta.get("text", "")
                })
            return recalled
        except Exception:
            return []

    def build_memory_prompt(self, user_query: str) -> str:
        """Kullanıcı profilini ve alakalı anıları tek bir prompt bağlamı haline getirir."""
        profile = self.get_profile()
        relevant_memories = self.recall_facts(user_query, top_k=2)

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

        prompt_lines.append("[KİŞİSELLEŞTİRME SONU]\n")
        return "\n".join(prompt_lines)

memory_service = MemoryService()
