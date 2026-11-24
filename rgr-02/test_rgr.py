import csv
import json
import sqlite3
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from corpus import belarusian_lexicon
from main import analyze
from src.database.repository import Repository
from src.dictionary.frequency import import_file
from statistics_rgr import dictionary, dispersion_rows, fit_reciprocal, juilland, length_statistics


class StatisticsTests(unittest.TestCase):
    def test_zipf_exact_reciprocal(self):
        result = fit_reciprocal([1, 2, 3, 4], [12, 6, 4, 3])
        self.assertEqual(result["c"], 12)
        self.assertAlmostEqual(result["log_slope"], -1)

    def test_length_ties_and_constant_length(self):
        rows = [("a", 1, 12), ("to", 2, 6), ("of", 2, 6), ("and", 3, 4)]
        result = length_statistics(rows)
        self.assertAlmostEqual(result["spearman"], -1)
        self.assertEqual(result["fit"]["c"], 12)
        self.assertIsNone(length_statistics(rows[1:3])["spearman"])

    def test_dispersion_matches_assignment_and_boundaries(self):
        self.assertAlmostEqual(juilland([10, 11, 8, 3]), 77.75608697)
        self.assertEqual(juilland([1, 1, 1, 1]), 100)
        self.assertEqual(juilland([7, 0, 0, 0]), 0)
        segments = [Counter(word=1), Counter(word=2)]
        row, = dispersion_rows(dictionary(segments), segments, [10, 20])
        self.assertEqual(row, ("word", 100_000, 1, 100))


class IntegrationTests(unittest.TestCase):
    def test_belarusian_lexicon_picks_most_common_lemma(self):
        entries = [
            "1\tсловы\tслова\tNOUN\t_\t_\t0\troot\t_\t_\n",
            "1\tсловы\tслова\tNOUN\t_\t_\t0\troot\t_\t_\n",
            "1\tсловы\tсловы\tNOUN\t_\t_\t0\troot\t_\t_\n",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "be.conllu"
            path.write_text("".join(entries), encoding="utf-8")
            self.assertEqual(belarusian_lexicon(path), {"словы": "слова"})

    def test_run_matches_work_01_and_keeps_token_count_after_lemmatization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            content = "The children and the child ran to the park."
            filename = source / "a.txt"
            filename.write_text(content, encoding="utf-8")
            (source / "b.txt").write_text(content, encoding="utf-8")

            db = root / "work-01.db"
            repository = Repository(db)
            try:
                import_file(repository, filename, "en")
            finally:
                repository.close()

            out = root / "results"
            analyze("en", source, "utf-8-sig", 4, None, None, out)
            with sqlite3.connect(db) as connection:
                expected = dict(connection.execute(
                    "SELECT word, frequency FROM words WHERE language = 'en'"
                ).fetchall())
            results = {}
            for mode in ("forms", "lemmas"):
                with (out / f"zipf-{mode}.csv").open(encoding="utf-8-sig") as table_file:
                    results[mode] = {
                        row["word"]: int(row["frequency"]) for row in csv.DictReader(table_file)
                    }
                self.assertEqual(sum(results[mode].values()), 9)
            self.assertEqual(expected, results["forms"])
            self.assertEqual(results["lemmas"]["child"], 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["segment_sizes"], [3, 2, 2, 2])
            self.assertEqual(len(summary["files"]), 1)
            self.assertTrue((out / "report.docx").is_file())


if __name__ == "__main__":
    unittest.main()
