#unit tests for data_loader.py

#the following unit tests were co-developed using Claude, as per the AI USAGE DISCLOSURE in the readme
"""
Tests for app.utility.analytics.data_loader
Run from server_backend/:  pytest tests/test_data_loader.py

No database needed: a FakeCursor returns canned rows and the CSVs live in tmp_path.
Needs `polars` installed (add it to requirements.txt); the module is skipped without it.

Fixture story (study 1), two participants, factors Control / New:

  trial  who  task    factor   start     end       files
  100    p1   Search  Control  10:00:00  10:00:30  Mouse Movement (max 28.5s), Keyboard (max 12s), video
  101    p1   Search  New      10:05:00  10:05:20  one MALFORMED csv (no running_time)
  102    p2   Search  Control  11:00:00  (open)    Mouse Movement stored at a STALE db path (max 9s)
  103    p2   Search  New      11:10:00  11:10:45  Mouse Movement row whose file is MISSING
  104    p2   Browse  Control  12:00:00  (open)    none
"""
import os
from datetime import datetime

import pytest

pl = pytest.importorskip("polars")

from app.utility.analytics import data_loader as dl  # noqa: E402
# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    return str(path)

class FakeCursor:
    """Mimics the bit of a DB-API cursor that query_rows() uses."""

    def __init__(self, trials=(), files=()):
        self.trials, self.files = trials, files
        self.executed = []
        self.description = None
        self._rows = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        columns, rows = self.files if "FROM session_data_instance" in sql else self.trials
        self.description = [(c,) for c in columns]
        self._rows = list(rows)

    def fetchall(self):
        return self._rows

TRIAL_COLS = [
    "trial_id", "participant_session_id", "participant_id", "task_id", "task_name",
    "factor_id", "factor_name", "started_at", "ended_at",
]
FILE_COLS = [
    "session_data_instance_id", "trial_id", "participant_session_id",
    "measurement", "results_path",
]

def dt(hms, day=1):
    h, m, s = (int(x) for x in hms.split(":"))
    return datetime(2026, 1, day, h, m, s)

@pytest.fixture
def results_dir(tmp_path):
    return str(tmp_path / "results")

@pytest.fixture
def cursor(results_dir):
    base = results_dir
    t100 = os.path.join(base, "1_study_id", "10_participant_session_id", "100_trial_id")
    t101 = os.path.join(base, "1_study_id", "10_participant_session_id", "101_trial_id")
    t102 = os.path.join(base, "1_study_id", "11_participant_session_id", "102_trial_id")

    mm100 = write(
        os.path.join(t100, "1.csv"),
        "Time,running_time,x,y\n"
        "2026-01-01 10:00:01,1.0,10,20\n"
        "2026-01-01 10:00:10,10.0,30,40\n"
        "2026-01-01 10:00:28,28.5,50,60\n",
    )
    kb100 = write(
        os.path.join(t100, "2.csv"),
        "Time,running_time,keys\n2026-01-01 10:00:05,5.0,a\n2026-01-01 10:00:12,12.0,b\n",
    )
    video100 = os.path.join(t100, "3.mp4")  # not read, may not even exist
    bad101 = write(os.path.join(t101, "6.csv"), "foo,bar\n1,2\n")
    # trial 102's file really lives under base_dir, but the DB remembers an old location
    write(
        os.path.join(t102, "5.csv"),
        "Time,running_time,x,y\n2026-01-01 11:00:02,2.0,1,1\n2026-01-01 11:00:09,9.0,2,2\n",
    )

    trials = (
        TRIAL_COLS,
        [
            (100, 10, 1, 1, "Search", 1, "Control", dt("10:00:00"), dt("10:00:30")),
            (101, 10, 1, 1, "Search", 2, "New", dt("10:05:00"), dt("10:05:20")),
            (102, 11, 2, 1, "Search", 1, "Control", dt("11:00:00"), None),
            (103, 11, 2, 1, "Search", 2, "New", dt("11:10:00"), dt("11:10:45")),
            (104, 11, 2, 2, "Browse", 1, "Control", dt("12:00:00"), None),
        ],
    )
    files = (
        FILE_COLS,
        [
            (1, 100, 10, "Mouse Movement", mm100),
            (2, 100, 10, "Keyboard Inputs", kb100),
            (3, 100, 10, "Screen Recording", video100),
            (4, 103, 11, "Mouse Movement", "/nonexistent/4.csv"),
            (5, 102, 11, "Mouse Movement", "/old/volume/5.csv"),
            (6, 101, 10, "Mouse Movement", bad101),
        ],
    )
    return FakeCursor(trials=trials, files=files)

@pytest.fixture
def data(cursor, results_dir):
    return dl.load_study(cursor, 1, base_dir=results_dir)

def trial_rows(data):
    return {r["trial_id"]: r for r in data.trials.iter_rows(named=True)}

# --------------------------------------------------------------------------
# pure helpers
# --------------------------------------------------------------------------
class TestPureDurations:
    def test_db_duration(self):
        assert dl.db_duration_seconds(dt("10:00:00"), dt("10:00:30")) == 30.0

    @pytest.mark.parametrize(
        "start,end",
        [(dt("10:00:00"), None), (None, dt("10:00:30")), (dt("10:00:30"), dt("10:00:00")),
         (dt("10:00:00"), dt("10:00:00"))],
    )
    def test_db_duration_unusable_is_none(self, start, end):
        assert dl.db_duration_seconds(start, end) is None

    def test_choose_prefers_csv_by_default(self):
        assert dl.choose_duration(30.0, 28.5) == (28.5, "csv")

    def test_choose_can_prefer_db(self):
        assert dl.choose_duration(30.0, 28.5, prefer="db") == (30.0, "db")

    def test_choose_falls_back(self):
        assert dl.choose_duration(20.0, None) == (20.0, "db")
        assert dl.choose_duration(None, 9.0) == (9.0, "csv")
        assert dl.choose_duration(None, None) == (None, None)

    def test_choose_rejects_bad_prefer(self):
        with pytest.raises(ValueError):
            dl.choose_duration(1.0, 1.0, prefer="nope")

class TestPureAttempts:
    def test_counts_per_participant_and_task_in_start_order(self):
        recs = [  # deliberately out of order
            {"trial_id": 3, "participant_id": 1, "task_id": 1, "started_at": dt("10:20:00")},
            {"trial_id": 1, "participant_id": 1, "task_id": 1, "started_at": dt("10:00:00")},
            {"trial_id": 2, "participant_id": 1, "task_id": 2, "started_at": dt("10:10:00")},
            {"trial_id": 4, "participant_id": 2, "task_id": 1, "started_at": dt("10:30:00")},
        ]
        out = {r["trial_id"]: r["attempt"] for r in dl.assign_attempts(recs)}
        assert out == {1: 1, 3: 2, 2: 1, 4: 1}

    def test_missing_start_time_sorts_last(self):
        recs = [
            {"trial_id": 1, "participant_id": 1, "task_id": 1, "started_at": None},
            {"trial_id": 2, "participant_id": 1, "task_id": 1, "started_at": dt("10:00:00")},
        ]
        out = {r["trial_id"]: r["attempt"] for r in dl.assign_attempts(recs)}
        assert out == {2: 1, 1: 2}

class TestPureResolvePath:
    def test_uses_stored_path_when_present(self, tmp_path):
        f = write(tmp_path / "x.csv", "a\n")
        assert dl.resolve_results_path(f, str(tmp_path), 1, 2, 3, 4) == f

    def test_falls_back_to_canonical_layout(self, tmp_path):
        target = write(
            tmp_path / "1_study_id" / "2_participant_session_id" / "3_trial_id" / "4.csv", "a\n"
        )
        assert dl.resolve_results_path("/stale/4.csv", str(tmp_path), 1, 2, 3, 4) == target

    def test_null_path_assumes_id_dot_csv(self, tmp_path):
        target = write(
            tmp_path / "1_study_id" / "2_participant_session_id" / "3_trial_id" / "4.csv", "a\n"
        )
        assert dl.resolve_results_path(None, str(tmp_path), 1, 2, 3, 4) == target

    def test_missing_returns_none(self, tmp_path):
        assert dl.resolve_results_path("/stale/4.csv", str(tmp_path), 1, 2, 3, 4) is None

class TestPureQueryRows:
    def test_tuple_rows(self):
        cur = FakeCursor(trials=(["a", "b"], [(1, 2)]))
        assert dl.query_rows(cur, "SELECT trial", ()) == [{"a": 1, "b": 2}]

    def test_dict_rows(self):
        cur = FakeCursor(trials=(["a", "b"], [{"a": 1, "b": 2}]))
        assert dl.query_rows(cur, "SELECT trial", ()) == [{"a": 1, "b": 2}]

# --------------------------------------------------------------------------
# load_study -> trials
# --------------------------------------------------------------------------
class TestLoadStudyTrials:
    def test_queries_use_study_id_and_validity_flag(self, cursor, results_dir):
        dl.load_study(cursor, 1, base_dir=results_dir)
        assert [p for _, p in cursor.executed] == [(1, 0), (1, 0)]
        #was missing in the original print of the test
        cursor.executed.clear()
        dl.load_study(cursor, 1, base_dir=results_dir, include_invalid=True)
        assert [p for _, p in cursor.executed] == [(1, 1), (1, 1)]

    def test_one_row_per_trial_including_trials_without_files(self, data):
        assert sorted(trial_rows(data)) == [100, 101, 102, 103, 104]

    def test_schema(self, data):
        assert dict(data.trials.schema) == dl.TRIAL_SCHEMA

    def test_csv_duration_wins_and_uses_max_across_files(self, data):
        r = trial_rows(data)[100]  # mouse max 28.5, keyboard max 12, db 30
        assert r["csv_duration_s"] == pytest.approx(28.5)
        assert r["db_duration_s"] == pytest.approx(30.0)
        assert r["duration_s"] == pytest.approx(28.5)
        assert r["duration_source"] == "csv"

    def test_db_duration_used_when_no_usable_csv(self, data):
        rows = trial_rows(data)
        assert rows[101]["duration_s"] == pytest.approx(20.0)  # malformed csv ignored
        assert rows[101]["duration_source"] == "db"
        assert rows[103]["duration_s"] == pytest.approx(45.0)  # file missing
        assert rows[103]["duration_source"] == "db"

    def test_open_trial_can_still_have_csv_duration(self, data):
        r = trial_rows(data)[102]  # stale DB path resolved via fallback
        assert r["completed"] is False
        assert r["db_duration_s"] is None
        assert r["duration_s"] == pytest.approx(9.0)
        assert r["duration_source"] == "csv"

    def test_no_data_at_all_gives_null_duration(self, data):
        r = trial_rows(data)[104]
        assert r["duration_s"] is None and r["duration_source"] is None
        assert r["completed"] is False

    def test_prefer_db(self, cursor, results_dir):
        d = dl.load_study(cursor, 1, base_dir=results_dir, prefer="db")
        r = trial_rows(d)[100]
        assert r["duration_s"] == pytest.approx(30.0)
        assert r["duration_source"] == "db"

    def test_attempt_numbers(self, data):
        attempts = {t: r["attempt"] for t, r in trial_rows(data).items()}
        assert attempts == {100: 1, 101: 2, 102: 1, 103: 2, 104: 1}

    def test_empty_study_returns_typed_empty_frames(self):
        d = dl.load_study(FakeCursor(trials=(TRIAL_COLS, []), files=(FILE_COLS, [])), 9, base_dir="/x")
        assert d.trials.height == 0 and d.files.height == 0
        assert dict(d.trials.schema) == dl.TRIAL_SCHEMA
        assert d.warnings == []

# --------------------------------------------------------------------------
# load_study -> files + warnings
# --------------------------------------------------------------------------
class TestLoadStudyFiles:
    def test_one_row_per_file_with_resolved_path(self, data):
        rows = {r["session_data_instance_id"]: r for r in data.files.iter_rows(named=True)}
        assert sorted(rows) == [1, 2, 3, 4, 5, 6]
        assert rows[5]["results_path"] == "/old/volume/5.csv"
        assert rows[5]["path"].endswith(os.path.join("102_trial_id", "5.csv"))
        assert rows[4]["path"] is None

    def test_missing_and_malformed_csvs_are_reported_not_hidden(self, data):
        assert len(data.warnings) == 2
        assert any(w.startswith("session_data_instance 4: file not found") for w in data.warnings)
        assert any(w.startswith("session_data_instance 6: could not read") for w in data.warnings)

    def test_non_csv_measurements_never_warn(self, data):
        assert not any("session_data_instance 3" in w for w in data.warnings)

# --------------------------------------------------------------------------
# events()
# --------------------------------------------------------------------------
class TestEvents:
    def test_stacks_trials_with_metadata(self, data):
        ev = data.events(dl.MOUSE_MOVEMENT)
        assert ev["trial_id"].to_list() == [100, 100, 100, 102, 102]
        assert ev["x"].dtype == pl.Float64
        assert ev["running_time"].to_list() == [1.0, 10.0, 28.5, 2.0, 9.0]
        row = ev.filter(pl.col("trial_id") == 102).row(0, named=True)
        assert row["participant_id"] == 2
        assert row["factor_name"] == "Control"
        assert row["task_name"] == "Search"
        assert row["attempt"] == 1

    def test_trial_filter(self, data):
        ev = data.events(dl.MOUSE_MOVEMENT, trial_ids=[102])
        assert ev["trial_id"].unique().to_list() == [102]
        assert ev.height == 2

    def test_keyboard_columns(self, data):
        ev = data.events(dl.KEYBOARD_INPUTS)
        assert ev["keys"].to_list() == ["a", "b"]

    def test_measurement_with_no_files_returns_empty_typed_frame(self, data):
        ev = data.events(dl.MOUSE_CLICKS)
        assert ev.height == 0
        assert {"x", "y", "running_time", "trial_id", "factor_name"} <= set(ev.columns)

    def test_rejects_non_csv_measurement(self, data):
        with pytest.raises(ValueError):
            data.events("Screen Recording")

    def test_unreadable_file_is_skipped_without_duplicate_warning(self, data):
        before = len(data.warnings)
        data.events(dl.MOUSE_MOVEMENT)  # touches malformed file 6 again
        assert len(data.warnings) == before

# --------------------------------------------------------------------------
# helpers feeding stats_engine
# --------------------------------------------------------------------------
class TestGroupValues:
    def test_groups_by_factor_and_drops_null_durations(self, data):
        g = dl.group_values(data.trials, by="factor_name")
        assert sorted(g) == ["Control", "New"]
        assert sorted(g["Control"]) == pytest.approx([9.0, 28.5])  # trial 104 has no duration
        assert sorted(g["New"]) == pytest.approx([20.0, 45.0])

    def test_group_by_task(self, data):
        g = dl.group_values(data.trials, by="task_name")
        assert sorted(g) == ["Search"]
        assert len(g["Search"]) == 4

    def test_other_value_column(self, data):
        g = dl.group_values(data.trials, by="factor_name", value="db_duration_s")
        assert sorted(g["Control"]) == pytest.approx([30.0])

class TestPairedValues:
    def test_aligned_by_participant(self, data):
        a, b = dl.paired_values(data.trials, "Control", "New")
        # p1: Control 28.5 / New 20.0 ; p2: Control 9.0 / New 45.0
        assert a == pytest.approx([28.5, 9.0])
        assert b == pytest.approx([20.0, 45.0])

    def test_repeated_trials_are_averaged_and_unpaired_participants_dropped(self):
        trials = pl.DataFrame(
            {
                "participant_id": [1, 1, 1, 2],
                "factor_name": ["A", "A", "B", "A"],  # p2 has no B -> dropped
                "duration_s": [10.0, 20.0, 5.0, 7.0],
            }
        )
        a, b = dl.paired_values(trials, "A", "B")
        assert a == pytest.approx([15.0])
        assert b == pytest.approx([5.0])

    def test_no_overlap_returns_empty_lists(self, data):
        assert dl.paired_values(data.trials, "Control", "Nope") == ([], [])