import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.core.platform_hal import platform_hal


class TestPlatformHAL(unittest.TestCase):
    def test_os_detection(self):
        os_type = platform_hal.get_os_type()
        self.assertIn(os_type, ["linux", "darwin", "windows"])

    def test_hardware_profile_structure(self):
        profile = platform_hal.get_hardware_profile()
        self.assertIsInstance(profile, dict)
        self.assertIn("os", profile)
        self.assertIn("architecture", profile)
        self.assertIn("gpu_backend", profile)
        self.assertIn("gpu_name", profile)
        self.assertIn("vram_free_gb", profile)
        self.assertIn("has_sandboxing", profile)
        self.assertIn("sandbox_type", profile)

    def test_optimal_gpu_layers(self):
        layers = platform_hal.get_optimal_gpu_layers()
        self.assertIn(layers, [-1, 20, 0])

    def test_sandboxed_execution(self):
        res = platform_hal.execute_sandboxed_command("echo HAL_SANDBOX_ACTIVE", cwd=".")
        self.assertEqual(res.returncode, 0)
        self.assertIn("HAL_SANDBOX_ACTIVE", res.stdout)


if __name__ == "__main__":
    unittest.main()

