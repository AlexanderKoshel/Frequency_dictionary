"""SQLite storage. All mutations are transactional; SQL sort keys are allowlisted."""
import sqlite3
from pathlib import Path
from ..parser.tokenizer import LANGUAGES, normalize, validate_word

TARGET = 5_000_000


# Explicit language order, including ё after е and Belarusian і/ў.
ALPHABET_RANKS = {letter: index for index, letter in enumerate("абвгдеёжзіийклмнопрстуўфхцчшщъыьэюя")}


def alphabet_key(word):
    return tuple(ALPHABET_RANKS.get(c, ord(c) + 100) for c in word)


class Repository:
    def __init__(self, path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.create_collation("ALPHABET", lambda a, b: (alphabet_key(a) > alphabet_key(b)) - (alphabet_key(a) < alphabet_key(b)))
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS words (
                language TEXT NOT NULL CHECK(language IN ('ru','en','be')),
                word TEXT NOT NULL,
                frequency INTEGER NOT NULL CHECK(frequency >= 0),
                PRIMARY KEY(language, word)
            );
            CREATE INDEX IF NOT EXISTS words_frequency ON words(language, frequency DESC, word);
            CREATE TABLE IF NOT EXISTS imports (
                language TEXT NOT NULL, digest TEXT NOT NULL,
                path TEXT NOT NULL, tokens INTEGER NOT NULL,
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(language, digest)
            );
        """)

    def close(self):
        self.connection.close()

    def check_language(self, language):
        if language not in LANGUAGES:
            raise ValueError(f"Неизвестный язык: {language}")

    def add(self, language, word):
        word = validate_word(word, language)
        with self.connection:
            self.connection.execute("INSERT OR IGNORE INTO words VALUES (?, ?, 0)", (language, word))

    def rename(self, language, old_word, new_word):
        old_word = validate_word(old_word, language)
        new_word = validate_word(new_word, language)
        with self.connection:
            row = self.connection.execute("SELECT frequency FROM words WHERE language=? AND word=?", (language, old_word)).fetchone()
            if row is None:
                raise ValueError("Исходное слово не найдено")
            if old_word == new_word:
                return
            self.add_counts(language, {new_word: row[0]})
            self.connection.execute("DELETE FROM words WHERE language=? AND word=?", (language, old_word))

    def delete(self, language, word):
        word = validate_word(word, language)
        with self.connection:
            self.connection.execute("DELETE FROM words WHERE language=? AND word=?", (language, word))

    def add_counts(self, language, counts):
        """Internal batch operation; caller owns the transaction."""
        self.check_language(language)
        self.connection.executemany("""
            INSERT INTO words VALUES (?, ?, ?)
            ON CONFLICT(language, word) DO UPDATE SET frequency=frequency+excluded.frequency
        """, ((language, word, count) for word, count in counts.items()))

    def rows(self, language, prefix="", sort="word", descending=False, limit=200, offset=0):
        self.check_language(language)
        if sort not in {"word", "frequency"} or not 1 <= limit <= 10000 or offset < 0:
            raise ValueError("Некорректные параметры страницы")
        order = "DESC" if descending else "ASC"
        key = "word COLLATE ALPHABET" if sort == "word" else "frequency"
        # Literal prefix: %, _ and SQL syntax cannot become wildcards or commands.
        prefix = normalize(prefix.strip())
        where = "language=?"
        args = [language]
        if prefix:
            where += " AND word>=? AND word<?"
            args.extend([prefix, prefix + chr(0x10ffff)])
        return self.connection.execute(
            f"SELECT word, frequency FROM words WHERE {where} ORDER BY {key} {order}, word COLLATE ALPHABET ASC LIMIT ? OFFSET ?",
            (*args, limit, offset)).fetchall()

    def stats(self, language):
        self.check_language(language)
        unique, total = self.connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(frequency),0) FROM words WHERE language=?", (language,)).fetchone()
        imported = self.connection.execute(
            "SELECT COALESCE(SUM(tokens),0) FROM imports WHERE language=?", (language,)).fetchone()[0]
        return {"unique": unique, "total": total, "imported": imported, "target": TARGET}
