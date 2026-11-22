"""Stream corpora into bounded batches; roll back a whole file on any error."""
import hashlib
from collections import Counter
from pathlib import Path
from ..parser.text_loader import iter_text_chunks
from ..parser.tokenizer import iter_words


def import_file(repository, path, language, encoding="utf-8-sig", progress=None, batch_size=50000):
    repository.check_language(language)
    if batch_size <= 0:
        raise ValueError("Размер пакета должен быть положительным")
    path = Path(path)
    # Remember the content hash for duplicate detection; verify it again before commit.
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if repository.connection.execute("SELECT 1 FROM imports WHERE language=? AND digest=?", (language, digest)).fetchone():
        return {"path": str(path), "tokens": 0, "skipped": True}
    counts = Counter()
    total = 0
    with repository.connection:
        for word in iter_words(iter_text_chunks(path, encoding), language):
            counts[word] += 1
            total += 1
            if total % batch_size == 0:
                repository.add_counts(language, counts)
                counts.clear()
                if progress:
                    progress(total)
        repository.add_counts(language, counts)
        # Detect edits made between hashing and reading before committing anything.
        with path.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != digest:
                raise ValueError("Файл изменился во время импорта; повторите операцию")
        repository.connection.execute("INSERT INTO imports(language,digest,path,tokens) VALUES(?,?,?,?)",
                                      (language, digest, str(path.resolve()), total))
    return {"path": str(path), "tokens": total, "skipped": False}
