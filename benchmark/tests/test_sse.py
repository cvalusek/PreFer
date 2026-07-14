import unittest

from prefer_bench.paths import FIXTURES_ROOT
from prefer_bench.sse import SSEError, parse_text


class SSETests(unittest.TestCase):
    def test_fixture_has_chunks_and_done(self) -> None:
        transcript = parse_text((FIXTURES_ROOT / "stream.sse").read_text(encoding="utf-8"))
        self.assertTrue(transcript.done)
        self.assertEqual(len(transcript.events), 3)

    def test_missing_done_is_rejected(self) -> None:
        with self.assertRaisesRegex(SSEError, "without data"):
            parse_text('data: {"object":"chat.completion.chunk","choices":[]}\n\n')

    def test_malformed_event_is_rejected(self) -> None:
        with self.assertRaisesRegex(SSEError, "invalid JSON"):
            parse_text("data: {\n\ndata: [DONE]\n\n")

    def test_wrong_chunk_object_is_rejected(self) -> None:
        with self.assertRaisesRegex(SSEError, "chat.completion.chunk"):
            parse_text('data: {"object":"chat.completion","choices":[]}\n\ndata: [DONE]\n\n')


if __name__ == "__main__":
    unittest.main()
