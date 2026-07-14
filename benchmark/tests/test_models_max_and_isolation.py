import os
from pathlib import Path
import unittest

from prefer_bench.contract import inspect_models_max
from prefer_bench.local import _free_port, _safe_environment
from prefer_bench.paths import COMPOSE_PATH, REPO_ROOT


class ModelsMaxAndIsolationTests(unittest.TestCase):
    def test_models_max_defaults_and_precedence_are_exact(self) -> None:
        facts = inspect_models_max(REPO_ROOT)
        self.assertEqual(facts["compose_default"], 1)
        self.assertEqual(facts["env_example_default"], 1)
        self.assertEqual(facts["auto_detection_default"], 1)
        self.assertEqual(facts["upstream_fallback_default"], 4)
        self.assertEqual(facts["tier_presets_with_load_on_startup"], [])

    def test_benchmark_compose_cannot_claim_operator_names_or_port(self) -> None:
        text = COMPOSE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("container_name:", text)
        self.assertNotIn('"8080:8080"', text)
        self.assertIn("127.0.0.1:${PREFER_BENCH_PORT", text)
        self.assertIn("PREFER_BENCH_PROJECT:?", text)
        self.assertIn("PREFER_BENCH_VOLUME:?", text)
        self.assertIn("external: true", text)
        self.assertIn("PRESTAGE_MODELS: none", text)
        self.assertNotIn("HF_TOKEN", text)
        self.assertNotIn("S3_BUCKET_NAME", text)

    def test_compose_subprocess_environment_drops_credentials(self) -> None:
        old = os.environ.get("HF_TOKEN")
        os.environ["HF_TOKEN"] = "must-not-propagate"
        try:
            safe = _safe_environment({"PREFER_BENCH_PROJECT": "prefer-bench-test"})
        finally:
            if old is None:
                os.environ.pop("HF_TOKEN", None)
            else:
                os.environ["HF_TOKEN"] = old
        self.assertNotIn("HF_TOKEN", safe)
        self.assertEqual(safe["COMPOSE_DISABLE_ENV_FILE"], "1")

    def test_port_allocator_never_uses_operator_or_ephemeral_port(self) -> None:
        port = _free_port()
        self.assertGreaterEqual(port, 18080)
        self.assertLess(port, 19000)
        self.assertNotEqual(port, 8080)


if __name__ == "__main__":
    unittest.main()
