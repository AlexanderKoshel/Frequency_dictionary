from pathlib import Path

def define_path():
    cwd = Path.cwd()
    path = cwd.parent / "texts"
    return path

def find_all_texts(folderpath=None):
    if folderpath == None:
        folderpath = define_path()

    for path in folderpath.rglob("*.txt"):
        return path