import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server.app.services.swarm_service import SwarmOrchestrator


class TestCompilerDirectedRepair(unittest.TestCase):
    def test_parse_rust_compiler_error(self):
        rust_output = """
error[E0308]: mismatched types
  --> src/main.rs:14:9
   |
14 |     let x: u32 = -5;
   |            ^^^   ^^ expected `u32`, found `i32`
   |
help: you can convert an `i32` to a `u32`
        """
        parsed = SwarmOrchestrator.parse_compiler_errors(rust_output, "src/main.rs")
        self.assertTrue(parsed["has_error"])
        self.assertEqual(parsed["file"], "src/main.rs")
        self.assertEqual(parsed["line"], 14)
        self.assertEqual(parsed["column"], 9)
        self.assertEqual(parsed["error_code"], "E0308")
        self.assertIn("mismatched types", parsed["message"])
        self.assertIn("convert", parsed["suggestion"])

    def test_parse_python_compiler_error(self):
        py_output = """
  File "calculator.py", line 42
    def add(a, b)
                 ^
SyntaxError: expected ':'
        """
        parsed = SwarmOrchestrator.parse_compiler_errors(py_output, "calculator.py")
        self.assertTrue(parsed["has_error"])
        self.assertEqual(parsed["file"], "calculator.py")
        self.assertEqual(parsed["line"], 42)
        self.assertIn("SyntaxError", parsed["message"])
        self.assertIn("def add", parsed["suggestion"])

    def test_clean_output_has_no_error(self):
        clean_output = "Compiling project v0.1.0\nFinished dev profile [unoptimized + debuginfo] in 0.42s"
        parsed = SwarmOrchestrator.parse_compiler_errors(clean_output, "src/lib.rs")
        self.assertFalse(parsed["has_error"])


if __name__ == "__main__":
    unittest.main()

