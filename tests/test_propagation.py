"""Defect propagation over the production-flow graph."""
from __future__ import annotations

from datetime import datetime

import numpy as np

from app.analytics.propagation import (build_chains_from_telemetry,
                                       propagate_defect, sankey_edges)


def test_propagation_reaches_downstream(plant):
    rec = propagate_defect(origin="B07",
                           t_origin=datetime(2026, 8, 20, 12, 0, 0),
                           defect_type="fastening",
                           severity=0.9,
                           plant=plant,
                           rng=np.random.default_rng(3))
    chain = rec["affected_stations"]

    assert len(chain) >= 2, \
        f"severity-0.9 defect must reach at least one downstream station, got {chain}"

    pos = {sid: i for i, sid in enumerate(plant.stations)}
    origin_pos = pos["B07"]
    assert chain[0] == "B07"
    assert all(pos[s] > origin_pos for s in chain[1:]), \
        f"all propagated stops must lie downstream of B07, got {chain}"

    detected = rec["detected_station"]
    assert detected is None or pos[detected] > origin_pos, \
        f"detection must happen downstream of the origin, got {detected}"


def test_chain_records_from_flagged_telemetry(tiny_db_failure, plant,
                                              load_telemetry_for):
    tel = load_telemetry_for(tiny_db_failure)
    flagged = tel[tel["defective_here"] == 1]
    assert not flagged.empty, \
        "b07_mechanical window should flag defective vehicles at B07"
    assert "B07" in set(flagged["station_id"]), \
        f"defect flags expected at B07, found origins: {sorted(set(flagged['station_id']))}"

    chains = build_chains_from_telemetry(tel, plant, seed=42)
    assert chains, "no defect chains derived from flagged telemetry"
    b07_chains = [c for c in chains if c["origin_station"] == "B07"]
    assert len(b07_chains) >= 1, \
        f"expected >=1 chain originating at B07, got origins: " \
        f"{sorted({c['origin_station'] for c in chains})}"


def test_sankey_edges(tiny_db_failure, plant, load_telemetry_for):
    tel = load_telemetry_for(tiny_db_failure)
    chains = build_chains_from_telemetry(tel, plant, seed=42)
    edges = sankey_edges(chains)
    assert len(edges) >= 1, "sankey_edges produced no edges for real chains"
    assert all(isinstance(e, tuple) and len(e) == 3 for e in edges)
    assert all(e[2] >= 1 for e in edges), f"edge counts must be >=1, got {edges}"
