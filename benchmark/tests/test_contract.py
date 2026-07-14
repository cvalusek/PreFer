import json
from pathlib import Path
import unittest

from prefer_bench.contract import (
    ContractError,
    load_contract,
    load_corpus,
    load_json,
    preset_contract_diff,
    validate_chat_request,
    validate_chat_response,
    validate_error_response,
    validate_models_response,
    validate_tool_calls,
)
from prefer_bench.paths import FIXTURES_ROOT


class ContractFixtureTests(unittest.TestCase):
    def test_contract_and_corpus_validate(self) -> None:
        self.assertEqual(load_contract()["contract_version"], "1.0.0")
        self.assertEqual(load_corpus()["data_class"], "synthetic_non_private")

    def test_contract_matches_all_preset_ids_aliases_and_quantizations(self) -> None:
        self.assertEqual(preset_contract_diff(), [])

    def test_ground_control_model_and_alias_are_pinned(self) -> None:
        model = next(item for item in load_contract()["models"] if "gemma-4-E2B" in item["canonical_id"])
        self.assertEqual(model["canonical_id"], "unsloth/gemma-4-E2B-it-qat-GGUF:UD-Q4_K_XL")
        self.assertEqual(model["discovery_id"], "unsloth/gemma-4-E2B-it-qat-GGUF:Q4_K_XL")
        self.assertIn("gemma-4-e2b", model["aliases"])

    def test_response_fixtures_match_minimal_envelopes(self) -> None:
        self.assertEqual(validate_models_response(load_json(FIXTURES_ROOT / "models.json")), [])
        for name in ("chat-nonstream.json", "chat-structured.json", "chat-tool-call.json", "chat-tool-result.json"):
            self.assertEqual(validate_chat_response(load_json(FIXTURES_ROOT / name)), [], name)
        self.assertEqual(validate_error_response(load_json(FIXTURES_ROOT / "error.json")), [])

    def test_tool_arguments_must_be_json_object_string(self) -> None:
        invalid = [{"id": "x", "type": "function", "function": {"name": "f", "arguments": "[]"}}]
        self.assertTrue(validate_tool_calls(invalid))

    def test_negative_missing_model_and_alias(self) -> None:
        with self.assertRaisesRegex(ContractError, "model is required"):
            validate_chat_request({"messages": [{"role": "user", "content": "x"}]})
        with self.assertRaisesRegex(ContractError, "unknown model"):
            validate_chat_request({"model": "not-a-model", "messages": [{"role": "user", "content": "x"}]})
        with self.assertRaisesRegex(ContractError, "unknown model"):
            validate_chat_request({"model": "unsloth/gemma-4-E2B-it-qat-GGUF:UD-Q4_K_XL", "messages": [{"role": "user", "content": "x"}]})

    def test_negative_unsupported_streaming_and_tools(self) -> None:
        with self.assertRaisesRegex(ContractError, "streaming n"):
            validate_chat_request({"model": "gemma-4-e2b", "messages": [{"role": "user", "content": "x"}], "stream": True, "n": 2})
        with self.assertRaisesRegex(ContractError, "parallel_tool_calls"):
            validate_chat_request({"model": "gemma-4-e2b", "messages": [{"role": "user", "content": "x"}], "parallel_tool_calls": True})
        with self.assertRaisesRegex(ContractError, "function tools require"):
            validate_chat_request({"model": "gemma-4-e2b", "messages": [{"role": "user", "content": "x"}], "tools": [{"type": "function", "function": {"name": "x"}}]})
        with self.assertRaisesRegex(ContractError, "function tools"):
            validate_chat_request({"model": "gemma-4-e2b", "messages": [{"role": "user", "content": "x"}], "tools": [None]})
        with self.assertRaisesRegex(ContractError, "function tools require"):
            validate_chat_request({
                "model": "gemma-4-e2b",
                "messages": [{"role": "user", "content": "x"}],
                "tools": [{"type": "function", "function": {"name": "", "parameters": {}}}],
            })

    def test_negative_malformed_structured_request(self) -> None:
        with self.assertRaisesRegex(ContractError, "json_schema.strict"):
            validate_chat_request({
                "model": "gemma-4-e2b",
                "messages": [{"role": "user", "content": "x"}],
                "response_format": {"type": "json_schema", "json_schema": {"name": "x", "schema": {}}},
            })


if __name__ == "__main__":
    unittest.main()
