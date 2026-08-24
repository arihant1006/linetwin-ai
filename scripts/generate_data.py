#!/usr/bin/env python
"""Generate the DigitalTwin demo database: seed -> simulate -> infer -> persist."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config.plant_config import SCENARIO_ORDER, build_station_specs  # noqa: E402
from app.data.seed import seed_database  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Generate the digital-twin SQLite database "
                    "(stations, vehicles, telemetry, twin metrics).")
    ap.add_argument("--days", type=float, default=7.0,
                    help="days of production history to simulate (default: 7)")
    ap.add_argument("--stations", type=int, default=40,
                    help="requested station count (accepted; prototype models exactly 40)")
    ap.add_argument("--vehicles", type=int, default=2400,
                    help="approximate vehicle count target across the horizon; "
                         "actual count follows the arrival rate")
    ap.add_argument("--rate", type=float, default=46.0,
                    help="arrival rate vehicles/hour during shifts "
                         "(default: 46 for realistic line congestion)")
    ap.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    ap.add_argument("--scenario", type=str, default="normal",
                    choices=list(SCENARIO_ORDER),
                    help="initial scenario baked into the history (default: normal)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.stations != 40:
        print(f"WARNING: --stations {args.stations} requested, but this prototype "
              f"models a fixed line of exactly 40 stations; proceeding with 40.")

    n_registry = len(build_station_specs(args.seed))
    if n_registry != 40:
        print(f"WARNING: station registry built {n_registry} stations (expected 40).")

    print("=" * 72)
    print("DigitalTwin.ai - database generation")
    print(f"  days={args.days}  vehicles_target={args.vehicles}  seed={args.seed}  "
          f"scenario={args.scenario}")
    print("=" * 72)

    res = seed_database(days=args.days, vehicles_target=args.vehicles,
                        seed=args.seed, scenario=args.scenario,
                        rate_vph=args.rate)

    states = res.get("states") or []
    alerts = res.get("alerts") or []
    ok = bool(res.get("ok"))

    print(f"\nStations          : {res.get('stations', 'n/a')}")
    print(f"Vehicles generated: {res.get('vehicles', 'n/a')}")
    print(f"Telemetry rows    : {res.get('telemetry_rows', 'n/a')}")
    print(f"Alerts (active)   : {len(alerts)}")
    print(f"Defect chains     : {len(res.get('defects') or [])}")
    print(f"Recommendations   : {len(res.get('recommendations') or [])}")

    if states:
        top5 = sorted(states, key=lambda s: s.bottleneck_prob, reverse=True)[:5]
        print("\nTop-5 predicted bottlenecks:")
        header = (f"  {'rank':<5}{'station':<8}{'health':>8}{'bottleneck_p':>14}"
                  f"{'confidence':>12}{'coverage':>10}")
        print(header)
        for i, s in enumerate(top5, 1):
            print(f"  {i:<5}{s.station_id:<8}{s.health_score:>8.1f}"
                  f"{s.bottleneck_prob:>14.3f}{s.confidence:>12.1f}"
                  f"{s.sensor_coverage:>10.0%}")
    else:
        print("\nTop-5 predicted bottlenecks: (no states produced)")

    print(f"\nok={ok}")
    if not ok:
        print(f"reason: {res.get('reason', 'unknown error')}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
