import os
import logging
import threading
from typing import Optional, Generator, Dict, Any
try:
    from llama_cpp import Llama, LlamaRAMCache
except ImportError:
    Llama = None
    LlamaRAMCache = None

from api_server.app.services.model_service import model_service

JSON_GBNF_GRAMMAR = r'''
root ::= object
value ::= object | array | string | number | "true" | "false" | "null"
object ::= "{" ws (entry ("," ws entry)*)? ws "}"
entry ::= string ws ":" ws value
array ::= "[" ws (value ("," ws value)*)? ws "]"
string ::= "\"" ([^"\\] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]))* "\""
number ::= "-"? [0-9]+ ("." [0-9]+)? ([eE] [-+]? [0-9]+)?
ws ::= [ \t\n\r]*
'''

logger = logging.getLogger(__name__)

class ProductionInferenceEngine:
    """
    Qwen 2.5 Coder modellerini (3B & 7B) en yüksek hız ve BPE token doğruluğuyla
    çalıştıran profesyonel yerel çıkarım motoru.
    """
    def __init__(self):
        self._llm: Optional[Llama] = None
        self._loaded_model_path: Optional[str] = None
        self._lock = threading.Lock()
        self._ctx_size: int = 2048

    @staticmethod
    def _truncate_prompt_sliding(prompt: str, max_chars: int = 6000) -> str:
        """Bağlam penceresi aşıldığında başlangıç sistem talimatını ve son kullanıcı sorusunu koruyarak kırpar (Fallback)."""
        if len(prompt) <= max_chars:
            return prompt
        head = prompt[: int(max_chars * 0.35)]
        tail = prompt[-int(max_chars * 0.60) :]
        return f"{head}\n...[BAĞLAM OTOMATİK KIRPILDI]...\n{tail}"

    @classmethod
    def _compact_prompt_intelligently(cls, prompt: str, max_chars: int = 5000) -> str:
        """
        ChatML ve ReAct şemalarını koruyarak akıllı bağlam sıkıştırması yapar.
        1. <|im_start|>system...<|im_end|> bloğunu (araç ve sistem talimatları) ASLA kesmez.
        2. Son kullanıcı sorusunu ve son asistan mesajını eksiksiz korur.
        3. Aradaki eski turları özetleyip süreç içi Rust HNSW hafızasına arşivler.
        """
        if len(prompt) <= max_chars:
            return prompt

        import re
        # ChatML bloklarını ayıkla: <|im_start|>(role)\n(content)<|im_end|>
        blocks = re.findall(r"(<\|im_start\|>(system|user|assistant|tool)[\s\S]*?<\|im_end\|>)", prompt)
        if not blocks or len(blocks) < 3:
            return cls._truncate_prompt_sliding(prompt, max_chars=max_chars)

        system_block = ""
        conversation_turns = []
        for full_block, role in blocks:
            if role == "system" and not system_block:
                system_block = full_block
            else:
                conversation_turns.append((role, full_block))

        if len(conversation_turns) <= 2:
            return cls._truncate_prompt_sliding(prompt, max_chars=max_chars)

        # Son 2 turu (kullanıcının son sorusu ve son yanıt) mutlaka eksiksiz koru
        recent_turns = conversation_turns[-2:]
        older_turns = conversation_turns[:-2]

        summary_snippets = []
        for role, block in older_turns:
            clean = block.replace("<|im_start|>", "").replace("<|im_end|>", "").strip()
            snippet = clean[:140] + ("..." if len(clean) > 140 else "")
            summary_snippets.append(f"• {snippet}")

        compressed_text = "Önceki Turlar Özeti:\n" + "\n".join(summary_snippets)

        # Rust HNSW hafızasına arka planda arşivle
        try:
            from api_server.app.services.memory_service import memory_service
            memory_service.remember_fact(compressed_text, topic="context_compaction_archive")
        except Exception:
            pass

        archive_block = f"<|im_start|>system\n[ARŞİVLENEN GEÇMİŞ BAĞLAM]\n{compressed_text}\n[ARŞİV SONU]<|im_end|>"
        recent_blocks_str = "\n".join(b[1] for b in recent_turns)

        return f"{system_block}\n{archive_block}\n{recent_blocks_str}"

    def _ensure_model_loaded(self) -> Llama:
        current_path = model_service.get_active_model_path()
        if not os.path.exists(current_path):
            raise FileNotFoundError(f"Model dosyası bulunamadı: {current_path}")

        # Eğer zaten bu model yüklüyse yeniden yükleme
        if self._llm is not None and self._loaded_model_path == current_path:
            return self._llm

        logger.info(f"🧠 Model belleğe yükleniyor (On-Demand): {current_path}")
        
        # Donanıma göre optimizasyon: Kullanıcı arayüzünü dondurmamak için çekirdek marjı bırakılır
        cpu_count = os.cpu_count() or 4
        safe_threads = int(os.environ.get("LLAMA_THREADS", max(1, min(4, cpu_count - 2))))

        # Akıllı GPU / VRAM Algılama ve Otomatik Katmanlama (CUDA, Metal, CPU)
        from api_server.app.core.platform_hal import platform_hal
        hal_hw = platform_hal.get_hardware_profile()
        backend = hal_hw.get("gpu_backend", "cpu")
        free_vram = hal_hw.get("vram_free_gb", 0.0)

        # KV-Cache Quantization (Q8_0 ile VRAM yarıya düşürülür, uzun bağlam sağlanır)
        kv_type = int(os.environ.get("LLAMA_KV_CACHE_TYPE", "2"))  # 2: q8_0

        if "LLAMA_CTX" in os.environ:
            ctx_size = int(os.environ["LLAMA_CTX"])
        elif backend in ("metal", "cuda") and free_vram >= 5.5:
            ctx_size = 8192  # Q8_0 KV-cache ile 8K context penceresi
        else:
            ctx_size = 2048

        if "LLAMA_GPU_LAYERS" in os.environ:
            n_gpu_layers = int(os.environ["LLAMA_GPU_LAYERS"])
        else:
            n_gpu_layers = platform_hal.get_optimal_gpu_layers()

        if n_gpu_layers == -1:
            logger.info(f"⚡ {backend.upper()} Hızlandırma ({hal_hw.get('gpu_name')}, {free_vram} GB VRAM). Tüm katmanlar GPU'da.")
        elif n_gpu_layers > 0:
            logger.info(f"⚡ Hibrit GPU Hızlandırma: {n_gpu_layers} katman VRAM'e aktarılıyor.")
        else:
            logger.info("ℹ️ CPU AVX2 SIMD motoru devrede.")
            platform_hal.bind_cpu_affinity(num_cores=safe_threads)

        try:
            self._llm = Llama(
                model_path=current_path,
                n_ctx=ctx_size,
                n_threads=safe_threads,
                n_gpu_layers=n_gpu_layers,
                type_k=kv_type,
                type_v=kv_type,
                verbose=False
            )
        except Exception as e:
            logger.warning(f"GPU katmanlama başlatılamadı ({e}), güvenli CPU moduna dönülüyor.")
            self._llm = Llama(
                model_path=current_path,
                n_ctx=ctx_size,
                n_threads=safe_threads,
                n_gpu_layers=0,
                verbose=False
            )

        # LlamaRAMCache ile Stateful KV Prefix Caching entegrasyonu (Ortak Prompt Prefix Hızlandırması)
        cache_size_mb = int(os.environ.get("LLAMA_CACHE_MB", "512"))
        if LlamaRAMCache is not None:
            try:
                ram_cache = LlamaRAMCache(capacity_bytes=cache_size_mb * 1024 * 1024)
                self._llm.set_cache(ram_cache)
                logger.info(f"⚡ [KV Cache] LlamaRAMCache devrede ({cache_size_mb} MB). Ortak sistem/araç şemaları anında yeniden kullanılacak.")
            except Exception as ce:
                logger.warning(f"LlamaRAMCache eklenemedi: {ce}")

        self._loaded_model_path = current_path
        self._ctx_size = ctx_size
        return self._llm

    def is_available(self) -> bool:
        if os.environ.get("MOCK_INFERENCE", "0") == "1" or os.environ.get("TESTING", "0") == "1":
            return False
        if Llama is None:
            return False
        current_path = model_service.get_active_model_path()
        return os.path.exists(current_path)

    def get_stats(self) -> Dict[str, Any]:
        """Çıkarım motorunun anlık KV cache, context penceresi ve donanım istatistiklerini döner."""
        return {
            "loaded_model": self._loaded_model_path,
            "ctx_size": self._ctx_size,
            "cache_enabled": self._llm is not None and getattr(self._llm, "cache", None) is not None,
            "gpu_layers": getattr(self._llm, "n_gpu_layers", 0) if self._llm else 0,
            "threads": getattr(self._llm, "n_threads", 0) if self._llm else 0
        }

    def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.6) -> str:
        """Tam metin yanıtı üretir (Thread-safe ve Context Overflow korumalı)."""
        if not self.is_available():
            current_path = model_service.get_active_model_path()
            return f"[Simülasyon Modu]: Model dosyası ({current_path}) bulunamadı."

        with self._lock:
            llm = self._ensure_model_loaded()
            try:
                output = llm(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stop=["<|im_end|>", "<|endoftext|>", "<|eot_id|>", "User:", "Human:"]
                )
            except ValueError as e:
                logger.warning(f"Bağlam sınırı aşıldı ({e}), akıllı sıkıştırma uygulanıyor...")
                safe_prompt = self._compact_prompt_intelligently(prompt, max_chars=4500)
                output = llm(
                    safe_prompt,
                    max_tokens=min(max_tokens, 256),
                    temperature=temperature,
                    stop=["<|im_end|>", "<|endoftext|>", "<|eot_id|>", "User:", "Human:"]
                )
            return output["choices"][0]["text"].strip()

    def generate_structured(self, prompt: str, grammar_type: str = "json", max_tokens: int = 512, temperature: float = 0.2) -> str:
        """
        GBNF (GGML BNF) gramer kısıtlamalı deterministik çıkarım yapar.
        Modelin belirlenen şema (örn. %100 geçerli JSON) dışında tek bir karakter dahi
        üretmesi token örnekleme seviyesinde kısıtlanır.
        """
        if not self.is_available():
            current_path = model_service.get_active_model_path()
            return f'{{"error": "Model ({current_path}) bulunamadı."}}'

        with self._lock:
            llm = self._ensure_model_loaded()
            kwargs = {
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stop": ["<|im_end|>", "<|endoftext|>", "<|eot_id|>"]
            }

            if grammar_type == "json":
                try:
                    from llama_cpp import LlamaGrammar
                    kwargs["grammar"] = LlamaGrammar.from_string(JSON_GBNF_GRAMMAR)
                except Exception as e:
                    logger.warning(f"GBNF gramer uygulanamadı: {e}")

            try:
                output = llm(prompt, **kwargs)
            except ValueError:
                safe_prompt = self._compact_prompt_intelligently(prompt, max_chars=4500)
                output = llm(safe_prompt, **kwargs)
            return output["choices"][0]["text"].strip()

    def generate_stream(self, prompt: str, max_tokens: int = 512, temperature: float = 0.6) -> Generator[str, None, None]:
        """Token token canlı akış (Streaming) üretir (Thread-safe)."""
        if not self.is_available():
            yield "Model dosyası bulunamadı. Lütfen modelin indiğinden emin olun."
            return

        with self._lock:
            llm = self._ensure_model_loaded()
            try:
                stream = llm(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=True,
                    stop=["<|im_end|>", "<|endoftext|>", "<|eot_id|>", "User:", "Human:"]
                )
                for chunk in stream:
                    token_text = chunk["choices"][0]["text"]
                    if token_text:
                        yield token_text
            except ValueError:
                safe_prompt = self._compact_prompt_intelligently(prompt, max_chars=4500)
                stream = llm(
                    safe_prompt,
                    max_tokens=min(max_tokens, 256),
                    temperature=temperature,
                    stream=True,
                    stop=["<|im_end|>", "<|endoftext|>", "<|eot_id|>", "User:", "Human:"]
                )
                for chunk in stream:
                    token_text = chunk["choices"][0]["text"]
                    if token_text:
                        yield token_text

production_engine = ProductionInferenceEngine()
