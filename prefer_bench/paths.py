from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = REPO_ROOT / "benchmark"
CONTRACT_ROOT = BENCHMARK_ROOT / "contract" / "v1"
CONTRACT_PATH = CONTRACT_ROOT / "contract.json"
CONTRACT_SCHEMA_PATH = CONTRACT_ROOT / "contract.schema.json"
FIXTURES_ROOT = CONTRACT_ROOT / "fixtures"
EVAL_ROOT = BENCHMARK_ROOT / "eval" / "v1"
CORPUS_PATH = EVAL_ROOT / "corpus.json"
CORPUS_SCHEMA_PATH = EVAL_ROOT / "corpus.schema.json"
RESULT_SCHEMA_PATH = BENCHMARK_ROOT / "result.schema.json"
COMPOSE_PATH = BENCHMARK_ROOT / "docker-compose.yml"
PRESETS_ROOT = REPO_ROOT / "docker" / "prefer" / "presets"
