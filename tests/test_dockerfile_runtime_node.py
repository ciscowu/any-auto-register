import unittest
from pathlib import Path


class DockerfileRuntimeNodeTests(unittest.TestCase):
    def test_runtime_stage_installs_nodejs(self):
        dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"
        content = dockerfile.read_text(encoding="utf-8")

        runtime_section = content.split("FROM python:3.12-slim AS runtime", 1)[1]

        self.assertIn("nodejs", runtime_section)


if __name__ == "__main__":
    unittest.main()
