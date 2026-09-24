from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from errdain.scenarios.catalog.models import MasterScenarioMetadata
from errdain.scenarios.configuration import ground_truth_from_execution_result
from errdain.scenarios.generic_executor import GenericScenarioExecutionResult, execute_generic_scenario


TEMPORAL_PRIMITIVES = {
    "timestamp_delay",
    "stale_timestamp",
    "timeout_violation",
    "timestamp_out_of_order",
    "future_timestamp",
}
TEMPORAL_DIRECTIONS = {
    "timestamp_delay": "forward",
    "timeout_violation": "forward",
    "stale_timestamp": "backward",
    "timestamp_out_of_order": "backward",
}
TEMPORAL_COLUMN_MARKERS = (
    "timestamp",
    "datetime",
    "date",
    "time",
    "created",
    "updated",
    "submitted",
    "settled",
    "shipped",
    "delivered",
    "due",
)


@dataclass(frozen=True)
class ConformanceCheck:
    check_id: str
    passed: bool
    message: str
    evidence: dict[str, Any]


@dataclass(frozen=True)
class ScenarioConformanceReport:
    scenario_id: str
    seed: int
    records: int
    certified: bool
    checks: tuple[ConformanceCheck, ...]

    @property
    def failures(self) -> tuple[ConformanceCheck, ...]:
        return tuple(check for check in self.checks if not check.passed)

    def model_dump(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "records": self.records,
            "certified": self.certified,
            "checks": [
                {
                    "check_id": check.check_id,
                    "passed": check.passed,
                    "message": check.message,
                    "evidence": check.evidence,
                }
                for check in self.checks
            ],
        }


def certify_scenario(
    scenario: MasterScenarioMetadata,
    *,
    records: int = 100,
    seed: int = 42,
) -> ScenarioConformanceReport:
    """Execute a scenario twice and verify the minimum certification contract."""

    first = execute_generic_scenario(scenario, records=records, seed=seed)
    replay = execute_generic_scenario(scenario, records=records, seed=seed)
    checks = [
        _positive_mutation_check(first),
        _ground_truth_check(first),
        _validator_check(first),
        _target_check(scenario, first),
        _replay_check(first, replay),
    ]
    certified = all(check.passed for check in checks)
    return ScenarioConformanceReport(
        scenario_id=scenario.scenario_id,
        seed=seed,
        records=records,
        certified=certified,
        checks=tuple(checks),
    )


def _positive_mutation_check(result: GenericScenarioExecutionResult) -> ConformanceCheck:
    selected = int(result.primitive_result.get("selected_count", 0))
    actual = int(result.primitive_result.get("actual_mutated_count", 0))
    passed = selected > 0 and actual > 0
    return ConformanceCheck(
        "mutation_applied",
        passed,
        "The primitive selected and mutated at least one record." if passed else "The primitive reported no applied mutation.",
        {"selected_count": selected, "actual_mutated_count": actual},
    )


def _ground_truth_check(result: GenericScenarioExecutionResult) -> ConformanceCheck:
    truth = ground_truth_from_execution_result(result)
    actual = int(result.primitive_result.get("actual_mutated_count", 0))
    passed = truth.actual_mutated_count == actual and len(truth.affected_entities) == min(actual, 100)
    return ConformanceCheck(
        "ground_truth_matches_execution",
        passed,
        "Ground truth agrees with the primitive execution result." if passed else "Ground truth count or affected entities disagree with execution.",
        {
            "ground_truth_count": truth.actual_mutated_count,
            "execution_count": actual,
            "ground_truth_entities": len(truth.affected_entities),
        },
    )


def _validator_check(result: GenericScenarioExecutionResult) -> ConformanceCheck:
    validator = result.validator_result
    actual = int(result.primitive_result.get("actual_mutated_count", 0))
    detected = int(validator.get("detected_count", 0))
    passed = (
        validator.get("status") == "PASS"
        and validator.get("reconciliation_status") == "PASS"
        and detected >= actual
        and result.scenario_outcome == "PASS"
    )
    return ConformanceCheck(
        "validator_detects_injected_truth",
        passed,
        "Validator detected and reconciled the injected failures." if passed else "Validator outcome does not agree with injected truth.",
        {
            "status": validator.get("status"),
            "reconciliation_status": validator.get("reconciliation_status"),
            "actual_mutated_count": actual,
            "detected_count": detected,
            "scenario_outcome": result.scenario_outcome,
        },
    )


def _target_check(scenario: MasterScenarioMetadata, result: GenericScenarioExecutionResult) -> ConformanceCheck:
    metadata = result.primitive_result.get("mutation_metadata", {})
    table = metadata.get("table")
    column = str(metadata.get("column") or "")
    table_matches = table == scenario.primary_table
    temporal_matches = True
    sample_matches = True
    samples = metadata.get("before_after_samples", [])
    if scenario.failure_primitive in TEMPORAL_PRIMITIVES:
        temporal_matches = any(marker in column.lower() for marker in TEMPORAL_COLUMN_MARKERS)
        if scenario.failure_primitive == "future_timestamp":
            sample_matches = bool(samples) and all(_is_invalid_calendar_date_sample(sample) for sample in samples)
        else:
            expected_direction = TEMPORAL_DIRECTIONS[scenario.failure_primitive]
            sample_matches = bool(samples) and all(
                _valid_temporal_sample(sample, expected_direction) for sample in samples
            )
    passed = table_matches and temporal_matches and sample_matches
    return ConformanceCheck(
        "mutation_target_is_semantically_compatible",
        passed,
        "Mutation target matches the scenario table and primitive semantics." if passed else "Mutation target is incompatible with the scenario or primitive semantics.",
        {
            "expected_table": scenario.primary_table,
            "actual_table": table,
            "column": column,
            "before_after_sample_count": len(samples),
            "expected_temporal_behavior": "invalid_calendar_date"
            if scenario.failure_primitive == "future_timestamp"
            else TEMPORAL_DIRECTIONS.get(scenario.failure_primitive),
        },
    )


def _valid_temporal_sample(sample: dict[str, Any], expected_direction: str) -> bool:
    try:
        before = datetime.fromisoformat(str(sample["before"]))
        after = datetime.fromisoformat(str(sample["after"]))
    except (KeyError, TypeError, ValueError):
        return False
    if expected_direction == "forward":
        return after > before
    if expected_direction == "backward":
        return after < before
    return False


def _is_invalid_calendar_date_sample(sample: dict[str, Any]) -> bool:
    try:
        datetime.fromisoformat(str(sample["before"]))
    except (KeyError, TypeError, ValueError):
        return False
    try:
        datetime.fromisoformat(str(sample["after"]))
    except (KeyError, TypeError, ValueError):
        return True
    return False


def _replay_check(
    first: GenericScenarioExecutionResult,
    replay: GenericScenarioExecutionResult,
) -> ConformanceCheck:
    first_signature = _execution_signature(first)
    replay_signature = _execution_signature(replay)
    passed = first_signature == replay_signature
    return ConformanceCheck(
        "seed_replay_is_deterministic",
        passed,
        "The same seed reproduced mutation and validation evidence." if passed else "The same seed produced different evidence.",
        {"first": first_signature, "replay": replay_signature},
    )


def _execution_signature(result: GenericScenarioExecutionResult) -> dict[str, Any]:
    primitive = result.primitive_result
    validator = result.validator_result
    metadata = primitive.get("mutation_metadata", {})
    return {
        "primitive_id": primitive.get("primitive_id"),
        "selected_count": primitive.get("selected_count"),
        "actual_mutated_count": primitive.get("actual_mutated_count"),
        "affected_entity_ids": primitive.get("affected_entity_ids"),
        "table": metadata.get("table"),
        "column": metadata.get("column"),
        "before_after_samples": metadata.get("before_after_samples", []),
        "validator_id": validator.get("validation_id"),
        "detected_count": validator.get("detected_count"),
        "reconciliation_status": validator.get("reconciliation_status"),
    }
