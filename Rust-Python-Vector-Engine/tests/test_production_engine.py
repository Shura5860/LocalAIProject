import unittest
import sys
import os

# Add project root and api_server to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.services.inference_engine import production_engine
from api_server.app.services.model_service import model_service
from api_server.app.services.llm_bridge import RustLLMBridge

class TestProductionEngine(unittest.TestCase):
    def setUp(self):
        if not production_engine.is_available():
            self.skipTest("Production engine veya model ağırlıkları mevcut değil (CI ortamı).")

    def test_production_engine_availability(self):
        self.assertTrue(production_engine.is_available())

    def test_production_generation_turkish(self):
        # Qwen 2.5 3B model is downloaded and active
        model_service.set_active_model("qwen2.5-coder-3b")
        prompt = (
            "<|im_start|>system\n"
            "Sen yardımsever bir Türkçe yapay zeka asistanısın.<|im_end|>\n"
            "<|im_start|>user\n"
            "Türkiye'nin başkenti neresidir? Tek kelimeyle cevap ver.<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
        answer = production_engine.generate(prompt=prompt, max_tokens=20)
        self.assertIsInstance(answer, str)
        self.assertGreater(len(answer), 2)
        self.assertIn("Ankara", answer)

    def test_streaming_generation(self):
        model_service.set_active_model("qwen2.5-coder-3b")
        prompt = (
            "<|im_start|>system\n"
            "Sen bir kodlama asistanısın.<|im_end|>\n"
            "<|im_start|>user\n"
            "Python'da print('test') ne yapar?<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
        stream = production_engine.generate_stream(prompt=prompt, max_tokens=25)
        tokens = []
        for token in stream:
            tokens.append(token)
            if len(tokens) >= 5:
                break
        self.assertGreaterEqual(len(tokens), 5)
        full_text = "".join(tokens)
        self.assertIsInstance(full_text, str)

    def test_llm_bridge_uses_production_engine(self):
        bridge = RustLLMBridge()
        # Direct call to bridge
        res = bridge.generate("Python nedir? Kısaca açıkla.", max_tokens=30)
        self.assertIsInstance(res, str)
        self.assertGreater(len(res), 5)
        # Should NOT return simulation error since models are downloaded!
        self.assertNotIn("Model dosyası bulunamadı", res)

if __name__ == "__main__":
    unittest.main()
