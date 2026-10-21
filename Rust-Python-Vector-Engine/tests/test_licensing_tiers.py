import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.core.licensing import license_manager, TIER_CONFIG

class TestLicensingTiers(unittest.TestCase):
    def setUp(self):
        self.hw_id = license_manager.get_hardware_fingerprint()

    def test_hardware_id_format(self):
        self.assertEqual(len(self.hw_id), 19)
        self.assertEqual(len(self.hw_id.split("-")), 4)

    def test_trial_tier(self):
        key = license_manager.generate_license_key(self.hw_id, tier="TRIAL")
        self.assertTrue(key.startswith("TRIAL-"))
        valid, msg, info = license_manager.verify_license(key, self.hw_id)
        self.assertTrue(valid, msg)
        self.assertEqual(info["tier"], "TRIAL")
        self.assertLessEqual(info["days_left"], 7)
        self.assertGreaterEqual(info["days_left"], 6)

    def test_month_tier(self):
        key = license_manager.generate_license_key(self.hw_id, tier="MONTH")
        self.assertTrue(key.startswith("MONTH-"))
        valid, msg, info = license_manager.verify_license(key, self.hw_id)
        self.assertTrue(valid, msg)
        self.assertEqual(info["tier"], "MONTH")
        self.assertGreaterEqual(info["days_left"], 29)

    def test_year_tier(self):
        key = license_manager.generate_license_key(self.hw_id, tier="YEAR1")
        self.assertTrue(key.startswith("YEAR1-"))
        valid, msg, info = license_manager.verify_license(key, self.hw_id)
        self.assertTrue(valid, msg)
        self.assertEqual(info["tier"], "YEAR1")
        self.assertGreaterEqual(info["days_left"], 364)

    def test_lifetime_tier(self):
        key = license_manager.generate_license_key(self.hw_id, tier="LIFET")
        self.assertTrue(key.startswith("LIFET-"))
        self.assertIn("PERPETUA", key)
        valid, msg, info = license_manager.verify_license(key, self.hw_id)
        self.assertTrue(valid, msg)
        self.assertTrue(info["is_lifetime"])

    def test_tampered_signature_rejected(self):
        key = license_manager.generate_license_key(self.hw_id, tier="YEAR1")
        tampered_key = key[:-4] + "FFFF"
        valid, msg, info = license_manager.verify_license(tampered_key, self.hw_id)
        self.assertFalse(valid)
        self.assertIn("tahrif", msg.lower())

    def test_wrong_hardware_rejected(self):
        fake_hw = "AAAA-BBBB-CCCC-DDDD"
        key = license_manager.generate_license_key(fake_hw, tier="YEAR1")
        valid, msg, info = license_manager.verify_license(key, self.hw_id)
        self.assertFalse(valid)
        self.assertIn("donanım", msg.lower())

if __name__ == "__main__":
    unittest.main()
