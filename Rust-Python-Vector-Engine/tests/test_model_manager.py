import unittest
import sys
import os

# Add project root and api_server to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.services.model_service import model_service
from api_server.app.services.llm_bridge import RustLLMBridge

class TestMultiModelManager(unittest.TestCase):
    def test_hardware_detection(self):
        hw = model_service.get_hardware_info()
        self.assertIn("ram", hw)
        self.assertIn("gpu", hw)
        self.assertIn("recommended_model_id", hw)
        self.assertTrue(hw["recommended_model_id"] in ["qwen2.5-coder-3b", "qwen2.5-coder-7b"])

    def test_model_catalog_profiles(self):
        models = model_service.list_models()
        self.assertEqual(len(models), 2)
        model_ids = [m["id"] for m in models]
        self.assertIn("qwen2.5-coder-7b", model_ids)
        self.assertIn("qwen2.5-coder-3b", model_ids)

        m3b = next(m for m in models if m["id"] == "qwen2.5-coder-3b")
        self.assertEqual(m3b["parameters"], "3.0B")
        self.assertLess(m3b["disk_size_gb"], 3.0)

    def test_dynamic_model_switching(self):
        # Switch to 3B model
        res3 = model_service.set_active_model("qwen2.5-coder-3b")
        self.assertEqual(res3["status"], "success")
        self.assertEqual(model_service.active_model_id, "qwen2.5-coder-3b")
        self.assertTrue("3b" in model_service.get_active_model_path().lower())

        # Check llm_bridge property points to the new model
        bridge = RustLLMBridge()
        self.assertEqual(bridge.model_path, model_service.get_active_model_path())

        # Switch back to 7B model
        res7 = model_service.set_active_model("qwen2.5-coder-7b")
        self.assertEqual(res7["status"], "success")
        self.assertEqual(model_service.active_model_id, "qwen2.5-coder-7b")
        self.assertTrue("7b" in bridge.model_path.lower())

    def test_invalid_model_switch_fails(self):
        with self.assertRaises(ValueError):
            model_service.set_active_model("non_existent_model_100b")

if __name__ == "__main__":
    unittest.main()
