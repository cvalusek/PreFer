import unittest

from prefer_bench.mock_server import contract_mock_server
from prefer_bench.replay import replay_contract


class ReplayTests(unittest.TestCase):
    def test_mock_replay_covers_positive_and_negative_contract(self) -> None:
        with contract_mock_server() as base_url:
            result = replay_contract(base_url)
        self.assertEqual(result["summary"], {"passed": 16, "failed": 0, "total": 16})
        names = {check["name"] for check in result["checks"]}
        self.assertIn("client_timeout_is_bounded", names)
        self.assertIn("client_stream_close_is_bounded", names)
        self.assertIn("error_unknown_model_or_alias", names)
        self.assertIn("error_malformed_tool", names)
        self.assertIn("configured_identity_has_bounded_extension_or_error_behavior", names)


if __name__ == "__main__":
    unittest.main()
