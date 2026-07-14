import unittest

from prefer_bench.report import render_markdown
from prefer_bench.results import empty_cell, summarize, validate_result
from prefer_bench.runner import _percentile


def sample_result() -> dict:
    good = empty_cell("structured-good", "structured_output")
    good["contract"]["pass"] = True
    good["quality"] = {"schema_valid": True, "semantic_evaluated": True, "semantic_anomalies": []}
    bad_semantics = empty_cell("structured-bad-date", "structured_output")
    bad_semantics["contract"]["pass"] = True
    bad_semantics["quality"] = {
        "schema_valid": True,
        "semantic_evaluated": True,
        "semantic_anomalies": [{"code": "impossible_date", "path": "/date"}],
    }
    cells = [good, bad_semantics]
    return {
        "schema_version": "prefer.benchmark-result.v1",
        "run": {
            "run_id": "fixture-run",
            "started_at": "2026-07-14T00:00:00Z",
            "duration_ms": 1000.0,
            "source_revision": "2fc6c8159535757f10f5d193e7ccbd4045ef0dd0",
            "source_dirty": False,
            "backend": {
                "name": "llama.cpp",
                "base_image": "fixture:b9843",
                "image_id": None,
                "revision": "b9843",
                "comparison_lane": False,
            },
            "contract_version": "1.0.0",
            "eval_version": "1.0.0",
            "hardware": {"tier": "12gb", "gpus": []},
            "preset": "12gb.ini",
            "models_max": 1,
            "command": ["python", "-m", "prefer_bench", "local"],
            "cleanup": {},
        },
        "cells": cells,
        "summary": summarize(cells),
    }


class ResultTests(unittest.TestCase):
    def test_concurrency_percentiles_are_interpolated(self) -> None:
        self.assertEqual(_percentile([100.0, 200.0], 0.50), 150.0)
        self.assertEqual(_percentile([100.0, 200.0], 0.95), 195.0)

    def test_result_schema_and_separate_rates(self) -> None:
        result = sample_result()
        validate_result(result)
        self.assertEqual(result["summary"]["schema_contract_pass_rate"], 1.0)
        self.assertEqual(result["summary"]["semantic_anomaly_rate"], 0.5)
        self.assertEqual(result["summary"]["schema_contract_attempts"], 2)
        self.assertEqual(result["summary"]["semantic_evaluations"], 2)

    def test_unproduced_document_fails_schema_without_diluting_semantics(self) -> None:
        result = sample_result()
        rejected = empty_cell("structured-rejected", "structured_output")
        rejected["contract"]["pass"] = False
        rejected["quality"] = {"schema_valid": False, "semantic_evaluated": False, "semantic_anomalies": []}
        result["cells"].append(rejected)
        result["summary"] = summarize(result["cells"])
        validate_result(result)
        self.assertAlmostEqual(result["summary"]["schema_contract_pass_rate"], 2 / 3)
        self.assertEqual(result["summary"]["semantic_anomaly_rate"], 0.5)
        self.assertEqual(result["summary"]["schema_contract_attempts"], 3)
        self.assertEqual(result["summary"]["semantic_evaluations"], 2)

    def test_report_keeps_schema_and_semantics_separate(self) -> None:
        report = render_markdown(sample_result())
        self.assertIn("Schema-contract pass rate: **100.0%**", report)
        self.assertIn("Semantic anomaly rate: **50.0%**", report)
        self.assertIn("impossible_date", report)
        self.assertIn("No architecture choice", report)


if __name__ == "__main__":
    unittest.main()
