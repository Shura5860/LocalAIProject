import sys
import os
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.main import app
from api_server.app.services.swarm_service import swarm_orchestrator, SwarmAgentRole


class TestSwarmEngine(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_swarm_orchestrator_run_direct(self):
        res = swarm_orchestrator.run_swarm(
            task_instruction="Yeni bir matematik modülü ekle ve test et",
            max_correction_loops=1
        )
        self.assertEqual(res["status"], "COMPLETED")
        self.assertGreaterEqual(res["total_events"], 3)
        agents = [e.get("agent") for e in res["events"] if "agent" in e]
        self.assertIn(SwarmAgentRole.ARCHITECT, agents)
        self.assertIn(SwarmAgentRole.CODER, agents)
        self.assertIn(SwarmAgentRole.VERIFIER, agents)

    def test_swarm_api_endpoint(self):
        payload = {
            "task": "Test görev: CLI komutunu güncelle",
            "max_correction_loops": 1,
            "auto_rollback_on_failure": True
        }
        response = self.client.post("/agent/swarm", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["task"], payload["task"])
        self.assertEqual(data["status"], "COMPLETED")
        self.assertGreater(data["total_events"], 0)
        self.assertTrue(len(data["events"]) > 0)

    def test_swarm_api_stream_endpoint(self):
        payload = {
            "task": "Streaming swarm görevi",
            "max_correction_loops": 1
        }
        response = self.client.post("/agent/swarm/stream", json=payload)
        self.assertEqual(response.status_code, 200)
        content = response.text
        self.assertIn("data: ", content)
        self.assertIn("[DONE]", content)
        self.assertIn("architect", content)


if __name__ == "__main__":
    unittest.main()
