"""Isolated SQLite persistence layer. All SQL lives here."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pandas as pd

from app.config.plant_config import DB_PATH

DDL = """
CREATE TABLE IF NOT EXISTS stations (
    station_id TEXT PRIMARY KEY, station_name TEXT, area TEXT, station_type TEXT,
    sequence INTEGER, cycle_time_target REAL, cycle_time_std REAL,
    sensor_coverage REAL, telemetry_class TEXT, criticality TEXT,
    torque_target REAL, torque_tol REAL, model_compatibility TEXT);
CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id TEXT PRIMARY KEY, model TEXT, entry_ts TEXT, exit_ts TEXT,
    current_station TEXT, quality_status TEXT, defect_flags TEXT);
CREATE TABLE IF NOT EXISTS telemetry (
    ts TEXT, station_id TEXT, vehicle_id TEXT, vehicle_model TEXT,
    cycle_time REAL, torque REAL, vibration REAL, temperature REAL,
    motor_current REAL, pressure REAL, machine_state TEXT,
    manual_checklist INTEGER, sensor_available REAL, data_quality REAL,
    wait_sec REAL, defective_here INTEGER);
CREATE INDEX IF NOT EXISTS idx_tel_station_ts ON telemetry(station_id, ts);
CREATE INDEX IF NOT EXISTS idx_tel_ts ON telemetry(ts);
CREATE INDEX IF NOT EXISTS idx_tel_vehicle ON telemetry(vehicle_id);
CREATE TABLE IF NOT EXISTS station_metrics (
    bucket_ts TEXT, station_id TEXT, throughput_vph REAL, avg_cycle_time REAL,
    ct_deviation_pct REAL, queue_length REAL, queue_pressure REAL,
    starvation_rate REAL, blocking_rate REAL, defect_rate REAL,
    sensor_coverage REAL, health_score REAL, anomaly_score REAL,
    bottleneck_score REAL, bottleneck_prob REAL, confidence REAL,
    status TEXT, causes_json TEXT, explanation_json TEXT,
    PRIMARY KEY (bucket_ts, station_id));
CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY, ts TEXT, station_id TEXT, severity TEXT,
    kind TEXT, message TEXT, confidence REAL, sensor_coverage REAL,
    causes_json TEXT, active INTEGER);
CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(ts);
CREATE TABLE IF NOT EXISTS defects (
    defect_id TEXT PRIMARY KEY, ts_origin TEXT, origin_station TEXT,
    defect_type TEXT, severity REAL, propagation_probability REAL,
    affected_stations_json TEXT, detected_station TEXT, ts_detected TEXT,
    scenario TEXT);
CREATE INDEX IF NOT EXISTS idx_defects_origin ON defects(origin_station);
CREATE TABLE IF NOT EXISTS recommendations (
    rec_id TEXT PRIMARY KEY, ts TEXT, station_id TEXT, issue TEXT,
    evidence_json TEXT, recommended_action TEXT, expected_effect TEXT,
    confidence REAL, simulation_only INTEGER);
CREATE TABLE IF NOT EXISTS simulation_runs (
    run_id TEXT PRIMARY KEY, ts TEXT, station_id TEXT, action TEXT,
    before_json TEXT, after_json TEXT, projected_improvement_pct REAL,
    note TEXT);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY, value TEXT);
"""

TEL_COLS = ["ts", "station_id", "vehicle_id", "vehicle_model", "cycle_time", "torque",
            "vibration", "temperature", "motor_current", "pressure", "machine_state",
            "manual_checklist", "sensor_available", "data_quality", "wait_sec",
            "defective_here"]
METRIC_COLS = ["bucket_ts", "station_id", "throughput_vph", "avg_cycle_time",
               "ct_deviation_pct", "queue_length", "queue_pressure", "starvation_rate",
               "blocking_rate", "defect_rate", "sensor_coverage", "health_score",
               "anomaly_score", "bottleneck_score", "bottleneck_prob", "confidence",
               "status", "causes_json", "explanation_json"]


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Additive migration: add columns that pre-existing DB files are missing."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(station_metrics)")}
    if cols and "explanation_json" not in cols:
        conn.execute("ALTER TABLE station_metrics ADD COLUMN explanation_json TEXT")
        conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)
    ensure_schema(conn)
    conn.commit()


def resolve_db_path(db_path: str | Path | None = None) -> Path:
    if db_path is not None:
        p = Path(db_path)
    else:
        env = os.environ.get("DIGITALTWIN_DB")
        p = Path(env) if env else DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get_conn(db_path: str | Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(resolve_db_path(db_path)), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)
    conn.commit()


def reset_db(db_path: str | Path | None = None) -> Path:
    p = resolve_db_path(db_path)
    for suffix in ("", "-wal", "-shm"):
        f = Path(str(p) + suffix)
        if f.exists():
            f.unlink()
    conn = get_conn(p)
    init_db(conn)
    conn.close()
    return p


def set_meta(conn: sqlite3.Connection, key: str, value) -> None:
    conn.execute(
        "INSERT INTO meta(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)))
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def insert_stations(conn: sqlite3.Connection, specs: pd.DataFrame) -> int:
    df = specs.reset_index()
    rows = [(r.station_id, r.station_name, r.area, r.station_type, int(r.sequence),
             r.cycle_time_target, r.cycle_time_std, r.sensor_coverage, r.telemetry_class,
             r.criticality, r.torque_target, r.torque_tol, r.model_compatibility)
            for r in df.itertuples()]
    conn.executemany(
        "INSERT OR REPLACE INTO stations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def insert_vehicles(conn: sqlite3.Connection, veh: pd.DataFrame) -> int:
    rows = [(r.vehicle_id, r.model, r.entry_ts, r.exit_ts, r.current_station,
             r.quality_status, r.defect_flags) for r in veh.itertuples()]
    conn.executemany("INSERT OR REPLACE INTO vehicles VALUES(?,?,?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def insert_telemetry(conn: sqlite3.Connection, tel: pd.DataFrame, chunk: int = 5000) -> int:
    if tel.empty:
        return 0
    cols = [c for c in TEL_COLS if c in tel.columns]
    rows = list(tel[cols].itertuples(index=False, name=None))
    stmt = f"INSERT OR REPLACE INTO telemetry({','.join(cols)}) VALUES({','.join('?' * len(cols))})"
    for i in range(0, len(rows), chunk):
        conn.executemany(stmt, rows[i:i + chunk])
    conn.commit()
    return len(rows)


def insert_metrics(conn: sqlite3.Connection, met: pd.DataFrame) -> int:
    if met.empty:
        return 0
    cols = [c for c in METRIC_COLS if c in met.columns]
    rows = list(met[cols].itertuples(index=False, name=None))
    placeholders = ",".join(["?"] * len(cols))
    stmt = (f"INSERT OR REPLACE INTO station_metrics({','.join(cols)}) VALUES({placeholders})")
    conn.executemany(stmt, rows)
    conn.commit()
    return len(rows)


def insert_alerts(conn: sqlite3.Connection, alerts: list[dict]) -> int:
    rows = [(a["alert_id"], a["ts"], a["station_id"], a["severity"], a["kind"],
             a["message"], a["confidence"], a["sensor_coverage"],
             json.dumps(a.get("causes", [])), int(a.get("active", 1)))
            for a in alerts]
    conn.executemany("INSERT OR REPLACE INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def insert_defects(conn: sqlite3.Connection, defects: list[dict]) -> int:
    rows = [(d["defect_id"], d["ts_origin"], d["origin_station"], d["defect_type"],
             d["severity"], d["propagation_probability"],
             json.dumps(d.get("affected_stations", [])),
             d.get("detected_station"), d.get("ts_detected"), d.get("scenario", ""))
            for d in defects]
    conn.executemany("INSERT OR REPLACE INTO defects VALUES(?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def insert_recommendations(conn: sqlite3.Connection, recs: list[dict]) -> int:
    rows = [(r["rec_id"], r["ts"], r["station_id"], r["issue"],
             json.dumps(r.get("evidence", [])), r["recommended_action"],
             r["expected_effect"], r["confidence"], int(r.get("simulation_only", 1)))
            for r in recs]
    conn.executemany("INSERT OR REPLACE INTO recommendations VALUES(?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def insert_simulation_run(conn: sqlite3.Connection, run: dict) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO simulation_runs VALUES(?,?,?,?,?,?,?,?)",
        (run["run_id"], run["ts"], run["station_id"], run["action"],
         json.dumps(run.get("before", {})), json.dumps(run.get("after", {})),
         run.get("projected_improvement_pct", 0.0), run.get("note", "")))
    conn.commit()


def load_stations(conn: sqlite3.Connection) -> pd.DataFrame:
    try:
        df = pd.read_sql_query("SELECT * FROM stations ORDER BY sequence", conn)
    except pd.errors.DatabaseError:
        return pd.DataFrame()
    if df.empty:
        return df
    return df.set_index("station_id")


def load_telemetry(conn: sqlite3.Connection, start: str | None = None,
                   end: str | None = None, station_ids: list[str] | None = None) -> pd.DataFrame:
    q = "SELECT * FROM telemetry"
    conds, params = [], []
    if start:
        conds.append("ts >= ?")
        params.append(start)
    if end:
        conds.append("ts < ?")
        params.append(end)
    if station_ids:
        conds.append(f"station_id IN ({','.join('?' * len(station_ids))})")
        params.extend(station_ids)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY ts"
    try:
        return pd.read_sql_query(q, conn, params=params)
    except pd.errors.DatabaseError:
        return pd.DataFrame()


def load_vehicles(conn: sqlite3.Connection) -> pd.DataFrame:
    try:
        return pd.read_sql_query("SELECT * FROM vehicles ORDER BY entry_ts", conn)
    except pd.errors.DatabaseError:
        return pd.DataFrame()


def load_latest_metrics(conn: sqlite3.Connection) -> pd.DataFrame:
    try:
        df = pd.read_sql_query(
            "SELECT m.* FROM station_metrics m "
            "JOIN (SELECT station_id, MAX(bucket_ts) AS b FROM station_metrics "
            "GROUP BY station_id) x ON m.station_id=x.station_id AND m.bucket_ts=x.b",
            conn)
    except pd.errors.DatabaseError:
        return pd.DataFrame()
    return df


def load_metric_history(conn: sqlite3.Connection, hours: float | None = None) -> pd.DataFrame:
    q = "SELECT * FROM station_metrics"
    params: list = []
    if hours and hours > 0:
        try:
            mx = conn.execute("SELECT MAX(bucket_ts) FROM station_metrics").fetchone()[0]
        except pd.errors.DatabaseError:
            mx = None
        if mx:
            from datetime import datetime, timedelta
            t0 = (pd.Timestamp(mx) - pd.Timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
            q += " WHERE bucket_ts >= ?"
            params.append(t0)
    try:
        return pd.read_sql_query(q, conn, params=params)
    except pd.errors.DatabaseError:
        return pd.DataFrame()


def load_alerts(conn: sqlite3.Connection, active_only: bool = True, limit: int = 100) -> pd.DataFrame:
    q = "SELECT * FROM alerts"
    if active_only:
        q += " WHERE active=1"
    q += " ORDER BY ts DESC LIMIT ?"
    try:
        return pd.read_sql_query(q, conn, params=(limit,))
    except pd.errors.DatabaseError:
        return pd.DataFrame()


def deactivate_alerts(conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE alerts SET active=0")
    conn.commit()


def load_defects(conn: sqlite3.Connection, limit: int = 200) -> pd.DataFrame:
    try:
        return pd.read_sql_query(
            "SELECT * FROM defects ORDER BY ts_origin DESC LIMIT ?", conn, params=(limit,))
    except pd.errors.DatabaseError:
        return pd.DataFrame()


def load_recommendations(conn: sqlite3.Connection, limit: int = 100) -> pd.DataFrame:
    try:
        return pd.read_sql_query(
            "SELECT * FROM recommendations ORDER BY ts DESC LIMIT ?", conn, params=(limit,))
    except pd.errors.DatabaseError:
        return pd.DataFrame()


def count_table(conn: sqlite3.Connection, table: str) -> int:
    assert table.isidentifier()
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.OperationalError:
        return 0
