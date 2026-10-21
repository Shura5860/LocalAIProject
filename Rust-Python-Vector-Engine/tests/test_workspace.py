import unittest
import sys
import os

# Add project root and api_server to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.services.workspace_service import workspace_service
from api_server.app.tools.devops import list_files, read_file

class TestWorkspaceHub(unittest.TestCase):
    def setUp(self):
        # Always start unbound
        workspace_service.unbind_workspace()

    def tearDown(self):
        workspace_service.unbind_workspace()

    def test_default_unbound_mode(self):
        status = workspace_service.get_status()
        self.assertFalse(status["is_project_bound"])
        self.assertIsNone(status["project_name"])
        self.assertIn("Genel amaçlı mod aktif", status["message"])

    def test_bind_and_unbind_project(self):
        # Bind the Rust-LLM-Engine subdirectory as a project
        target_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../Rust-LLM-Engine"))
        bind_res = workspace_service.bind_workspace(target_dir)

        self.assertEqual(bind_res["status"], "connected")
        self.assertEqual(bind_res["project_name"], "Rust-LLM-Engine")

        status = workspace_service.get_status()
        self.assertTrue(status["is_project_bound"])
        self.assertEqual(status["project_name"], "Rust-LLM-Engine")

        # Unbind
        unbind_res = workspace_service.unbind_workspace()
        self.assertEqual(unbind_res["status"], "disconnected")
        self.assertFalse(workspace_service.get_status()["is_project_bound"])

    def test_file_tree_generation(self):
        target_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../Rust-LLM-Engine"))
        workspace_service.bind_workspace(target_dir)

        tree = workspace_service.get_file_tree(max_depth=2)
        self.assertIn("tree", tree)
        self.assertEqual(tree["root_name"], "Rust-LLM-Engine")
        self.assertTrue(any(c["name"] == "Cargo.toml" for c in tree["tree"].get("children", [])))

    def test_devops_tools_dynamic_workspace(self):
        # Bind Rust-LLM-Engine and list files
        target_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../Rust-LLM-Engine"))
        workspace_service.bind_workspace(target_dir)

        files = list_files.execute(directory=".")
        self.assertTrue(any("Cargo.toml" in f for f in files))

        # read_file Cargo.toml
        content = read_file.execute(path="Cargo.toml")
        self.assertIn("rust-llm-engine", content)

if __name__ == "__main__":
    unittest.main()
