"""Strict decoding: an unreadable file must never silently change the dictionary."""
from pathlib import Path
from .text_finder import define_path, find_all_texts


def iter_text_chunks(filepath, encoding="utf-8-sig", chunk_size=65536):
    if chunk_size <= 0:
        raise ValueError("Размер блока должен быть положительным")
    with Path(filepath).open(encoding=encoding) as source:
        while chunk := source.read(chunk_size):
            yield chunk


def load_from_folder(folderpath=None, encoding="utf-8-sig"):
    """Compatibility helper; large corpora should use iter_text_chunks instead."""
    return ["".join(iter_text_chunks(p, encoding)) for p in find_all_texts(folderpath)]
