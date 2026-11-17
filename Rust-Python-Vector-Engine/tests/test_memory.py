import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.services.memory_service import memory_service


class TestMemorySystem(unittest.TestCase):
    def test_user_profile(self):
        profile = memory_service.get_profile()
        self.assertEqual(profile.get("name"), "Shura")

        updated = memory_service.update_profile({"favorite_editor": "Neovim & Antigravity IDE"})
        self.assertEqual(updated.get("favorite_editor"), "Neovim & Antigravity IDE")

    def test_episodic_memory(self):
        fact1 = "Ben kahvemi daima sütsüz ve şekersiz içerim."
        fact2 = "Projelerimde asenkron mimari ve SIMD donanım optimizasyonu kullanırım."

        res1 = memory_service.remember_fact(fact1, topic="habits")
        res2 = memory_service.remember_fact(fact2, topic="tech")
        self.assertEqual(res1["status"], "success")

        recalled = memory_service.recall_facts("Kahve nasıl hazırlanmalı?", top_k=1)
        self.assertGreaterEqual(len(recalled), 1)
        self.assertIn("sütsüz", recalled[0]["fact"])

        prompt_ctx = memory_service.build_memory_prompt("Bana kahve öner")
        self.assertIn("Shura", prompt_ctx)
        self.assertIn("sütsüz", prompt_ctx)


if __name__ == "__main__":
    unittest.main()
