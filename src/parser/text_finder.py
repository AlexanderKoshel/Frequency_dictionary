"""Find source texts independently of the current working directory."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def define_path():
    return ROOT / "texts"


def find_all_texts(folderpath=None):
    folder = Path(folderpath) if folderpath is not None else define_path()
    if not folder.is_dir():
        raise NotADirectoryError(f"Папка не найдена: {folder}")
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() == ".txt")
