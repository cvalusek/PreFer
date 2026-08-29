from pathlib import Path, PurePosixPath


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = REPO_ROOT / "benchmark"
BASELINES_ROOT = BENCHMARK_ROOT / "baselines"
CONTRACT_ROOT = BENCHMARK_ROOT / "contract" / "v1"
CONTRACT_PATH = CONTRACT_ROOT / "contract.json"
CONTRACT_SCHEMA_PATH = CONTRACT_ROOT / "contract.schema.json"
FIXTURES_ROOT = CONTRACT_ROOT / "fixtures"
EVAL_ROOT = BENCHMARK_ROOT / "eval" / "v1"
CORPUS_PATH = EVAL_ROOT / "corpus.json"
CORPUS_SCHEMA_PATH = EVAL_ROOT / "corpus.schema.json"
RESULT_SCHEMA_PATH = BENCHMARK_ROOT / "result.schema.json"
COMPOSE_PATH = BENCHMARK_ROOT / "docker-compose.yml"
PRESETS_ROOT = REPO_ROOT / "docker" / "llama-cpp" / "presets"


def preset_paths() -> list[Path]:
    return sorted(PRESETS_ROOT.rglob("*.ini"))


def preset_relative(path: Path) -> str:
    return path.relative_to(PRESETS_ROOT).as_posix()


def resolve_preset(value: str) -> Path:
    relative = PurePosixPath(value.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".ini":
        raise ValueError(f"unsafe preset path: {value}")
    path = PRESETS_ROOT.joinpath(*relative.parts)
    if not path.is_file():
        raise ValueError(f"unknown preset: {value}")
    return path
