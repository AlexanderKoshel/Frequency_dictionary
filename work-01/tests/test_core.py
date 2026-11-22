import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from src.database.repository import Repository
from src.dictionary.frequency import import_file
from src.main import main
from src.parser.text_finder import find_all_texts
from src.parser.text_loader import load_from_folder
from src.parser.tokenizer import iter_words, tokenize, validate_word


class TokenizerTests(unittest.TestCase):
    def test_languages_and_punctuation(self):
        self.assertEqual(list(tokenize("Ёлка, ёлка! кто-то English котcat 123", "ru")), ["ёлка", "ёлка", "кто-то"])
        self.assertEqual(list(tokenize("DON’T mother-in-law rock’n’roll", "en")), ["don't", "mother-in-law", "rock'n'roll"])
        self.assertEqual(list(tokenize("Беларусь сям’я воўк і ёлка щука", "be")), ["беларусь", "сям'я", "воўк", "і", "ёлка"])

    def test_every_chunk_boundary(self):
        text = "Е\u0308лка кто‑то кот привет! "
        expected = list(tokenize(text, "ru"))
        for size in range(1, len(text) + 1):
            self.assertEqual(list(iter_words((text[i:i+size] for i in range(0, len(text), size)), "ru")), expected)

    def test_validation(self):
        for value in ["", "two words", "cat3", "_", "кот", "-cat"]:
            with self.assertRaises(ValueError):
                validate_word(value, "en")
        self.assertEqual(validate_word(" CAT ", "en"), "cat")


class DictionaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "data" / "words.db"
        self.repo = Repository(self.db)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def text(self, name, value, encoding="utf-8"):
        path = self.root / name
        path.write_text(value, encoding=encoding)
        return path

    def test_import_persistence_and_duplicate_content(self):
        first = self.text("first.txt", "Cat cat dog")
        outcome = import_file(self.repo, first, "en", batch_size=1)
        self.assertEqual(outcome["tokens"], 3)
        self.assertTrue(import_file(self.repo, self.text("copy.txt", "Cat cat dog"), "en")["skipped"])
        self.assertEqual(self.repo.rows("en"), [("cat", 2), ("dog", 1)])
        second = Repository(self.db)
        try:
            self.assertEqual(second.stats("en")["total"], 3)
        finally:
            second.close()

    def test_crud_merge_and_statistics(self):
        import_file(self.repo, self.text("a.txt", "cat cat dog"), "en")
        self.repo.add("en", "new")
        self.repo.add("en", "cat")
        self.assertEqual(dict(self.repo.rows("en"))["new"], 0)
        self.repo.rename("en", "cat", "dog")
        self.assertEqual(dict(self.repo.rows("en"))["dog"], 3)
        self.repo.rename("en", "dog", "Dog")
        self.repo.rename("en", "dog", "tree")
        self.repo.delete("en", "tree")
        self.assertEqual(self.repo.stats("en"), {"total": 0, "unique": 1, "imported": 3, "target": 5000000})
        with self.assertRaises(ValueError):
            self.repo.rename("en", "missing", "valid")

    def test_prefix_sorts_pages_and_language_isolation(self):
        import_file(self.repo, self.text("a.txt", "cat cat car dog"), "en")
        import_file(self.repo, self.text("b.txt", "кот кот"), "ru")
        self.assertEqual(self.repo.rows("en", "CA"), [("car", 1), ("cat", 2)])
        self.assertEqual(self.repo.rows("en", "c", "frequency", True, 1), [("cat", 2)])
        self.assertEqual(self.repo.rows("en", sort="word", descending=True, limit=1, offset=1), [("cat", 2)])
        self.assertEqual(self.repo.rows("en", "%"), [])
        self.assertEqual(self.repo.rows("en", "' OR 1=1 --"), [])
        self.assertEqual(self.repo.stats("ru")["total"], 2)
        with self.assertRaises(ValueError):
            self.repo.rows("en", sort="DROP TABLE words")

    def test_alphabet_yo_and_belarusian(self):
        for word in ["жук", "ёлка", "ель"]:
            self.repo.add("ru", word)
        self.assertEqual([w for w, _ in self.repo.rows("ru")], ["ель", "ёлка", "жук"])
        for word in ["кава", "іголка", "йод", "воўк"]:
            self.repo.add("be", word)
        self.assertEqual([w for w, _ in self.repo.rows("be")], ["воўк", "іголка", "йод", "кава"])

    def test_failed_decode_rolls_back_flushed_batches(self):
        path = self.root / "broken.txt"
        path.write_bytes(b"cat " * 20000 + b"\xff")
        with self.assertRaises(UnicodeError):
            import_file(self.repo, path, "en", batch_size=1)
        self.assertEqual(self.repo.stats("en")["total"], 0)
        self.assertEqual(self.repo.stats("en")["imported"], 0)
        self.assertEqual(self.repo.connection.execute("SELECT COUNT(*) FROM imports").fetchone()[0], 0)

    def test_encodings_and_finder(self):
        self.text("cyrillic.TXT", "кот кот", "cp1251")
        nested = self.root / "nested"
        nested.mkdir()
        (nested / "a.txt").write_text("hello", encoding="utf-8")
        paths = find_all_texts(self.root)
        self.assertEqual(len(paths), 2)
        import_file(self.repo, self.root / "cyrillic.TXT", "ru", "cp1251")
        self.assertEqual(self.repo.stats("ru")["total"], 2)
        self.assertEqual(load_from_folder(nested), ["hello"])
        with self.assertRaises(NotADirectoryError):
            find_all_texts(self.root / "missing")

    def test_cli(self):
        path = self.text("sample.txt", "cat cat dog")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--db", str(self.db), "import", "en", str(path)]), 0)
            self.assertEqual(main(["--db", str(self.db), "search", "en", "ca"]), 0)
            self.assertEqual(main(["--db", str(self.db), "stats", "en"]), 0)
        self.assertIn("cat\t2", output.getvalue())


if __name__ == "__main__":
    unittest.main()
