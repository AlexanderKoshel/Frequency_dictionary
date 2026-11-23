import csv
import re
from functools import cache
from itertools import chain
from pathlib import Path

from nltk.corpus import stopwords
from pymorphy3 import MorphAnalyzer
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parent
WORD = re.compile(r"[а-яё]+")
TOKEN_PATTERN = r"(?u)\b\w+\b"
CLASS_NAMES = {0: "отрицательный", 1: "положительный"}


def read_reviews():
    with (ROOT / "reviews.csv").open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    train = [(row["text"], int(row["label"])) for row in rows if row["split"] == "train"]
    test = [(row["text"], int(row["label"])) for row in rows if row["split"] == "test"]
    return train, test


def tokenize(text):
    return WORD.findall(text.lower())


def make_normalizer():
    try:
        stop_words = set(stopwords.words("russian")) - {"не", "ни", "нет"}
    except LookupError:
        raise SystemExit("Загрузите стоп-слова командой: python -m nltk.downloader stopwords")

    analyzer = MorphAnalyzer(lang="ru")

    @cache
    def lemma(word):
        return analyzer.parse(word)[0].normal_form

    def normalize(text):
        return " ".join(lemma(word) for word in tokenize(text) if word not in stop_words)

    return normalize


def show_matrix(names, matrix, train_size):
    lines = [
        "Указаны ненулевые элементы. Все остальные координаты равны нулю.",
        "",
        "| Отзыв | Ненулевые координаты вектора |",
        "|---|---|",
    ]
    for index, row in enumerate(matrix):
        if index < train_size:
            title = f"Обучение {index + 1}"
        else:
            title = f"Тест {index - train_size + 1}"
        weights = ", ".join(
            f"{names[column]}={value:.3g}" for column, value in sorted(zip(row.indices, row.data))
        )
        lines.append(f"| {title} | {weights or '—'} |")
    return lines


def run_experiment(title, prepare, train, test):
    train_texts = [prepare(text) for text, _ in train]
    train_labels = [label for _, label in train]
    test_texts = [prepare(text) for text, _ in test]
    test_labels = [label for _, label in test]
    methods = (
        ("One-Hot", CountVectorizer(binary=True, token_pattern=TOKEN_PATTERN)),
        ("TF", CountVectorizer(token_pattern=TOKEN_PATTERN)),
        ("TF-IDF", TfidfVectorizer(token_pattern=TOKEN_PATTERN, norm="l2", smooth_idf=True)),
    )
    lines = [f"## {title}", ""]
    predictions = []
    for method, vectorizer in methods:
        features = vectorizer.fit_transform(train_texts)
        test_features = vectorizer.transform(test_texts)
        model = LogisticRegression(max_iter=1000)
        model.fit(features, train_labels)
        predicted = model.predict(test_features)
        positive_index = list(model.classes_).index(1)
        probabilities = model.predict_proba(test_features)[:, positive_index]
        predictions.append(list(zip(predicted, probabilities)))
        vocabulary = vectorizer.get_feature_names_out()
        lines.extend([
            f"### {method}",
            "",
            f"Словарь ({len(vocabulary)} слов): " + ", ".join(vocabulary) + ".",
            "",
            f"Матрица обучения: {features.shape[0]} × {features.shape[1]}.",
            "",
            *show_matrix(vocabulary, chain(features, test_features), len(train)),
            "",
        ])

    lines.extend([
        "### Сравнение предсказаний",
        "",
        "В каждой ячейке указан класс и вероятность положительного класса.",
        "",
        "| Тест | Истинный класс | One-Hot | TF | TF-IDF |",
        "|---|---|---|---|---|",
    ])
    for index, (text, label) in enumerate(test, start=1):
        cells = [
            f"{CLASS_NAMES[predicted]} ({probability:.1%})"
            for predicted, probability in (result[index - 1] for result in predictions)
        ]
        lines.append(f"| {index}. {text} | {CLASS_NAMES[label]} | " + " | ".join(cells) + " |")

    scores = [
        sum(predicted == expected for (predicted, _), expected in zip(result, test_labels))
        for result in predictions
    ]
    summary = ", ".join(
        f"{method} {correct}/{len(test)}" for (method, _), correct in zip(methods, scores)
    )
    lines.extend(["", f"Верно классифицировано: {summary}.", ""])
    print(f"{title}: {summary}")
    return lines


def main():
    train, test = read_reviews()
    normalize = make_normalizer()
    report = [
        "# Результаты лабораторной № 4",
        "",
        f"Учебный набор из {len(train)} обучающих и {len(test)} тестовых отзывов.",
        "Метки 1 и 0 обозначают положительный и отрицательный классы.",
        "",
    ]
    report.extend(run_experiment("Только токенизация", lambda text: " ".join(tokenize(text)), train, test))
    report.extend(run_experiment("Стоп-слова и лемматизация", normalize, train, test))
    path = ROOT / "RESULTS.md"
    path.write_text("\n".join(report), encoding="utf-8")
    print(f"Матрицы и таблицы предсказаний сохранены в {path}")


if __name__ == "__main__":
    main()
