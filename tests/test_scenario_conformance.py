from __future__ import annotations

import pytest

from errdain.scenarios.catalog import expanded_scenario_items
from errdain.scenarios.conformance import certify_scenario


def _scenario(scenario_id: str):
    return next(item for item in expanded_scenario_items() if item.scenario_id == scenario_id)


def test_retail_timestamp_delay_satisfies_conformance_contract() -> None:
    report = certify_scenario(
        _scenario("retail_returns_return_timestamp_delay_04"),
        records=80,
        seed=805,
    )

    assert report.certified is True, report.model_dump()
    assert {check.check_id for check in report.checks} == {
        "mutation_applied",
        "ground_truth_matches_execution",
        "validator_detects_injected_truth",
        "mutation_target_is_semantically_compatible",
        "seed_replay_is_deterministic",
    }


def test_conformance_report_is_reproducible() -> None:
    scenario = _scenario("ecommerce_payment_retry")
    first = certify_scenario(scenario, records=80, seed=919)
    second = certify_scenario(scenario, records=80, seed=919)

    assert first.model_dump() == second.model_dump()


@pytest.mark.parametrize(
    "primitive",
    [
        "timestamp_delay",
        "stale_timestamp",
        "timeout_violation",
        "timestamp_out_of_order",
        "future_timestamp",
    ],
)
def test_temporal_primitive_has_a_certifiable_scenario(primitive: str) -> None:
    executable = [item for item in expanded_scenario_items() if item.execution_status == "executable"]
    scenario = next(item for item in executable if item.failure_primitive == primitive)
    report = certify_scenario(scenario, records=80, seed=2409)

    assert report.certified is True, {primitive: report.model_dump()}
