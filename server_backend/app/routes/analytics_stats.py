from math import isfinite

from flask import Blueprint, jsonify, request

from app.utility.analytics.stats_engine import describe, independent_ttest, one_way_anova


bp = Blueprint("analytics_stats", __name__)


@bp.post("/api/stats/describe")
def describe_sample():
    """Summarize pasted numbers without reading or modifying study data."""
    payload = request.get_json(silent=True)
    if isinstance(payload, dict) and "samples" in payload:
        return describe_groups(payload)
    text = payload.get("values") if isinstance(payload, dict) else None
    if not isinstance(text, str):
        return jsonify(error="Enter numbers separated by commas or whitespace."), 400
    if len(text) > 100_000:
        return jsonify(error="Enter at most 100,000 characters."), 400

    try:
        # Splitting on whitespace also accepts lines and tab-separated values.
        values = [float(token) for token in text.replace(",", " ").split()]
        if not values or not all(map(isfinite, values)):
            raise ValueError("Expected finite values")
        result = describe(values)
    except ValueError:
        return jsonify(error="Enter at least one number and use only finite numbers."), 400
    except OverflowError:
        return jsonify(error="These numbers are too large to summarize."), 400
    if any(isinstance(value, float) and not isfinite(value) for value in result.values()):
        return jsonify(error="These numbers are too large to summarize."), 400

    return jsonify(result)


def describe_groups(payload):
    samples = payload["samples"]
    test = payload.get("test")
    if not isinstance(samples, list) or not 1 <= len(samples) <= 500:
        return jsonify(error="Provide between 1 and 500 samples."), 400
    if not all(isinstance(sample, list) and sample for sample in samples):
        return jsonify(error="Every sample must contain numeric values."), 400
    if sum(map(len, samples)) > 50_000:
        return jsonify(error="Provide at most 50,000 values."), 400
    if test not in (None, "welch", "anova"):
        return jsonify(error="Choose a supported comparison test."), 400
    if test == "welch" and len(samples) != 2:
        return jsonify(error="Welch’s t-test requires two groups."), 400
    if test == "anova" and len(samples) < 2:
        return jsonify(error="One-way ANOVA requires at least two groups."), 400
    try:
        if not all(type(value) in (float, int) and isfinite(value) for sample in samples for value in sample):
            raise ValueError("Samples must contain only finite numbers.")
        summaries = [describe(sample) for sample in samples]
        if any(isinstance(value, float) and not isfinite(value)
               for summary in summaries for value in summary.values()):
            raise OverflowError
        comparison = None
        if test == "welch":
            comparison = independent_ttest(*samples)
            comparison["mean_difference"] = summaries[0]["mean"] - summaries[1]["mean"]
            if not isfinite(comparison["mean_difference"]):
                raise OverflowError
        if test == "anova":
            comparison = one_way_anova(*samples)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OverflowError:
        return jsonify(error="These numbers are too large to summarize."), 400
    return jsonify(summaries=summaries, comparison=comparison)
