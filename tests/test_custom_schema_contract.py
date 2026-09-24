from __future__ import annotations

import pytest
from pydantic import ValidationError

from errdain.custom_schema import CustomDatasetSchema


def _customer_order_schema() -> dict:
    return {
        "schema_id": "customer-orders",
        "name": "Customer Orders",
        "version": "1.0.0",
        "source_format": "ui",
        "tables": [
            {
                "name": "customers",
                "primary_key": "customer_id",
                "fields": [
                    {"name": "customer_id", "type": "uuid", "unique": True},
                    {"name": "email", "type": "email", "unique": True},
                ],
            },
            {
                "name": "orders",
                "primary_key": "order_id",
                "fields": [
                    {"name": "order_id", "type": "uuid", "unique": True},
                    {
                        "name": "customer_id",
                        "type": "uuid",
                        "relationship": {
                            "field": "customer_id",
                            "references_table": "customers",
                            "references_field": "customer_id",
                        },
                    },
                    {"name": "amount", "type": "number", "minimum": 0, "distribution": "normal"},
                    {"name": "ordered_at", "type": "datetime"},
                ],
            },
        ],
    }


def test_custom_schema_accepts_relational_multi_table_contract() -> None:
    schema = CustomDatasetSchema.model_validate(_customer_order_schema())

    assert schema.tables[1].fields[1].relationship.references_table == "customers"
    assert schema.compatibility_fingerprint() == CustomDatasetSchema.model_validate(
        _customer_order_schema()
    ).compatibility_fingerprint()


def test_custom_schema_rejects_missing_relationship_target() -> None:
    payload = _customer_order_schema()
    payload["tables"][1]["fields"][1]["relationship"]["references_table"] = "missing"

    with pytest.raises(ValidationError, match="relationship target table does not exist"):
        CustomDatasetSchema.model_validate(payload)


def test_custom_schema_rejects_invalid_primary_key_and_constraints() -> None:
    payload = _customer_order_schema()
    payload["tables"][1]["primary_key"] = "missing_id"
    with pytest.raises(ValidationError, match="primary_key"):
        CustomDatasetSchema.model_validate(payload)

    payload = _customer_order_schema()
    payload["tables"][1]["fields"][2]["minimum"] = 10
    payload["tables"][1]["fields"][2]["maximum"] = 1
    with pytest.raises(ValidationError, match="minimum must not exceed maximum"):
        CustomDatasetSchema.model_validate(payload)
