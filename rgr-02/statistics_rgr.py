from collections import Counter
from math import isclose, log, sqrt
from statistics import correlation, linear_regression, median, pstdev, quantiles, StatisticsError


def dictionary(segments):
    counts = sum(segments, Counter())
    entries = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [(word, frequency, rank) for rank, (word, frequency) in enumerate(entries, 1)]


def fit_reciprocal(x, y):
    products = [a * b for a, b in zip(x, y)]
    c = median(products)
    quartiles = quantiles(products, method="inclusive") if len(products) >= 2 else [c] * 3
    if len(set(x)) < 2:
        slope = None
    else:
        slope = linear_regression(list(map(log, x)), list(map(log, y))).slope
    return {
        "c": c,
        "q1": quartiles[0],
        "q3": quartiles[2],
        "min_product": min(products),
        "max_product": max(products),
        "log_slope": slope,
    }


def length_rows(entries, allowed):
    return [
        (word, sum(letter.isalpha() for letter in word), frequency)
        for word, frequency, _ in entries if word in allowed
    ]


def tied_ranks(values):
    counts = Counter(values)
    first = 1
    ranks = {}
    for value, count in sorted(counts.items()):
        ranks[value] = first + (count - 1) / 2
        first += count
    return [ranks[value] for value in values]


def length_statistics(rows):
    if not rows:
        return {"words": 0, "spearman": None, "fit": None}
    _, lengths, frequencies = zip(*rows)
    try:
        rho = correlation(tied_ranks(lengths), tied_ranks(frequencies))
    except StatisticsError:
        rho = None
    return {"words": len(rows), "spearman": rho, "fit": fit_reciprocal(lengths, frequencies)}


def juilland(frequencies):
    mean = sum(frequencies) / len(frequencies)
    result = 100 * (1 - pstdev(frequencies, mu=mean) / (mean * sqrt(len(frequencies) - 1)))
    return 0.0 if isclose(result, 0, abs_tol=1e-10) else result


def dispersion_rows(entries, segments, sizes):
    total = sum(sizes)
    for word, frequency, rank in entries:
        rates = [segment[word] / size for segment, size in zip(segments, sizes)]
        yield word, frequency * 1_000_000 / total, rank, juilland(rates)
