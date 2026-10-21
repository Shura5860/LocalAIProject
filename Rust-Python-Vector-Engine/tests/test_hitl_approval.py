import unittest
import sys
import os
import json

# Add project root and api_server to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.core.guardrails import is_approval_required, record_audit_log, AUDIT_LOG_FILE
from api_server.app.services.react_agent_service import react_agent_service

class TestHITLApproval(unittest.TestCase):
    def test_critical_tools_classification(self):
        # Read-only tools should NOT require approval
        self.assertFalse(is_approval_required("read_file"))
        self.assertFalse(is_approval_required("list_files"))
        self.assertFalse(is_approval_required("calculator"))
        self.assertFalse(is_approval_required("system_info"))
        self.assertFalse(is_approval_required("web_search"))
        self.assertFalse(is_approval_required("read_web_page"))

        # Destructive/Mutating tools MUST require approval
        self.assertTrue(is_approval_required("write_file"))
        self.assertTrue(is_approval_required("run_terminal_command"))

    def test_react_agent_pause_on_critical_action(self):
        # A query requesting terminal command with require_approval=True
        q = "cargo check komutunu çalıştır"
        res = react_agent_service.run(user_query=q, max_steps=2, require_approval=True)

        self.assertEqual(res["status"], "WAITING_APPROVAL")
        self.assertIsNotNone(res["pending_action"])
        self.assertEqual(res["pending_action"]["tool"], "run_terminal_command")
        action_id = res["pending_action"]["action_id"]

        # Action is held in pending_actions
        self.assertIn(action_id, react_agent_service.pending_actions)

        # 1. Test Rejection
        reject_res = react_agent_service.execute_decision(
            action_id=action_id,
            approved=False,
            rejection_reason="Test amaçlı kullanıcı reddi"
        )
        self.assertEqual(reject_res["status"], "CANCELLED")
        self.assertNotIn(action_id, react_agent_service.pending_actions)

    def test_react_agent_approval_and_execution(self):
        # Test approval of a critical action
        q = "cargo check komutunu çalıştır"
        res = react_agent_service.run(user_query=q, max_steps=2, require_approval=True)
        self.assertEqual(res["status"], "WAITING_APPROVAL")
        action_id = res["pending_action"]["action_id"]

        # Approve action
        approve_res = react_agent_service.execute_decision(
            action_id=action_id,
            approved=True
        )
        self.assertEqual(approve_res["status"], "EXECUTED")
        self.assertIsNotNone(approve_res["result"])

    def test_audit_log_written(self):
        # Verify that hitl_audit.log exists and contains log entries
        self.assertTrue(os.path.exists(AUDIT_LOG_FILE))
        with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertGreater(len(lines), 0)
        last_entry = json.loads(lines[-1])
        self.assertIn("timestamp", last_entry)
        self.assertIn("status", last_entry)
        self.assertIn("tool", last_entry)

    def test_autonomous_mode_bypass(self):
        # When require_approval=False, non-critical or critical actions can run autonomously
        q = "Sistemdeki disk alanını oku"
        res = react_agent_service.run(user_query=q, max_steps=2, require_approval=False)
        self.assertEqual(res["status"], "COMPLETED")
        self.assertIsNone(res["pending_action"])

if __name__ == "__main__":
    unittest.main()
