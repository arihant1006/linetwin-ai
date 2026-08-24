"""Scenario registry helpers (definitions live in app.config.plant_config)."""
from __future__ import annotations

from datetime import datetime

from app.config.plant_config import SCENARIOS, SCENARIO_ORDER, ScenarioSpec
from app.simulation.failures import FailureInjector, InjectionPlan


def all_scenarios() -> list[ScenarioSpec]:
    return [SCENARIOS[k] for k in SCENARIO_ORDER]


def get_scenario(key: str) -> ScenarioSpec:
    return SCENARIOS.get(key, SCENARIOS["normal"])


def build_plan(scenario: ScenarioSpec, anchor_end: datetime, seed: int = 42
               ) -> InjectionPlan:
    return FailureInjector(seed=seed).build_plan(scenario, anchor_end)
