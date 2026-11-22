"""Word forms, without stemming; retain internal hyphens and apostrophes."""
import re
import unicodedata

LANGUAGES = {"ru": "Русский", "en": "English", "be": "Беларуская"}
ALPHABETS = {"ru": "а-яё", "en": "a-z",
             "be": "абвгдеёжзійклмнопрстуўфхцчшыьэюя"}
TRANSLATION = str.maketrans({"’": "'", "ʼ": "'", "‘": "'", "‐": "-", "‑": "-"})
CANDIDATE = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*", re.UNICODE)


def normalize(text):
    return unicodedata.normalize("NFC", text).lower().translate(TRANSLATION)


def word_pattern(language):
    if language not in LANGUAGES:
        raise ValueError(f"Неизвестный язык: {language}")
    letters = ALPHABETS[language]
    return re.compile(f"[{letters}]+(?:[-'][{letters}]+)*")


def tokenize(text, language):
    pattern = word_pattern(language)
    for match in CANDIDATE.finditer(normalize(text)):
        word = match.group()
        # Reject mixed alphabets instead of importing fragments of foreign words.
        if pattern.fullmatch(word):
            yield word


def validate_word(word, language):
    word = normalize(word.strip())
    if not word_pattern(language).fullmatch(word):
        raise ValueError("Введите одно слово на выбранном языке")
    return word


def iter_words(chunks, language):
    """Carry the final token across read boundaries (including combining marks)."""
    pending = ""
    for chunk in chunks:
        text = pending + chunk
        split = len(text)
        while split and (text[split - 1].isalpha() or
                         unicodedata.category(text[split - 1]).startswith("M") or
                         text[split - 1] in "-'’ʼ‘‐‑"):
            split -= 1
        yield from tokenize(text[:split], language)
        pending = text[split:]
    yield from tokenize(pending, language)
