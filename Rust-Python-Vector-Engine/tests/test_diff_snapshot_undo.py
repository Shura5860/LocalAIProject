import os
import sys
import shutil
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.main import app
from api_server.app.services.diff_snapshot_service import DiffSnapshotService, diff_snapshot_service
from api_server.app.services.react_agent_service import react_agent_service
from api_server.app.tools.devops import write_file, apply_diff, _get_base_workspace


class TestDiffSnapshotAndUndo(unittest.TestCase):
    def setUp(self):
        self.base_ws = _get_base_workspace()
        self.scratch_dir = os.path.join(self.base_ws, "tests_diff_scratch")
        os.makedirs(self.scratch_dir, exist_ok=True)
        self.sample_file = os.path.join(self.scratch_dir, "sample.py")
        self.rel_sample = os.path.relpath(self.sample_file, self.base_ws)
        with open(self.sample_file, "w", encoding="utf-8") as f:
            f.write("def greet(name):\n    return f'Hello {name}'\n")
        self.client = TestClient(app)

    def tearDown(self):
        if os.path.exists(self.scratch_dir):
            shutil.rmtree(self.scratch_dir)

    def test_build_diff_preview_for_apply_diff(self):
        svc = DiffSnapshotService()
        preview = svc.build_diff_preview(
            "apply_diff",
            {
                "path": self.rel_sample,
                "search_block": "    return f'Hello {name}'",
                "replace_block": "    return f'Merhaba {name}!'",
            },
        )
        self.assertIsNotNone(preview)
        self.assertEqual(preview["total_files"], 1)
        self.assertEqual(preview["total_additions"], 1)
        self.assertEqual(preview["total_deletions"], 1)
        file_diff = preview["files"][0]
        self.assertFalse(file_diff["is_new_file"])
        self.assertTrue(any(h["type"] == "del" and "Hello" in h["text"] for h in file_diff["hunks"]))
        self.assertTrue(any(h["type"] == "add" and "Merhaba" in h["text"] for h in file_diff["hunks"]))

    def test_snapshot_capture_and_undo_existing_file(self):
        svc = DiffSnapshotService()
        args = {
            "path": self.rel_sample,
            "search_block": "    return f'Hello {name}'",
            "replace_block": "    return f'Selam {name}'",
        }
        snap = svc.capture_snapshot("apply_diff", args)
        self.assertIsNotNone(snap)

        apply_diff.execute(**args)
        with open(self.sample_file, "r", encoding="utf-8") as f:
            self.assertIn("Selam", f.read())

        undo_res = svc.undo_snapshot(snap["snapshot_id"])
        self.assertEqual(undo_res["status"], "REVERTED")
        with open(self.sample_file, "r", encoding="utf-8") as f:
            self.assertIn("Hello", f.read())

    def test_snapshot_undo_deletes_newly_created_file(self):
        svc = DiffSnapshotService()
        new_file_abs = os.path.join(self.scratch_dir, "brand_new.py")
        new_file_rel = os.path.relpath(new_file_abs, self.base_ws)

        args = {"path": new_file_rel, "content": "print('new')\n"}
        snap = svc.capture_snapshot("write_file", args)
        self.assertTrue(snap["diff_preview"]["files"][0]["is_new_file"])

        write_file.execute(**args)
        self.assertTrue(os.path.exists(new_file_abs))

        undo_res = svc.undo_snapshot(snap["snapshot_id"])
        self.assertEqual(undo_res["status"], "REVERTED")
        self.assertFalse(os.path.exists(new_file_abs))

    def test_api_decision_and_undo_endpoints(self):
        action_id = "test-diff-action-001"
        args = {
            "path": self.rel_sample,
            "search_block": "    return f'Hello {name}'",
            "replace_block": "    return f'API_UPDATED {name}'",
        }
        diff_preview = diff_snapshot_service.build_diff_preview("apply_diff", args)
        react_agent_service.pending_actions[action_id] = {
            "action_id": action_id,
            "tool": "apply_diff",
            "args": args,
            "description": "Test diff action",
            "diff_preview": diff_preview,
        }

        res_approve = self.client.post(
            "/agent/action/decision",
            json={"action_id": action_id, "approved": True},
        )
        self.assertEqual(res_approve.status_code, 200)
        body = res_approve.json()
        self.assertEqual(body["status"], "EXECUTED")
        self.assertEqual(body["snapshot_id"], action_id)
        self.assertIsNotNone(body["diff_preview"])

        # List changes
        res_list = self.client.get("/agent/changes")
        self.assertEqual(res_list.status_code, 200)
        changes = res_list.json()["changes"]
        self.assertTrue(any(c["snapshot_id"] == action_id and c["status"] == "applied" for c in changes))

        # Undo via API
        res_undo = self.client.post("/agent/changes/undo", json={"snapshot_id": action_id})
        self.assertEqual(res_undo.status_code, 200)
        self.assertEqual(res_undo.json()["status"], "REVERTED")

        with open(self.sample_file, "r", encoding="utf-8") as f:
            self.assertIn("Hello", f.read())


if __name__ == "__main__":
    unittest.main()

