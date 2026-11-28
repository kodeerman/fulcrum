from collections import Counter
from math import isfinite, isnan, sqrt
from statistics import mean, median, quantiles, variance


def _numeric_values(values):
    """Drop missing data and convert array scalars to Python numbers."""
    numbers = []
    for value in values:
        if value is None:
            continue
        number = float(value)
        if isnan(number):
            continue
        # Infinity cannot be represented in a strict JSON response.
        if not isfinite(number):
            raise ValueError("Values must be finite")
        numbers.append(number)

    if not numbers:
        raise ValueError("At least one numeric value is required")
    return numbers


def _modes(numbers):
    """Return all repeated values tied for the highest frequency."""
    counts = Counter(numbers)
    highest_frequency = max(counts.values())
    if highest_frequency == 1:
        return []
    return sorted(number for number, count in counts.items() if count == highest_frequency)


def describe(values):
    """Summarize one numeric sample using JSON-safe Python values."""
    numbers = _numeric_values(values)
    n = len(numbers)
    minimum = min(numbers)
    maximum = max(numbers)

    # Sample variance divides by n - 1. A single value has no sample variance.
    sample_variance = variance(numbers) if n > 1 else None
    standard_deviation = sqrt(sample_variance) if sample_variance is not None else None

    # Inclusive quartiles interpolate at positions 0.25 and 0.75 times (n - 1).
    q1, _, q3 = quantiles(numbers, method="inclusive") if n > 1 else (minimum,) * 3

    return {
        "n": n,
        "mean": mean(numbers),
        "median": median(numbers),
        "min": minimum,
        "max": maximum,
        "range": maximum - minimum,
        "variance": sample_variance,
        "std": standard_deviation,
        "mode": _modes(numbers),
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
    }


def mode(values):
    """Return the sorted modes of one numeric sample."""
    return _modes(_numeric_values(values))


def _sample(values, minimum=2):
    numbers = _numeric_values(values)
    if len(numbers) < minimum:
        raise ValueError(f"At least {minimum} numeric values are required per sample.")
    return numbers


def _pairs(a, b, minimum):
    if len(a) != len(b):
        raise ValueError("Paired inputs must have the same length.")
    pairs = [
        (x, y) for x, y in zip(a, b)
        if x is not None and y is not None and not isnan(float(x)) and not isnan(float(y))
    ]
    if len(pairs) < minimum:
        raise ValueError(f"At least {minimum} complete pairs are required.")
    x, y = zip(*pairs)
    return _numeric_values(x), _numeric_values(y)


def _finite(value):
    return float(value) if isfinite(value) else None


def _t_result(result, difference):
    statistic = _finite(result.statistic)
    interval = result.confidence_interval() if statistic is not None else None
    return {
        "t_stat": statistic,
        "p_value": _finite(result.pvalue) if statistic is not None else None,
        "df": _finite(result.df),
        "mean_difference": _finite(difference),
        "ci_low": _finite(interval.low) if interval else None,
        "ci_high": _finite(interval.high) if interval else None,
    }


def one_sample_ttest(values, popmean):
    from scipy import stats

    if not isfinite(popmean):
        raise ValueError("The reference mean must be finite.")
    sample = _sample(values)
    return _t_result(stats.ttest_1samp(sample, popmean), mean(sample) - popmean)


def independent_ttest(a, b, equal_var=False):
    from scipy import stats

    a, b = _sample(a), _sample(b)
    difference = mean(a) - mean(b)
    if min(a) == max(a) and min(b) == max(b):
        return {
            "t_stat": None,
            "p_value": None,
            "df": None,
            "mean_difference": _finite(difference),
            "ci_low": None,
            "ci_high": None,
        }
    return _t_result(stats.ttest_ind(a, b, equal_var=equal_var), difference)


def paired_ttest(a, b):
    from scipy import stats

    a, b = _pairs(a, b, 2)
    differences = [first - second for first, second in zip(a, b)]
    if not all(map(isfinite, differences)):
        raise ValueError("The differences are too large to compare.")
    return {
        **_t_result(stats.ttest_rel(a, b), mean(differences)),
        "pairs": len(differences),
    }


def one_way_anova(*groups):
    from scipy import stats

    if len(groups) < 2:
        raise ValueError("At least two groups are required.")
    samples = [_sample(group) for group in groups]
    result = stats.f_oneway(*samples)
    return {
        "f_stat": _finite(result.statistic),
        "p_value": _finite(result.pvalue) if isfinite(result.statistic) else None,
        "df_between": len(samples) - 1,
        "df_within": sum(map(len, samples)) - len(samples),
    }


def linear_fit(x, y):
    from scipy import stats

    x, y = _pairs(x, y, 3)
    if min(x) == max(x):
        raise ValueError("The predictor needs nonzero variance.")
    result = stats.linregress(x, y)
    return {
        "slope": _finite(result.slope),
        "intercept": _finite(result.intercept),
        "r": _finite(result.rvalue),
        "r_squared": _finite(result.rvalue ** 2),
        "p_value": _finite(result.pvalue),
        "std_err": _finite(result.stderr),
        "n": len(x),
    }


def normality_test(values, alpha=0.05):
    from scipy import stats

    if not 0 < alpha < 1:
        raise ValueError("Alpha must be between zero and one.")
    sample = _sample(values, 3)
    if min(sample) == max(sample):
        raise ValueError("The sample needs nonzero variance.")
    result = stats.shapiro(sample)
    return {
        "statistic": _finite(result.statistic),
        "p_value": _finite(result.pvalue),
        "is_normal": bool(result.pvalue >= alpha),
    }


def normal_fit(values, n_points=100):
    import numpy as np
    from scipy import stats

    sample = _sample(values)
    center, std = mean(sample), sqrt(variance(sample))
    if std == 0 or n_points < 2:
        raise ValueError("The curve requires nonzero variance and at least two points.")
    x = np.linspace(center - 4 * std, center + 4 * std, n_points)
    return {
        "mean": center,
        "std": std,
        "x": [_finite(value) for value in x],
        "pdf": [_finite(value) for value in stats.norm.pdf(x, loc=center, scale=std)],
    }


def histogram(values, bins=10):
    import numpy as np

    sample = _numeric_values(values)
    counts, edges = np.histogram(sample, bins=bins)
    density = counts / len(sample) / np.diff(edges)
    return {
        "edges": [_finite(edge) for edge in edges],
        "counts": counts.tolist(),
        "density": [_finite(value) for value in density],
    }
