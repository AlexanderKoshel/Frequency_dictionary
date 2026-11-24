"""Build one DOCX from completed English and Russian RGR 2 runs."""

import argparse
import json
from pathlib import Path

from report import HEADINGS, LANGUAGES, MODES, contents, cover, figure, number, setup_document, table


CONTINUATION = "Задание 3. Русский корпус"


def count_text(value):
    return f"{value:,}".replace(",", "\u00a0")


def read_summary(folder, language):
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    if summary["language"] != language:
        raise ValueError(f"Ожидался результат для {language}: {folder}")
    return summary


def dictionary_rows(summaries):
    for summary in summaries:
        language = LANGUAGES[summary["language"]]
        for mode, key in zip(MODES, ("forms", "lemmas")):
            yield language, mode, summary["variants"][key]


def dataset_overview(doc, summaries, source):
    doc.add_paragraph("Корпуса обработаны раздельно. Для каждого построены словарь "
                      "словоформ и словарь лемм. Объёмы и размеры словарей приведены в таблице 1.")
    rows = [
        (LANGUAGES[s["language"]], count_text(s["tokens"]),
         count_text(s["variants"]["forms"]["unique"]), count_text(s["variants"]["lemmas"]["unique"]))
        for s in summaries
    ]
    table(doc, "Таблица 1 — Корпуса и размеры словарей",
          ("Язык", "Словоупотребления", "Словоформы", "Леммы"), rows, (3.8, 4.8, 4.2, 4.2))
    doc.add_paragraph(source)
    doc.add_paragraph("При токенизации учтён алфавит выбранного языка, регистр приведён "
                      "к нижнему. Для английского использована библиотека Simplemma, для "
                      "русского — pymorphy3. Лемматизация объединяет частоты словоформ "
                      "и сохраняет число словоупотреблений.")


def comparison_figures(doc, runs, image, start, subject):
    for index, (folder, summary) in enumerate(runs, start):
        language = LANGUAGES[summary["language"]].lower()
        figure(doc, folder / f"{image}.png", f"Рисунок {index} — {subject}, {language}", width=12)


def rank_comparison(doc, runs):
    doc.add_heading(HEADINGS[0].upper(), 1)
    doc.add_paragraph("Постановка. Проверить зависимость f × r = c в обоих корпусах.")
    doc.add_paragraph("Решение. Ранги назначены по убыванию абсолютной частоты f. "
                      "При равной частоте порядок лексикографический. c оценено медианой "
                      "произведений f × r. На рисунках 1 и 2 наблюдения сопоставлены с c/r.")
    comparison_figures(doc, runs, "zipf", 1, "Частота и ранг")
    rows = []
    any_variation = False
    for language, mode, entry in dictionary_rows(summary for _, summary in runs):
        fit = entry["zipf"]
        any_variation |= fit["max_product"] != fit["min_product"]
        quartiles = f"{number(fit['q1'], 0)}–{number(fit['q3'], 0)}"
        rows.append((language, mode, number(fit["c"], 1), quartiles, number(fit["log_slope"], 3)))
    doc.add_paragraph("В таблице 2 указаны коэффициент, средние 50 % произведений "
                      "f × r и наклон графика в логарифмическом масштабе.")
    table(doc, "Таблица 2 — Показатели закона Ципфа",
          ("Язык", "Словарь", "c", "Q1–Q3", "Наклон"), rows, (3.1, 3.1, 2.8, 5.1, 2.9))
    if any_variation:
        doc.add_paragraph("В исследованных словарях произведение f × r варьируется. "
                          "Для точной модели оно постоянно, а наклон равен −1.")


def length_comparison(doc, runs):
    doc.add_heading(HEADINGS[1].upper(), 1)
    doc.add_paragraph("Постановка. Проверить связь длины и частоты служебных слов.")
    doc.add_paragraph("Решение. Слова отобраны по спискам для каждого языка. Длина L "
                      "измерена в буквах. На рисунках 3 и 4 показаны частоты и модель k/L, "
                      "где k — медиана f × L. В таблице 3 приведён коэффициент Спирмена ρ.")
    comparison_figures(doc, runs, "length", 3, "Длина и частота")
    rows = []
    rhos = []
    exact = []
    for language, mode, entry in dictionary_rows(summary for _, summary in runs):
        length = entry["length"]
        fit = length["fit"]
        spread = "—" if fit is None else f"{fit['min_product']}–{fit['max_product']}"
        rows.append((language, mode, length["words"], spread, number(length["spearman"], 3)))
        rhos.append(length["spearman"])
        exact.append(fit is not None and fit["min_product"] == fit["max_product"])
    table(doc, "Таблица 3 — Связь длины и частоты служебных слов",
          ("Язык", "Словарь", "Слов", "Диапазон f × L", "ρ"), rows, (3.3, 3.2, 2.0, 5.1, 3.4))
    if all(rho is not None and rho < 0 for rho in rhos):
        doc.add_paragraph("Во всех четырёх словарях короткие служебные слова в среднем "
                          "встречаются чаще, согласно знаку коэффициента Спирмена.")
    else:
        doc.add_paragraph("Отрицательные значения ρ указывают на тенденцию к меньшей "
                          "частоте у более длинных служебных слов.")
    if not any(exact):
        doc.add_paragraph("Произведение f × L меняется. Точная обратная пропорциональность "
                          "для исследованных списков не подтверждается.")


def dispersion(doc, en, ru):
    doc.add_heading(HEADINGS[2].upper(), 1)
    doc.add_paragraph("Постановка. Оценить равномерность употребления каждой единицы "
                      "по сегментам её корпуса.")
    doc.add_paragraph("Решение. Корпус делится на n почти равных последовательных сегментов "
                      "по числу словоупотреблений. Для относительных частот по сегментам "
                      "вычислены среднее μ и стандартное отклонение σ. Использована формула "
                      "D = 100 × (1 − σ / (μ × √(n − 1))). В расчёте участвуют все сегменты, "
                      "включая те, где частота равна нулю. При равномерном распределении "
                      "D = 100, при концентрации в одном сегменте D ≈ 0.")
    for summary in (en, ru):
        sizes = ", ".join(count_text(size) for size in summary["segment_sizes"])
        language = LANGUAGES[summary["language"]]
        doc.add_paragraph(f"{language} корпус. Размеры сегментов — {sizes}.")
    doc.add_paragraph("IPM — число употреблений на миллион слов всего корпуса. "
                      "В таблицах 4–7 показаны начала словарей. Полные расчёты "
                      "сохранены в CSV для каждого языка.")
    for index, summary in enumerate((en, ru)):
        if index:
            doc.add_heading(CONTINUATION.upper(), 1)
            doc.add_paragraph("В таблицах 6 и 7 приведены пять первых позиций русских "
                              "словарей. Метод сегментации и формула те же.")
        language = LANGUAGES[summary["language"]].lower()
        for j, (_, mode, entry) in enumerate(dictionary_rows([summary])):
            rows = [
                (word, number(ipm), rank, number(d))
                for word, ipm, rank, d in entry["top_dispersion"]
            ]
            table(doc, f"Таблица {4 + 2 * index + j} — {mode}, {language} корпус",
                  ("Слово", "IPM", "Ранг", "D"), rows, (5.2, 4.0, 3.5, 4.3))
    doc.add_paragraph("Лемматизация меняет состав словарей, поэтому ранги и D следует "
                      "сравнивать с учётом того, какие формы объединены. D описывает "
                      "распределение по сегментам конкретного корпуса.")


def combine(en_folder, ru_folder, output, author, source):
    en = read_summary(en_folder, "en")
    ru = read_summary(ru_folder, "ru")
    runs = ((en_folder, en), (ru_folder, ru))
    doc = setup_document(author[0])
    cover(doc, author)
    contents(doc, (*HEADINGS, CONTINUATION))
    dataset_overview(doc, (en, ru), source)
    rank_comparison(doc, runs)
    length_comparison(doc, runs)
    dispersion(doc, en, ru)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)


def main():
    parser = argparse.ArgumentParser(description="Собрать единый отчёт РГР по английскому и русскому")
    parser.add_argument("--en", type=Path, required=True, help="Каталог результатов английского прогона")
    parser.add_argument("--ru", type=Path, required=True, help="Каталог результатов русского прогона")
    parser.add_argument("--out", type=Path, default=Path("out/RGR2_EN_RU.docx"))
    parser.add_argument("--author", default="ФИО")
    parser.add_argument("--course", default="___")
    parser.add_argument("--group", default="___")
    parser.add_argument("--source", default="Входные данные — исходные тексты в формате TXT.")
    args = parser.parse_args()
    try:
        combine(args.en, args.ru, args.out, (args.author, args.course, args.group), args.source)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Ошибка: {error}\n")
    print(f"Общий отчёт сохранён: {args.out.resolve()}")


if __name__ == "__main__":
    main()
