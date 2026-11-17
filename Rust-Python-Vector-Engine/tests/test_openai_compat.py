import sys
import os
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.main import app


class TestOpenAICompatibility(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_list_models(self):
        response = self.client.get("/v1/models")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["object"], "list")
        self.assertGreaterEqual(len(data["data"]), 1)
        model_ids = [m["id"] for m in data["data"]]
        self.assertIn("qwen2.5-coder-3b", model_ids)

    def test_chat_completions_sync(self):
        payload = {
            "model": "qwen2.5-coder-3b",
            "messages": [
                {"role": "system", "content": "Sen bir asistansın."},
                {"role": "user", "content": "Merhaba!"}
            ],
            "max_tokens": 50,
            "stream": False
        }
        response = self.client.post("/v1/chat/completions", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["id"].startswith("chatcmpl-"))
        self.assertEqual(data["object"], "chat.completion")
        self.assertGreaterEqual(len(data["choices"]), 1)
        self.assertEqual(data["choices"][0]["message"]["role"], "assistant")
        self.assertIn("usage", data)

    def test_embeddings_endpoint(self):
        payload = {
            "model": "aura-multilingual-v1",
            "input": ["Merhaba dünya", "Rust ve Python ile AI"]
        }
        response = self.client.post("/v1/embeddings", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["object"], "list")
        self.assertEqual(len(data["data"]), 2)
        self.assertEqual(len(data["data"][0]["embedding"]), 384)


if __name__ == "__main__":
    unittest.main()

