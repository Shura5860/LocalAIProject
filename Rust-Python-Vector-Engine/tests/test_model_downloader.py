import sys
import os
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.main import app
from api_server.app.services.model_downloader_service import model_downloader
from api_server.app.services.model_service import model_service


class TestModelDownloader(unittest.TestCase):
    def setUp(self):
        self._old_testing = os.environ.get("TESTING")
        os.environ["TESTING"] = "1"
        self.client = TestClient(app)
        self.original_catalog = dict(model_service.catalog)

    def tearDown(self):
        if self._old_testing is not None:
            os.environ["TESTING"] = self._old_testing
        else:
            os.environ.pop("TESTING", None)
        model_service.catalog = dict(self.original_catalog)

    def test_search_hub_direct(self):
        results = model_downloader.search_hub(query="qwen", limit=5)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        first = results[0]
        self.assertIn("id", first)
        self.assertIn("author", first)

    def test_search_hub_api(self):
        response = self.client.get("/models/hub/search?query=qwen")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_pull_model_stream_direct(self):
        test_model_id = "test-tiny-coder"
        events = list(model_downloader.pull_model_stream(
            repo="Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
            filename="tiny-coder-q4.gguf",
            model_id=test_model_id
        ))
        self.assertGreaterEqual(len(events), 4)
        last_event = events[-1]
        self.assertEqual(last_event.get("status"), "completed")
        self.assertEqual(last_event.get("progress"), 100.0)

        # Check if registered in catalog
        self.assertIn(test_model_id, model_service.catalog)
        self.assertEqual(model_service.catalog[test_model_id]["filename"], "tiny-coder-q4.gguf")

    def test_pull_model_api(self):
        payload = {
            "repo": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B-GGUF",
            "filename": "deepseek-7b-q4.gguf",
            "model_id": "test-deepseek-pull"
        }
        response = self.client.post("/models/pull", json=payload)
        self.assertEqual(response.status_code, 200)
        content = response.text
        self.assertIn("data: ", content)
        self.assertIn("completed", content)
        self.assertIn("test-deepseek-pull", content)


if __name__ == "__main__":
    unittest.main()
