import sys
import os
import unittest
import tempfile
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.tools.devops import apply_multi_diff, apply_diff, _validate_safe_path, _get_base_workspace
from api_server.app.services.rag_service import rag_service


class TestMultiDiffAndRepoMap(unittest.TestCase):
    def setUp(self):
        self.file1 = _validate_safe_path("temp_multidiff_module_a.py")
        self.file2 = _validate_safe_path("temp_multidiff_module_b.py")

        with open(self.file1, "w", encoding="utf-8") as f:
            f.write("def calculate_tax(amount):\n    return amount * 0.18\n")

        with open(self.file2, "w", encoding="utf-8") as f:
            f.write("from module_a import calculate_tax\n\ndef get_total(price):\n    return price + calculate_tax(price)\n")

    def tearDown(self):
        for f in [self.file1, self.file1 + ".bak", self.file2, self.file2 + ".bak"]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    def test_apply_multi_diff_atomic_success(self):
        edits = [
            {
                "path": self.file1,
                "search": "return amount * 0.18",
                "replace": "return amount * 0.20"
            },
            {
                "path": self.file2,
                "search": "def get_total(price):",
                "replace": "def get_total_with_tax(price):"
            }
        ]
        res = apply_multi_diff.execute(edits=edits)
        self.assertIn("Atomik çoklu yama başarıyla uygulandı", res)

        with open(self.file1, "r", encoding="utf-8") as f:
            c1 = f.read()
            self.assertIn("0.20", c1)

        with open(self.file2, "r", encoding="utf-8") as f:
            c2 = f.read()
            self.assertIn("def get_total_with_tax", c2)

    def test_apply_multi_diff_atomic_rollback_on_failure(self):
        # file2 has a bad search block
        edits = [
            {
                "path": self.file1,
                "search": "return amount * 0.18",
                "replace": "return amount * 0.99"
            },
            {
                "path": self.file2,
                "search": "BU_SATIR_DOSYADA_YOK",
                "replace": "yenisi"
            }
        ]
        res = apply_multi_diff.execute(edits=edits)
        self.assertIn("Hata:", res)

        # File 1 must NOT be touched! (Zero partial corruption)
        with open(self.file1, "r", encoding="utf-8") as f:
            c1 = f.read()
            self.assertIn("0.18", c1)
            self.assertNotIn("0.99", c1)

    def test_generate_repo_map(self):
        repo_map = rag_service.generate_repo_map(workspace_path=_get_base_workspace())
        self.assertIn("PROJE MİMARİ HARİTASI", repo_map)
        self.assertIn("temp_multidiff_module_a.py", repo_map)
        self.assertIn("def calculate_tax", repo_map)


if __name__ == "__main__":
    unittest.main()
