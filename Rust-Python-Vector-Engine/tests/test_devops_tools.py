import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.tools.registry import tool_registry
from api_server.app.tools.devops import _validate_safe_path

TEMP_TEST_FILE = "temp_apply_diff_test.txt"


class TestDevOpsTools(unittest.TestCase):
    def tearDown(self):
        full_temp = _validate_safe_path(TEMP_TEST_FILE)
        for f in [full_temp, full_temp + ".bak"]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    def test_file_tools(self):
        list_tool = tool_registry.get_tool("list_files")
        self.assertIsNotNone(list_tool)
        files = list_tool.execute(directory=".")
        self.assertTrue(any("Rust-LLM-Engine" in f for f in files))

        read_tool = tool_registry.get_tool("read_file")
        self.assertIsNotNone(read_tool)
        cargo_content = read_tool.execute(path="Rust-LLM-Engine/Cargo.toml")
        self.assertIn("rust-llm-engine", cargo_content)

    def test_apply_diff_surgical_replacement(self):
        # 1. Test dosyası oluştur
        write_tool = tool_registry.get_tool("write_file")
        content = "fn main() {\n    let old_value = 100;\n    println!(\"{}\", old_value);\n}\n"
        write_tool.execute(path=TEMP_TEST_FILE, content=content)

        # 2. Cerrahi yama uygula
        diff_tool = tool_registry.get_tool("apply_diff")
        self.assertIsNotNone(diff_tool)
        res = diff_tool.execute(
            path=TEMP_TEST_FILE,
            search_block="    let old_value = 100;\n    println!(\"{}\", old_value);",
            replace_block="    let new_value = 999;\n    println!(\"Updated: {}\", new_value);"
        )
        self.assertIn("Yama başarıyla uygulandı", res)

        # 3. İçeriği doğrula
        read_tool = tool_registry.get_tool("read_file")
        updated = read_tool.execute(path=TEMP_TEST_FILE)
        self.assertIn("let new_value = 999;", updated)
        self.assertNotIn("old_value", updated)
        # Otomatik .bak kontrolü
        full_temp = _validate_safe_path(TEMP_TEST_FILE)
        self.assertTrue(os.path.exists(full_temp + ".bak"))

    def test_git_checkpoint_tool(self):
        checkpoint_tool = tool_registry.get_tool("git_checkpoint")
        self.assertIsNotNone(checkpoint_tool)
        res = checkpoint_tool.execute(action="create")
        self.assertIn("Kurtarma noktası oluşturuldu", res)

    def test_path_traversal_security(self):
        read_tool = tool_registry.get_tool("read_file")
        sec_res = read_tool.execute(path="/etc/passwd")
        self.assertIn("Güvenlik İhlali", sec_res)

    def test_git_status_tool(self):
        git_status_tool = tool_registry.get_tool("git_status")
        self.assertIsNotNone(git_status_tool)
        status_out = git_status_tool.execute()
        self.assertIsInstance(status_out, str)


if __name__ == "__main__":
    unittest.main()
