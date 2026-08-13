import unittest

from benchmark.scripts.full_context import (
    FILLER_UNIT,
    _context_size_from_record,
    _matching_model,
    build_prompt,
    normalize_base_url,
    size_prompt,
)


class FullContextProbeTests(unittest.TestCase):
    def test_normalizes_root_and_v1_urls(self) -> None:
        self.assertEqual(normalize_base_url("http://127.0.0.1:8080/v1/"), "http://127.0.0.1:8080")
        self.assertEqual(normalize_base_url("http://127.0.0.1:8080"), "http://127.0.0.1:8080")

    def test_discovers_loaded_model_alias_and_context(self) -> None:
        record = {
            "id": "repo/model:Q4_K_XL",
            "aliases": ["model"],
            "status": {"value": "loaded", "args": ["llama-server", "--ctx-size", "262144"]},
        }
        model, selected = _matching_model([record], "model")
        self.assertEqual(model, "model")
        self.assertIs(selected, record)
        self.assertEqual(_context_size_from_record(record), 262144)

    def test_prompt_places_needles_in_order(self) -> None:
        codes = ["START-ONE", "MIDDLE-TWO", "END-THREE"]
        prompt = build_prompt(11, codes)
        self.assertLess(prompt.index(codes[0]), prompt.index(codes[1]))
        self.assertLess(prompt.index(codes[1]), prompt.index(codes[2]))
        self.assertEqual(prompt.count(FILLER_UNIT), 11)

    def test_sizer_converges_with_linear_tokenizer(self) -> None:
        codes = ["START-ONE", "MIDDLE-TWO", "END-THREE"]

        def token_counter(prompt: str) -> int:
            return 97 + 4 * prompt.count(FILLER_UNIT)

        prompt, repetitions, count = size_prompt(token_counter, 253952, 4, codes)
        self.assertLessEqual(abs(count - 253952), 4)
        self.assertEqual(prompt.count(FILLER_UNIT), repetitions)


if __name__ == "__main__":
    unittest.main()
