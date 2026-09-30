from pathlib import Path

def define_path():
    cwd = Path.cwd()
    path = cwd.parent / "texts"
    return path
        
def load_from_folder(folderpath=None):
    if folderpath == None:
        folderpath = define_path()

    text_list = []

    try:
        for filepath in folderpath.rglob("*.txt"):
            with open(filepath) as textfile:
                text = textfile.read()
                text_list.append(text)
        
    except Exception as e:
        return f"Error with reading the {filepath.name} in {Path(filepath.parent)}: {e}"

    return text_list