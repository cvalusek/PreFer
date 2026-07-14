import json
import unittest

from prefer_bench.contract import load_corpus
from prefer_bench.evaluate import evaluate_content


class EvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = {case["id"]: case for case in load_corpus()["cases"]}

    def test_schema_valid_impossible_date_is_semantic_anomaly(self) -> None:
        case = self.cases["aurora-facts-v1"]
        content = json.dumps({
            "project": "Project Aurora",
            "review_date": "2026-02-30",
            "owner": "Mira Chen",
            "required_action": "submit the risk register",
            "due_date": "2026-08-12",
            "launch_state": "paused",
        })
        result = evaluate_content(content, case["output_schema"], case["semantic_rules"])
        self.assertTrue(result["schema_valid"])
        self.assertIn("impossible_date", {item["code"] for item in result["semantic_anomalies"]})

    def test_schema_valid_weak_plan_is_semantic_anomaly(self) -> None:
        case = self.cases["cedar-plan-v1"]
        content = json.dumps({
            "plan_title": "Cedar",
            "steps": [
                {"sequence": 1, "action": "validates the backup", "owner": "Imani Rao", "due_date": "2026-09-03", "evidence": "restore log"},
                {"sequence": 2, "action": "runs the failover drill", "owner": "Theo Park", "due_date": "2026-09-05", "evidence": "drill transcript"},
                {"sequence": 3, "action": "something vague", "owner": "Imani Rao", "due_date": "2026-09-06", "evidence": "signed checklist"},
            ],
            "release_freeze_date": "2026-09-07",
        })
        result = evaluate_content(content, case["output_schema"], case["semantic_rules"])
        self.assertTrue(result["schema_valid"])
        self.assertIn("missing_required_planning_content", {item["code"] for item in result["semantic_anomalies"]})

    def test_malformed_json_fails_structure_without_fake_semantics(self) -> None:
        case = self.cases["aurora-facts-v1"]
        result = evaluate_content("{", case["output_schema"], case["semantic_rules"])
        self.assertFalse(result["json_valid"])
        self.assertFalse(result["schema_valid"])
        self.assertEqual(result["semantic_anomalies"][0]["code"], "unparseable_structured_content")


if __name__ == "__main__":
    unittest.main()
