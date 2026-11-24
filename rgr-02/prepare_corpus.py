import argparse
import csv
from pathlib import Path
from tempfile import TemporaryDirectory

import fsspec
from pyarrow.parquet import ParquetFile

from corpus import iter_words


REVISION = "b04c8d1ceb2f5cd4588862100d08de323dccfbaa"
DATASET = f"https://huggingface.co/datasets/wikimedia/wikipedia/resolve/{REVISION}"
SHARDS = {
    "en": ("train-00000-of-00041.parquet", 420_296_449),
    "ru": ("train-00000-of-00021.parquet", 581_024_230),
    "be": ("train-00000-of-00002.parquet", 167_751_354),
}


def prepare(language, target, root, exclude_domains):
    name, size = SHARDS[language]
    url = f"{DATASET}/20231101.{language}/{name}"
    destination = root / language
    destination.mkdir(parents=True, exist_ok=True)
    filesystem = fsspec.filesystem("https", client_kwargs={"trust_env": True})
    total = 0
    reported_millions = 0
    seen = set()

    with TemporaryDirectory(dir=root) as tmp:
        corpus_path = Path(tmp) / "wikipedia.txt"
        attribution_path = Path(tmp) / "sources.csv"
        with (
            filesystem.open(url, "rb", size=size, block_size=1024 * 1024) as source,
            corpus_path.open("w", encoding="utf-8", newline="\n") as output,
            attribution_path.open("w", encoding="utf-8", newline="") as attribution,
        ):
            table = ParquetFile(source)
            writer = csv.writer(attribution)
            writer.writerow(("id", "title", "url", "tokens"))
            for batch in table.iter_batches(batch_size=256, columns=["id", "title", "url", "text"]):
                for article in batch.to_pylist():
                    if exclude_domains and article["title"].startswith("."):
                        continue
                    content = article["text"].strip().replace("\r\n", "\n").replace("\r", "\n")
                    count = sum(1 for _ in iter_words((content,), language))
                    if not count or article["id"] in seen:
                        continue
                    seen.add(article["id"])
                    output.write(content + "\n\n")
                    writer.writerow((article["id"], article["title"], article["url"], count))
                    total += count
                    if total // 1_000_000 > reported_millions:
                        reported_millions = total // 1_000_000
                        print(f"{language}: {total:_} словоупотреблений", flush=True)
                    if total >= target:
                        break
                if total >= target:
                    break

        if total < target:
            raise ValueError(f"{language}: доступно {total:_} из {target:_} запрошенных словоупотреблений")
        attribution_path.replace(destination / attribution_path.name)
        corpus_path.replace(destination / corpus_path.name)

    print(f"{language}: {total:_} словоупотреблений, {len(seen):_} статей → {destination}")


def main():
    parser = argparse.ArgumentParser(description="Подготовить корпус из статей Википедии")
    parser.add_argument("languages", nargs="+", choices=tuple(SHARDS))
    parser.add_argument("--words", type=int, default=5_000_000, help="Минимум токенов на язык")
    parser.add_argument("--out", type=Path, default=Path("data/corpora"))
    parser.add_argument("--exclude-domain-pages", action="store_true", help="Пропустить статьи о доменных зонах")
    args = parser.parse_args()
    if args.words < 1:
        parser.error("--words должен быть положительным")
    for language in dict.fromkeys(args.languages):
        prepare(language, args.words, args.out, args.exclude_domain_pages)


if __name__ == "__main__":
    main()
