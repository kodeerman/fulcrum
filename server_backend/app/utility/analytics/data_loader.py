#data_loader.py: loads data from the database and returns it in a format suitable for analytics processing in Polar
# Notes:
#>This module does not import Flask or the `app` package. The caller passes the DB cursor in, so tests can use a fake cursor and a temp directory.
# If you, dear reader, intend to extend this in the future, please do NOT impot flask and skip the tests. 
#>Trials come from the `trial` table, NOT from the file list. Some trials have no files at all (participant used another recording method) and still count.
#>Nothing is silently dropped anymore: missing or unreadable files are listed in `StudyData.warnings`.
#>Every duration is in seconds. `duration_s` is the value to analyse; the two sources it is chosen from are kept in `db_duration_s` and `csv_duration_s`.

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Optional
import polars as pl

logger = logging.getLogger(__name__)
DEFAULT_RESULTS_BASE_DIR = "/app/data/participants_results"

#names match measurement_option.measurement_option_name (sql_database/seed_reference_data.sql)
MOUSE_MOVEMENT = "Mouse Movement"
MOUSE_SCROLLS = "Mouse Scrolls"
MOUSE_CLICKS = "Mouse Clicks"
KEYBOARD_INPUTS = "Keyboard Inputs"

#The measurements stored as CSV
CSV_MEASUREMENTS = (MOUSE_MOVEMENT, MOUSE_SCROLLS, MOUSE_CLICKS, KEYBOARD_INPUTS)

#column layout written by local_backend/tracking/utility/file_management.py
_MOUSE_COLUMNS = {
    "Time": pl.Utf8,
    "running_time": pl.Float64,
    "x": pl.Float64,
    "y": pl.Float64,
}
EVENT_SCHEMAS = {
    MOUSE_MOVEMENT: _MOUSE_COLUMNS,
    MOUSE_SCROLLS: _MOUSE_COLUMNS,
    MOUSE_CLICKS: _MOUSE_COLUMNS,
    KEYBOARD_INPUTS: {"Time": pl.Utf8, "running_time": pl.Float64, "keys": pl.Utf8},
}
_NUMERIC_EVENT_COLUMNS = ("running_time", "x", "y")

TRIAL_SCHEMA = {
    "trial_id": pl.Int64,
    "participant_session_id": pl.Int64,
    "participant_id": pl.Int64,
    "task_id": pl.Int64,
    "task_name": pl.Utf8,
    "factor_id": pl.Int64,
    "factor_name": pl.Utf8,
    "started_at": pl.Datetime,
    "ended_at": pl.Datetime,
    "completed": pl.Boolean,
    "attempt": pl.Int64,
    "db_duration_s": pl.Float64,
    "csv_duration_s": pl.Float64,
    "duration_s": pl.Float64,
    "duration_source": pl.Utf8,
}

FILE_SCHEMA = {
    "session_data_instance_id": pl.Int64,
    "trial_id": pl.Int64,
    "participant_session_id": pl.Int64,
    "measurement": pl.Utf8,
    "results_path": pl.Utf8,  #as stored in the database
    "path": pl.Utf8,  #where the file was actually found (None if missing)
}

#trial columns copied onto every telemetry row by StudyData.events()
_EVENT_META_COLUMNS = (
    "trial_id",
    "participant_session_id",
    "participant_id",
    "task_id",
    "task_name",
    "factor_id",
    "factor_name",
    "attempt",
)

# `%s` is the MySQLdb placeholder. `(ps.is_valid = 1 OR %s = 1)` lets the caller
#opt in to sessions flagged invalid.
#you'll never believe who tried to do this in postgres
TRIALS_QUERY = """
SELECT
    tr.trial_id,
    tr.participant_session_id,
    ps.participant_id,
    tr.task_id,
    t.task_name,
    tr.factor_id,
    f.factor_name,
    tr.started_at,
    tr.ended_at
FROM trial tr
INNER JOIN participant_session ps ON ps.participant_session_id = tr.participant_session_id
INNER JOIN task t ON t.task_id = tr.task_id
LEFT JOIN factor f ON f.factor_id = tr.factor_id
WHERE ps.study_id = %s
  AND (ps.is_valid = 1 OR %s = 1)
ORDER BY tr.started_at, tr.trial_id
"""

FILES_QUERY = """
SELECT
    sdi.session_data_instance_id,
    sdi.trial_id,
    tr.participant_session_id,
    mo.measurement_option_name AS measurement,
    sdi.results_path
FROM session_data_instance sdi
INNER JOIN trial tr ON tr.trial_id = sdi.trial_id
INNER JOIN participant_session ps ON ps.participant_session_id = tr.participant_session_id
INNER JOIN measurement_option mo ON mo.measurement_option_id = sdi.measurement_option_id
WHERE ps.study_id = %s
  AND (ps.is_valid = 1 OR %s = 1)
ORDER BY sdi.session_data_instance_id
"""

#helpers (no Polars, no I/O beyond os.path.isfile) [for test reasons]
def query_rows(cursor, sql: str, params: tuple) -> list[dict[str, Any]]:
    """Run a query and return rows as dicts, for tuple or dict cursors alike."""
    cursor.execute(sql, params)
    columns = [d[0] for d in cursor.description]
    return [
        row if isinstance(row, dict) else dict(zip(columns, row))
        for row in cursor.fetchall()
    ]

def db_duration_seconds(
    started_at: Optional[datetime], ended_at: Optional[datetime]
) -> Optional[float]:
    """Wall-clock trial length from the DB timestamps; None if unusable (<= 0 or open)."""
    if started_at is None or ended_at is None:
        return None
    seconds = (ended_at - started_at).total_seconds()
    return seconds if seconds > 0 else None

def choose_duration(
    db_s: Optional[float], csv_s: Optional[float], prefer: str = "csv"
) -> tuple[Optional[float], Optional[str]]:
    """Pick the duration to analyse -> (seconds, "csv" | "db" | None).

    csv_s is the last `running_time` recorded by the tracking agent: finer than the
    DB's one-second timestamps, but it under-reads if the participant sat idle at the
    end of a trial. `prefer` picks which source wins when both exist.
    """
    if prefer not in ("csv", "db"):
        raise ValueError("prefer must be 'csv' or 'db'")
    sources = [("csv", csv_s), ("db", db_s)]
    if prefer == "db":
        sources.reverse()
    for name, value in sources:
        if value is not None and value > 0:
            return value, name
    return None, None

def assign_attempts(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add `attempt`: 1-based repeat count per (participant, task), by start time."""
    order = sorted(
        range(len(records)),
        key=lambda i: (
            records[i]["started_at"] is None,
            records[i]["started_at"] or datetime.min,
            records[i]["trial_id"],
        ),
    )
    counters: dict[tuple, int] = {}
    for i in order:
        key = (records[i]["participant_id"], records[i]["task_id"])
        counters[key] = counters.get(key, 0) + 1
        records[i]["attempt"] = counters[key]
    return records

def resolve_results_path(
    results_path: Optional[str],
    base_dir: str,
    study_id: int,
    participant_session_id: int,
    trial_id: int,
    session_data_instance_id: int,
) -> Optional[str]:
    """Find a stored file on disk, or None.
    The DB stores an absolute path, which goes stale when the results volume moves.
    Fall back to the canonical layout under `base_dir`:
    <study>_study_id/<session>_participant_session_id/<trial>_trial_id/<file>
    """
    if results_path and os.path.isfile(results_path):
        return results_path
    #basename() so an odd DB value can never point the fallback outside base_dir
    filename = (
        os.path.basename(results_path)
        if results_path
        else f"{session_data_instance_id}.csv"
    )
    candidate = os.path.join(
        base_dir,
        f"{study_id}_study_id",
        f"{participant_session_id}_participant_session_id",
        f"{trial_id}_trial_id",
        filename,
    )
    return candidate if os.path.isfile(candidate) else None

def _unreadable_prefix(session_data_instance_id: int) -> str:
    return f"session_data_instance {session_data_instance_id}: could not read"

#CSV reading (Polars)
def _csv_max_running_time(path: str) -> Optional[float]:
    """Largest `running_time` in a CSV, scanning only that column. None if no usable value."""
    value = (
        pl.scan_csv(path, infer_schema_length=0)  # everything as text: no inference surprises
        .select(pl.col("running_time").cast(pl.Float64, strict=False).max())
        .collect()
        .item()
    )
    if value is None or not math.isfinite(value) or value <= 0:
        return None
    return float(value)

def _read_event_csv(path: str) -> pl.DataFrame:
    """Read one telemetry CSV with numeric columns cast to Float64."""
    df = pl.read_csv(path, infer_schema_length=0)
    if "running_time" not in df.columns:
        raise ValueError("missing 'running_time' column")
    return df.with_columns(
        [
            pl.col(c).cast(pl.Float64, strict=False)
            for c in _NUMERIC_EVENT_COLUMNS
            if c in df.columns
        ]
    )

#public API
@dataclass
class StudyData:
    study_id: int
    trials: pl.DataFrame
    files: pl.DataFrame
    base_dir: str
    warnings: list[str] = field(default_factory=list) #this is where java is more preferable, surprisingly.
    def events(
        self, measurement: str, trial_ids: Optional[Iterable[int]] = None
    ) -> pl.DataFrame:
        """Raw telemetry for one measurement, all trials stacked, with trial metadata.
        Cols: the CSV columns (Time, running_time, x, y | keys) plus trial_id,
        participant_session_id, participant_id, task_id, task_name, factor_id,
        factor_name, attempt. Unreadable files are skipped and added to `warnings`.
        It is strongly recommended to make a test study and test this feature before
        using it on a real study.
        """
        if measurement not in EVENT_SCHEMAS:
            raise ValueError(
                f"measurement must be one of {', '.join(CSV_MEASUREMENTS)}"
            )
        wanted = None if trial_ids is None else set(trial_ids)
        frames = []
        for row in self.files.iter_rows(named=True):
            if row["measurement"] != measurement or not row["path"]:
                continue  # wrong type, or missing file (already warned about in load_study)
            if wanted is not None and row["trial_id"] not in wanted:
                continue
            try:
                df = _read_event_csv(row["path"])
            except Exception as exc:  # one bad file must not sink the whole analysis
                prefix = _unreadable_prefix(row["session_data_instance_id"])
                if not any(w.startswith(prefix) for w in self.warnings):
                    self.warnings.append(f"{prefix} {row['path']} ({exc})")
                continue
            frames.append(
                df.with_columns(pl.lit(row["trial_id"], dtype=pl.Int64).alias("trial_id"))
            )
        if frames:
            events = pl.concat(frames, how="diagonal")
        else:
            events = pl.DataFrame(
                schema={**EVENT_SCHEMAS[measurement], "trial_id": pl.Int64}
            )
        return events.join(
            self.trials.select(list(_EVENT_META_COLUMNS)), on="trial_id", how="left"
        )

def load_study(
    cursor,
    study_id: int,
    base_dir: Optional[str] = None,
    include_invalid: bool = False,
    prefer: str = "csv",
) -> StudyData:
    """Load trials and the file index for a study.
    
    cursor           DB cursor (e.g. get_db_connection().cursor()); tuple or dict rows.
    base_dir         results root; default $RESULTS_BASE_DIR_PATH or the Docker path.
    include_invalid  also include sessions flagged is_valid = 0.
    prefer           "csv" or "db": which duration source wins when both exist.

    TEST THIS FEATURE BEFORE USING IT!!! It may not work as expected and is UNTESTED.
    """
    base_dir = base_dir or os.environ.get("RESULTS_BASE_DIR_PATH", DEFAULT_RESULTS_BASE_DIR)
    params = (study_id, 1 if include_invalid else 0)
    trial_rows = query_rows(cursor, TRIALS_QUERY, params)
    file_rows = query_rows(cursor, FILES_QUERY, params)
    warnings: list[str] = []
    file_records: list[dict[str, Any]] = []
    csv_durations: dict[int, float] = {}  #trial_id -> largest running_time over its CSVs

    for row in file_rows:
        sdi_id = row["session_data_instance_id"]
        measurement = row["measurement"]
        path = resolve_results_path(
            row["results_path"],
            base_dir,
            study_id,
            row["participant_session_id"],
            row["trial_id"],
            sdi_id,
        )
        if measurement in CSV_MEASUREMENTS:
            if path is None:
                warnings.append(
                    f"session_data_instance {sdi_id}: file not found ({row['results_path']})"
                )
            else:
                try:
                    seconds = _csv_max_running_time(path)
                except Exception as exc:
                    warnings.append(f"{_unreadable_prefix(sdi_id)} {path} ({exc})")
                else:
                    if seconds is not None:
                        tid = row["trial_id"]
                        csv_durations[tid] = max(seconds, csv_durations.get(tid, 0.0))
        file_records.append(
            {
                "session_data_instance_id": sdi_id,
                "trial_id": row["trial_id"],
                "participant_session_id": row["participant_session_id"],
                "measurement": measurement,
                "results_path": row["results_path"],
                "path": path,
            }
        )
    trial_records: list[dict[str, Any]] = []
    for row in trial_rows:
        db_s = db_duration_seconds(row["started_at"], row["ended_at"])
        csv_s = csv_durations.get(row["trial_id"])
        duration, source = choose_duration(db_s, csv_s, prefer)
        trial_records.append(
            {
                "trial_id": row["trial_id"],
                "participant_session_id": row["participant_session_id"],
                "participant_id": row["participant_id"],
                "task_id": row["task_id"],
                "task_name": row["task_name"],
                "factor_id": row["factor_id"],
                "factor_name": row["factor_name"],
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
                "completed": row["ended_at"] is not None,
                "db_duration_s": db_s,
                "csv_duration_s": csv_s,
                "duration_s": duration,
                "duration_source": source,
            }
        )
    assign_attempts(trial_records)
    for message in warnings:
        logger.warning(message)

    return StudyData(
        study_id=study_id,
        trials=_frame(trial_records, TRIAL_SCHEMA),
        files=_frame(file_records, FILE_SCHEMA),
        base_dir=base_dir,
        warnings=warnings,
    )

def _frame(records: list[dict[str, Any]], schema: dict) -> pl.DataFrame:
    """Column-oriented construction so dtypes are explicit even for empty/None-heavy data."""
    return pl.DataFrame(
        {col: [r[col] for r in records] for col in schema}, schema=schema
    )

def group_values(
    trials: pl.DataFrame, by: str = "factor_name", value: str = "duration_s"
) -> dict[Any, list[float]]:
    """{level: [values]} for independent-groups tests (Welch t-test, one-way ANOVA).

    Rows where `value` or `by` is null are dropped. Keys keep their native type, so
    convert with str() before jsonify.
    """
    sub = trials.filter(pl.col(value).is_not_null() & pl.col(by).is_not_null())
    return {
        level: sub.filter(pl.col(by) == level)[value].to_list()
        for level in sub[by].unique(maintain_order=True).to_list()
    }

def paired_values(
    trials: pl.DataFrame,
    level_a: Any,
    level_b: Any,
    by: str = "factor_name",
    value: str = "duration_s",
) -> tuple[list[float], list[float]]:
    """Aligned (a, b) lists for a paired t-test: one pair per participant.

    A participant's repeated trials at one level are averaged. Only participants
    with data at BOTH levels are kept; output is ordered by participant_id.
    """
    sub = trials.filter(
        pl.col(by).is_in([level_a, level_b])
        & pl.col(value).is_not_null()
        & pl.col("participant_id").is_not_null()
    )
    per_participant = sub.group_by(["participant_id", by]).agg(
        pl.col(value).mean().alias("v")
    )

    def side(level: Any, name: str) -> pl.DataFrame:
        return per_participant.filter(pl.col(by) == level).select(
            "participant_id", pl.col("v").alias(name)
        )
    paired = side(level_a, "a").join(side(level_b, "b"), on="participant_id", how="inner")
    paired = paired.sort("participant_id")
    return paired["a"].to_list(), paired["b"].to_list()