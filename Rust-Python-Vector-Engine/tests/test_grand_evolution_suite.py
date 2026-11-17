import sys
import os
import unittest
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.tools.devops import apply_diff
from api_server.app.services.rag_service import RagService
from api_server.app.services.memory_service import MemoryService, memory_service
from api_server.app.core.platform_hal import PlatformHAL
from api_server.app.services.react_agent_service import ReActAgentService


class TestGrandEvolutionSuite(unittest.TestCase):
    def setUp(self):
        self.scratch_dir = os.path.join(os.path.dirname(__file__), "test_scratch")
        os.makedirs(self.scratch_dir, exist_ok=True)

    def tearDown(self):
        import shutil
        if os.path.exists(self.scratch_dir):
            shutil.rmtree(self.scratch_dir, ignore_errors=True)

    def test_fuzzy_diff_matching(self):
        test_file = os.path.join(self.scratch_dir, "sample.py")
        original_code = "def calculate():\n    x = 10\n    y = 20\n    return x + y\n"
        with open(test_file, "w") as f:
            f.write(original_code)

        # Farklı girintili / hafif boşluk farkı olan arama bloğu (Fuzzy Match testi)
        search_block = "x = 10\n  y = 20"
        replace_block = "x = 100\n    y = 200"

        res = apply_diff.execute(path=test_file, search_block=search_block, replace_block=replace_block)
        self.assertIn("Yama başarıyla uygulandı", res)

        with open(test_file, "r") as f:
            updated = f.read()
        self.assertIn("x = 100", updated)
        self.assertIn("y = 200", updated)

    def test_ast_call_graph_extraction(self):
        code = """
def init():
    setup_db()
    load_cache()

def setup_db():
    connect()

def main():
    init()
"""
        graph = RagService.extract_call_graph(code, "test.py")
        self.assertIn("init", graph)
        self.assertIn("setup_db", graph["init"])
        self.assertIn("load_cache", graph["init"])
        self.assertIn("main", graph)
        self.assertIn("init", graph["main"])

    def test_project_rules_loading(self):
        rules_file = os.path.join(self.scratch_dir, ".cursorrules")
        with open(rules_file, "w") as f:
            f.write("Bu projede daima Tokio ve Result kullanılmalıdır.")

        rules = MemoryService.load_project_rules(self.scratch_dir)
        self.assertEqual(len(rules), 1)
        self.assertIn("Tokio ve Result", rules[0])

    def test_cpu_affinity_binding(self):
        # Platform Linux ise CPU affinity çağrısı True döner veya exception fırlatmaz
        res = PlatformHAL.bind_cpu_affinity(num_cores=2)
        if PlatformHAL.get_os_type() == "linux" and hasattr(os, "sched_setaffinity"):
            self.assertTrue(res)

    def test_flight_recorder_trace_export(self):
        trace_data = [
            {"step": 1, "thought": "Analiz yapıldı.", "action": "test", "observation": "OK"}
        ]
        exported_path = ReActAgentService.export_flight_recorder_trace(
            query="Test trace sorgusu",
            trace_data=trace_data,
            final_answer="Tamamlandı",
            status="COMPLETED"
        )
        self.assertIsNotNone(exported_path)
        self.assertTrue(os.path.exists(exported_path))
        self.assertTrue(exported_path.endswith(".auratrace.json"))
        # Temizlik
        try:
            os.remove(exported_path)
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
