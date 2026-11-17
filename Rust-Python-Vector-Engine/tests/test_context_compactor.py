import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.services.memory_service import context_compactor, ContextCompactor


class TestContextCompactor(unittest.TestCase):
    def test_short_context_not_compacted(self):
        compactor = ContextCompactor(max_context_tokens=1000, compact_threshold=0.75)
        msgs = [
            {"role": "user", "content": "Merhaba!"},
            {"role": "assistant", "content": "Size nasıl yardımcı olabilirim?"}
        ]
        res, was_compacted = compactor.compact_if_needed(msgs, keep_last=1)
        self.assertFalse(was_compacted)
        self.assertEqual(len(res), 2)

    def test_large_context_triggers_compaction(self):
        # Create a small compactor threshold to trigger compaction easily
        compactor = ContextCompactor(max_context_tokens=100, compact_threshold=0.50)
        msgs = [
            {"role": "user", "content": "İlk soru: Rust bellek yönetimi nasıldır?" * 5},
            {"role": "assistant", "content": "Rust ownership ve borrow checker ile çalışır." * 5},
            {"role": "user", "content": "İkinci soru: Python GIL nedir?" * 5},
            {"role": "assistant", "content": "GIL tek thread garantisi sağlar." * 5},
            {"role": "user", "content": "Son soru: Bunları karşılaştır."}
        ]
        res, was_compacted = compactor.compact_if_needed(msgs, keep_last=2)
        self.assertTrue(was_compacted)
        # Should contain [ARŞİV BAĞLAMI: ...] + keep_last turns
        self.assertEqual(len(res), 3)
        self.assertIn("ARŞİV BAĞLAMI", res[0]["content"])
        self.assertEqual(res[-1]["content"], "Son soru: Bunları karşılaştır.")


if __name__ == "__main__":
    unittest.main()

