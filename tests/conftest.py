"""Shared fixtures: tiny deterministic twin databases via $DIGITALTWIN_DB override.

Runtime budget: each seeded db is ~400 vehicles over 1.2 days (~16k visits /
~16k telemetry rows) and builds in roughly 5-10s, keeping the whole pytest run
well under two minutes.

NOTE on size: the brief suggested ~90 vehicles, but at days=1.2 that maps to
the simulator's 6 vph rate floor, which makes the failure window statistically
barren (frequently zero defect flags for chain tests) and leaves sparse
end-of-shift buckets empty. vehicles_target=400 (~20.8 vph) keeps determinism
and runtime while making scenario evidence robust. Same seed (7) throughout.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DAYS = 1.2
VEHICLES_TARGET = 400
SEED = 7


def _seed_db(db_path: Path) -> None:
    """Seed a fresh normal-history database. Env var is set BEFORE app imports."""
    os.environ["DIGITALTWIN_DB"] = str(db_path)
    from app.data.seed import seed_database  # imported after env override
    res = seed_database(days=DAYS, vehicles_target=VEHICLES_TARGET,
                        seed=SEED, scenario="normal", rate_vph=46.0)
    assert res.get("ok"), f"seed_database failed: {res}"


@pytest.fixture(scope="module")
def tiny_db(tmp_path_factory):
    """Small deterministic NORMAL dataset; returns the sqlite path (str)."""
    db_path = tmp_path_factory.mktemp("twin_normal") / "tiny_normal.db"
    _seed_db(db_path)
    return str(db_path)


@pytest.fixture(scope="module")
def tiny_db_failure(tmp_path_factory):
    """Same tiny dataset with b07_mechanical injected into the live window."""
    db_path = tmp_path_factory.mktemp("twin_failure") / "tiny_failure.db"
    _seed_db(db_path)
    os.environ["DIGITALTWIN_DB"] = str(db_path)
    from app.simulation.inject import apply_scenario  # imported after env override
    res = apply_scenario(scenario_key="b07_mechanical")
    assert res.get("ok"), f"apply_scenario failed: {res}"
    return str(db_path)


@pytest.fixture(scope="module")
def open_db():
    """Callable(path) -> new sqlite connection with $DIGITALTWIN_DB pointed there."""

    def _open(path: str):
        os.environ["DIGITALTWIN_DB"] = str(path)
        from app.data import database as db
        return db.get_conn()

    return _open


@pytest.fixture(scope="module")
def load_telemetry_for(open_db):
    """Callable(path) -> full telemetry DataFrame from that db."""

    def _load(path: str):
        conn = open_db(path)
        try:
            from app.data import database as db
            return db.load_telemetry(conn)
        finally:
            conn.close()

    return _load


@pytest.fixture(scope="module")
def station_scores(open_db, specs, plant):
    """Callable(path) -> {station_id: {'health','bprob','conf','status'}}.

    Prefers the persisted twin snapshot (db.load_latest_metrics). If that
    stored snapshot is partial (the engine scores only its final bucket, which
    can be ragged when the anchor falls near a shift boundary), falls back to
    a deterministic engine recomputation over the newest fully-populated
    bucket of stored telemetry - same inputs, same seeded pipeline.
    """

    def _scores(path: str) -> dict:
        conn = open_db(path)
        try:
            from app.data import database as db
            met = db.load_latest_metrics(conn)
            scored = met[met["health_score"].notna()] if not met.empty else met
            if len(scored) >= len(specs):
                return {r.station_id: {"health": float(r.health_score),
                                       "bprob": float(r.bottleneck_prob),
                                       "conf": float(r.confidence),
                                       "status": str(r.status)}
                        for r in scored.itertuples()}
            tel = db.load_telemetry(conn)
        finally:
            conn.close()

        from app.analytics.features import compute_features
        from app.analytics.inference import TwinInference
        feat, _ = compute_features(tel, specs, plant)
        counts = feat.groupby(level="bucket_ts").size()
        full = counts[counts >= max(1, int(0.9 * len(specs)))]
        target_ts = (full if len(full) else counts).index.max()
        trunc = feat[feat.index.get_level_values("bucket_ts") <= target_ts]
        states = TwinInference(specs, plant).update(trunc)
        return {s.station_id: {"health": float(s.health_score),
                               "bprob": float(s.bottleneck_prob),
                               "conf": float(s.confidence),
                               "status": str(s.status)}
                for s in states}

    return _scores


@pytest.fixture(scope="module")
def specs():
    from app.config.plant_config import build_station_specs
    return build_station_specs(42)


@pytest.fixture(scope="module")
def plant(specs):
    from app.simulation.plant import PlantModel
    return PlantModel(specs)
