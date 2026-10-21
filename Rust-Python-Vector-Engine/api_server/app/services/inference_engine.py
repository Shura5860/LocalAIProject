import os
import logging
from typing import Optional, Generator
from llama_cpp import Llama
from api_server.app.services.model_service import model_service

logger = logging.getLogger(__name__)

class ProductionInferenceEngine:
    """
    Qwen 2.5 Coder modellerini (3B & 7B) en yüksek hız ve BPE token doğruluğuyla
    çalıştıran profesyonel yerel çıkarım motoru.
    """
    def __init__(self):
        self._llm: Optional[Llama] = None
        self._loaded_model_path: Optional[str] = None

    def _ensure_model_loaded(self) -> Llama:
        current_path = model_service.get_active_model_path()
        if not os.path.exists(current_path):
            raise FileNotFoundError(f"Model dosyası bulunamadı: {current_path}")

        # Eğer zaten bu model yüklüyse yeniden yükleme
        if self._llm is not None and self._loaded_model_path == current_path:
            return self._llm

        logger.info(f"🧠 Model belleğe yükleniyor (On-Demand): {current_path}")
        
        # Donanıma göre optimizasyon: 6 CPU thread'i ve 4096 context window
        self._llm = Llama(
            model_path=current_path,
            n_ctx=4096,
            n_threads=6,
            verbose=False
        )
        self._loaded_model_path = current_path
        return self._llm

    def is_available(self) -> bool:
        current_path = model_service.get_active_model_path()
        return os.path.exists(current_path)

    def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.6) -> str:
        """Tam metin yanıtı üretir."""
        if not self.is_available():
            current_path = model_service.get_active_model_path()
            return f"[Simülasyon Modu]: Model dosyası ({current_path}) bulunamadı."

        llm = self._ensure_model_loaded()
        output = llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["<|im_end|>", "<|endoftext|>", "User:", "Human:"]
        )
        return output["choices"][0]["text"].strip()

    def generate_stream(self, prompt: str, max_tokens: int = 512, temperature: float = 0.6) -> Generator[str, None, None]:
        """Token token canlı akış (Streaming) üretir."""
        if not self.is_available():
            yield "Model dosyası bulunamadı. Lütfen modelin indiğinden emin olun."
            return

        llm = self._ensure_model_loaded()
        stream = llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
            stop=["<|im_end|>", "<|endoftext|>", "User:", "Human:"]
        )
        for chunk in stream:
            token_text = chunk["choices"][0]["text"]
            if token_text:
                yield token_text

production_engine = ProductionInferenceEngine()
