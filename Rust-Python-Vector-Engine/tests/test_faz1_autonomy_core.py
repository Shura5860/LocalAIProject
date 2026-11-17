import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.tools.registry import tool_registry
from api_server.app.services.react_agent_service import react_agent_service, ReActAgentService


class TestFaz1AutonomyCore(unittest.TestCase):
    def test_semantic_tool_pruning_math(self):
        query = "10 ile 25 sayısını çarp ve hesapla"
        tools = tool_registry.get_relevant_tools(query, top_k=5)
        tool_names = [t.name for t in tools]
        self.assertIn("calculator", tool_names)
        self.assertLessEqual(len(tools), 5)

    def test_semantic_tool_pruning_web(self):
        query = "internette ve webde son yapay zeka haberlerini ara"
        tools = tool_registry.get_relevant_tools(query, top_k=5)
        tool_names = [t.name for t in tools]
        self.assertTrue("web_search" in tool_names or "read_web_page" in tool_names)

    def test_semantic_tool_pruning_git(self):
        query = "git status ve git diff çıktısını incele"
        tools = tool_registry.get_relevant_tools(query, top_k=5)
        tool_names = [t.name for t in tools]
        self.assertTrue("git_status" in tool_names or "git_diff" in tool_names)

    def test_semantic_tool_pruning_preserves_pinned(self):
        query = "Herhangi rastgele bir soru"
        tools = tool_registry.get_relevant_tools(query, top_k=5)
        tool_names = [t.name for t in tools]
        # Pinned core tools must be included
        self.assertIn("read_file", tool_names)

    def test_hallucination_guard_catches_fake_file(self):
        fake_path = "hayali_olmayan_dosya_12345.rs"
        is_valid, msg = ReActAgentService.validate_action_against_hallucination(
            "read_file",
            {"path": fake_path}
        )
        self.assertFalse(is_valid)
        self.assertIn("Halüsinasyon Kalkanı", msg)
        self.assertIn("dosyası bulunamadı", msg)

    def test_hallucination_guard_allows_real_file(self):
        real_path = "README.md"
        is_valid, msg = ReActAgentService.validate_action_against_hallucination(
            "read_file",
            {"path": real_path}
        )
        self.assertTrue(is_valid)
        self.assertIsNone(msg)

    def test_tree_of_thoughts_empty_thought_grounding(self):
        grounded = ReActAgentService.evaluate_thought_candidates("Rust kodunu düzelt", "")
        self.assertIn("Rust kodunu düzelt", grounded)
        self.assertGreaterEqual(len(grounded), 10)


if __name__ == "__main__":
    unittest.main()

