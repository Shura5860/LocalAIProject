import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.services.inference_engine import production_engine, ProductionInferenceEngine


class TestKVCacheAndCompactor(unittest.TestCase):
    def test_compact_prompt_preserves_system_and_recent_turns(self):
        system_content = "<|im_start|>system\nSen uzman bir yazılım mühendisisin.<|im_end|>"
        turn1 = "<|im_start|>user\n1. Soru: Rust'ta bellek güvenliği nasıl sağlanır?<|im_end|>"
        turn2 = "<|im_start|>assistant\nOwnership ve borrowing kuralları derleme zamanında kontrol edilir.<|im_end|>"
        turn3 = "<|im_start|>user\n2. Soru: C++ ile farkı nedir?<|im_end|>"
        turn4 = "<|im_start|>assistant\nC++ manuel bellek yönetimi kullanır.<|im_end|>"
        turn5 = "<|im_start|>user\n3. Soru: 1 ile 100 arasındaki asal sayıları yaz.<|im_end|>"

        full_prompt = f"{system_content}\n{turn1}\n{turn2}\n{turn3}\n{turn4}\n{turn5}"

        # Sınırı küçük tutarak akıllı sıkıştırmayı tetikle
        compacted = ProductionInferenceEngine._compact_prompt_intelligently(full_prompt, max_chars=300)

        # 1. Sistem talimatı korunmalı
        self.assertIn("Sen uzman bir yazılım mühendisisin", compacted)
        # 2. Arşiv bloğu eklenmeli
        self.assertIn("ARŞİVLENEN GEÇMİŞ BAĞLAM", compacted)
        # 3. Son soru eksiksiz korunmalı
        self.assertIn("3. Soru: 1 ile 100 arasındaki asal sayıları yaz", compacted)

    def test_compact_prompt_no_op_for_short_prompt(self):
        short_prompt = "<|im_start|>system\nTest<|im_end|>\n<|im_start|>user\nMerhaba<|im_end|>"
        res = ProductionInferenceEngine._compact_prompt_intelligently(short_prompt, max_chars=1000)
        self.assertEqual(res, short_prompt)

    def test_engine_stats_structure(self):
        stats = production_engine.get_stats()
        self.assertIn("loaded_model", stats)
        self.assertIn("ctx_size", stats)
        self.assertIn("cache_enabled", stats)
        self.assertIn("gpu_layers", stats)
        self.assertIn("threads", stats)


if __name__ == "__main__":
    unittest.main()

