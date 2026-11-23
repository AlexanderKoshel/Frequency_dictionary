import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from corpus import (
    digest, function_word_list, lemmatize_types, lemmatized_segments, segment_counts,
    sources, tokens,
)
from report import plots, write_report
from statistics_rgr import dictionary, dispersion_rows, fit_reciprocal, length_rows, length_statistics


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)


def analyze(language, corpus, encoding, parts, be_lexicon, function_words, out,
            author_info=("ФИО", "___", "___")):
    files = sources(corpus)
    forms = Counter(tokens(files, language, encoding))
    sizes, form_segments = segment_counts(files, forms, language, encoding, parts)
    lemmas = lemmatize_types(forms, language, be_lexicon)
    lemma_segments = list(lemmatized_segments(form_segments, lemmas))
    allowed_forms = function_word_list(language, function_words)
    allowed_lemmas = {lemmas[word] for word in allowed_forms & forms.keys()}

    if sum(form_segments, Counter()) != forms:
        raise ValueError("Частоты изменились между проходами")

    out.mkdir(parents=True, exist_ok=True)
    summary = {
        "language": language,
        "files": [
            {"name": path.relative_to(corpus).as_posix() if corpus.is_dir() else path.name,
             "sha256": checksum}
            for path, checksum in files
        ],
        "encoding": encoding,
        "segment_sizes": sizes,
        "tokens": forms.total(),
        "function_words": sorted(allowed_forms),
        "changed_forms": sum(word != lemma for word, lemma in lemmas.items()),
        "variants": {},
    }
    if be_lexicon is not None:
        summary["be_lexicon_sha256"] = digest(be_lexicon)

    plot_data = []
    for mode, segments, allowed in (
        ("forms", form_segments, allowed_forms),
        ("lemmas", lemma_segments, allowed_lemmas),
    ):
        entries = dictionary(segments)
        lengths = length_rows(entries, allowed)
        _, counts, ranks = zip(*entries)
        zipf = fit_reciprocal(ranks, counts)
        length = length_statistics(lengths)
        write_csv(out / f"zipf-{mode}.csv", ("word", "frequency", "rank", "frequency_x_rank"),
                  ((word, f, r, f * r) for word, f, r in entries))
        write_csv(out / f"length-{mode}.csv", ("word", "letters", "frequency", "frequency_x_length"),
                  ((word, letters, f, f * letters) for word, letters, f in lengths))
        dispersion = list(dispersion_rows(entries, segments, sizes))
        write_csv(out / f"dispersion-{mode}.csv", ("word", "ipm", "rank", "D"), dispersion)
        summary["variants"][mode] = {
            "unique": len(entries), "zipf": zipf, "length": length,
            "top_dispersion": dispersion[:5],
        }
        plot_data.append((ranks, counts, lengths, zipf, length))

    plots(out, plot_data)
    write_report(out, summary, author_info)
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description="Закон Ципфа и коэффициент Жуйана")
    parser.add_argument("language", choices=("en", "ru", "be"))
    parser.add_argument("corpus", type=Path, help="TXT-файл или папка с текстами")
    parser.add_argument("--encoding", default="utf-8-sig")
    parser.add_argument("--parts", type=int, default=4)
    parser.add_argument("--be-lexicon", type=Path, help="Файл CoNLL-U с белорусской разметкой")
    parser.add_argument("--function-words", type=Path, help="Список служебных слов в UTF-8")
    parser.add_argument("--out", type=Path, help="Каталог результатов (по умолчанию out/<язык>)")
    parser.add_argument("--author", default="ФИО", help="ФИО для титульного листа")
    parser.add_argument("--course", default="___", help="Курс для титульного листа")
    parser.add_argument("--group", default="___", help="Группа для титульного листа")
    args = parser.parse_args()
    out = args.out or Path("out") / args.language
    if args.be_lexicon is not None and args.language != "be":
        parser.error("--be-lexicon используется только для be")
    try:
        analyze(args.language, args.corpus, args.encoding, args.parts, args.be_lexicon,
                args.function_words, out, (args.author, args.course, args.group))
    except (OSError, ValueError, LookupError) as error:
        parser.exit(1, f"Ошибка: {error}\n")
    print(f"Результаты сохранены: {out.resolve()}")


if __name__ == "__main__":
    main()
