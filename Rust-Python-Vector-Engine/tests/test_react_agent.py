import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.services.react_agent_service import react_agent_service

import unittest

class TestReActAgent(unittest.TestCase):
    def test_react_multistep(self):
        q1 = "Sistemdeki disk alanını oku ve bunu 1024 ile çarp."
        res1 = react_agent_service.run(user_query=q1, max_steps=5)
        self.assertGreaterEqual(len(res1["trace"]), 1)
        self.assertIsNotNone(res1.get("final_answer"))

    def test_react_direct_calculation(self):
        q2 = "450 * 20 kaçtır?"
        res2 = react_agent_service.run(user_query=q2, max_steps=3)
        self.assertGreaterEqual(len(res2["trace"]), 1)
        self.assertIsNotNone(res2.get("final_answer"))

if __name__ == "__main__":
    unittest.main()
