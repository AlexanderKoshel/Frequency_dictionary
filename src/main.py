from parser import text_loader

def main():
    loaded_texts : list[str] = text_loader.load_from_folder()

    if loaded_texts is None:
        raise Exception("Failed to load texts: no data was returned")
    else:
        for text in loaded_texts:
            print(text)

    return 0

if __name__ == '__main__': 
    main()