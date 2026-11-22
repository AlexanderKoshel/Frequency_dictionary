"""Run with python -m src.main or python src/main.py."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "src"

from .database.repository import Repository
from .dictionary.frequency import import_file
from .parser.text_finder import ROOT, find_all_texts


def main(argv=None):
    parser = argparse.ArgumentParser(description="Частотные словари: русский, английский, белорусский")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "dictionary.db")
    sub = parser.add_subparsers(dest="command")
    imp = sub.add_parser("import", help="Импорт TXT-файла или папки")
    imp.add_argument("language", choices=("ru", "en", "be"))
    imp.add_argument("path", type=Path)
    imp.add_argument("--encoding", default="utf-8-sig")
    stats = sub.add_parser("stats")
    stats.add_argument("language", choices=("ru", "en", "be"))
    search = sub.add_parser("search")
    search.add_argument("language", choices=("ru", "en", "be"))
    search.add_argument("prefix", nargs="?", default="")
    search.add_argument("--sort", choices=("word", "frequency"), default="word")
    search.add_argument("--desc", action="store_true")
    search.add_argument("--limit", type=int, default=200)
    args = parser.parse_args(argv)
    if args.command is None:
        try:
            from PySide6.QtWidgets import QApplication
            from .ui.main_window import MainWindow
        except ImportError:
            parser.exit(1, "Для интерфейса выполните: python -m pip install -r requirements.txt\n")
        app = QApplication(sys.argv[:1])
        try:
            window = MainWindow(args.db)
        except (OSError, ValueError, sqlite3.Error) as error:
            parser.exit(1, f"Ошибка: {error}\n")
        window.show()
        return app.exec()
    repository = None
    try:
        repository = Repository(args.db)
        if args.command == "import":
            paths = find_all_texts(args.path) if args.path.is_dir() else [args.path]
            if not paths:
                raise ValueError("TXT-файлы не найдены")
            for path in paths:
                print(json.dumps(import_file(repository, path, args.language, args.encoding), ensure_ascii=False))
        elif args.command == "stats":
            print(json.dumps(repository.stats(args.language), ensure_ascii=False, indent=2))
        elif args.command == "search":
            for word, count in repository.rows(args.language, args.prefix, args.sort, args.desc, args.limit):
                print(f"{word}\t{count}")
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f"Ошибка: {error}\n")
    finally:
        if repository is not None:
            repository.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
