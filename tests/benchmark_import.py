"""Optional capacity check: python -m tests.benchmark_import is not required.
Run from the repository root: python tests/benchmark_import.py.
Synthetic repetitions test counting capacity only; they are NOT real corpora.
"""
from pathlib import Path
import sys
import tempfile
from time import perf_counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.database.repository import Repository
from src.dictionary.frequency import import_file


def main():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        repository = Repository(root / "benchmark.db")
        try:
            for language, phrase in [("en", "cat dog tree sky sun "),
                                    ("ru", "кот дом лес мир сон "),
                                    ("be", "кот дом лес мір сон ")]:
                path = root / f"{language}.txt"
                with path.open("w", encoding="utf-8") as target:
                    for _ in range(1000):
                        target.write(phrase * 1000 + "\n")
                start = perf_counter()
                result = import_file(repository, path, language)
                assert result["tokens"] == 5_000_000
                assert repository.stats(language)["total"] == 5_000_000
                assert repository.stats(language)["imported"] == 5_000_000
                print(f"{language}: 5,000,000 synthetic tokens, {perf_counter() - start:.2f}s")
        finally:
            repository.close()


if __name__ == "__main__":
    main()
