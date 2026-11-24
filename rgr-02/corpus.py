from collections import Counter, defaultdict
from hashlib import file_digest
from itertools import islice
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "work-01"))
from src.parser.text_finder import find_all_texts
from src.parser.text_loader import iter_text_chunks
from src.parser.tokenizer import iter_words, normalize, word_pattern


FUNCTION_WORDS = {
    "en": """
        the a an and or but nor yet so if because although though while whereas whether
        unless since until when than as that after before about above across against
        along among around at behind below beneath beside between beyond by despite
        down during except for from in inside into near of off on onto out outside over
        past per through throughout to toward towards under underneath upon with within
        without not even only just also too
    """,
    "ru": """
        в во на с со к ко по из из-за из-под от о об обо до для за у без над под перед
        при через между около вокруг кроме после ради против сквозь вдоль среди
        и а но да или либо зато однако чтобы чтоб потому поскольку если хотя пока
        будто словно точно чем как что не ни бы б же ж ли ль ведь вот вон даже лишь
        только именно разве неужели уж всё-таки пусть пускай
    """,
    "be": """
        у ў на з са да па ад аб пра для за без над пад перад пры праз паміж каля
        вакол пасля акрамя дзеля супраць уздоўж сярод і ды а але ці або альбо затое
        каб бо калі хоць пакуль нібы быццам чым як што не ні бы б жа ж вось вунь
        нават толькі менавіта няўжо няхай
    """,
}


def digest(path):
    with path.open("rb") as source:
        return file_digest(source, "sha256").hexdigest()


def sources(corpus):
    paths = find_all_texts(corpus) if corpus.is_dir() else [corpus]
    unique = {}
    for path in paths:
        unique.setdefault(digest(path), path)
    if not unique:
        raise ValueError("TXT-файлы не найдены")
    return [(path, checksum) for checksum, path in unique.items()]


def tokens(files, language, encoding):
    for path, checksum in files:
        yield from iter_words(iter_text_chunks(path, encoding), language)
        if digest(path) != checksum:
            raise ValueError(f"Файл изменился во время расчёта: {path}")


def segment_counts(files, first_pass, language, encoding, parts):
    total = first_pass.total()
    if not 2 <= parts <= total:
        raise ValueError(f"Нужно от 2 до {total} непустых сегментов, получено {parts}")
    size, remainder = divmod(total, parts)
    sizes = [size + (index < remainder) for index in range(parts)]
    words = iter(tokens(files, language, encoding))
    segments = [Counter(islice(words, size)) for size in sizes]
    if next(words, None) is not None or any(segment.total() != size for segment, size in zip(segments, sizes)):
        raise ValueError("Число слов изменилось между проходами")
    return sizes, segments


def belarusian_lexicon(path):
    pattern = word_pattern("be")
    variants = defaultdict(Counter)
    with path.open(encoding="utf-8-sig") as source:
        for line in source:
            columns = line.rstrip("\r\n").split("\t")
            if len(columns) != 10 or not columns[0].isdigit():
                continue
            word, lemma = (normalize(value) for value in columns[1:3])
            if pattern.fullmatch(word) and pattern.fullmatch(lemma):
                variants[word][lemma] += 1
    if not variants:
        raise ValueError("В CoNLL-U не найдено белорусских слов с леммами")
    return {
        word: min(counts, key=lambda lemma: (-counts[lemma], lemma))
        for word, counts in variants.items()
    }


def lemmatize_types(words, language, belarusian_data):
    if language == "en":
        from simplemma import lemmatize

        def lookup(word):
            return lemmatize(word, lang="en")

    elif language == "ru":
        from pymorphy3 import MorphAnalyzer

        analyzer = MorphAnalyzer(lang="ru")

        def lookup(word):
            return analyzer.parse(word)[0].normal_form

    else:
        if belarusian_data is None:
            raise ValueError("Для be нужен --be-lexicon с белорусским файлом CoNLL-U")
        lexicon = belarusian_lexicon(belarusian_data)

        def lookup(word):
            return lexicon.get(word, word)

    lemmas = {}
    pattern = word_pattern(language)
    for word in words:
        lemma = normalize(lookup(word))
        lemmas[word] = lemma if pattern.fullmatch(lemma) else word
    return lemmas


def lemmatized_segments(segments, lemmas):
    for segment in segments:
        counts = Counter()
        for word, frequency in segment.items():
            counts[lemmas[word]] += frequency
        yield counts


def function_word_list(language, path):
    source = FUNCTION_WORDS[language] if path is None else path.read_text(encoding="utf-8-sig")
    words = set(normalize(source).split())
    if not words or not all(map(word_pattern(language).fullmatch, words)):
        raise ValueError("Список служебных слов должен содержать отдельные слова выбранного языка")
    return words
