import json
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from sheet import TransactionSheet
from tools import MAX_ROWS, Tool, build_tools


@pytest.fixture
def mock_sheet() -> MagicMock:
    return MagicMock(spec=TransactionSheet)


@pytest.fixture
def tools(mock_sheet: MagicMock) -> dict[str, Tool]:
    return build_tools(mock_sheet, ["Food", "Transport"], ["Contanti", "Carta"])


def test_tool_schema_exposes_dynamic_enums(tools: dict[str, Tool]) -> None:
    spec = tools["append_transactions"].spec()
    tx_props = spec["function"]["parameters"]["$defs"]["TxInput"]["properties"]
    assert tx_props["category"]["enum"] == ["Food", "Transport"]
    assert tx_props["method"]["enum"] == ["Contanti", "Carta"]


def test_append_transactions_valid(tools: dict[str, Tool], mock_sheet: MagicMock) -> None:
    mock_sheet.add.return_value = 1
    payload = json.dumps(
        {
            "transactions": [
                {
                    "date": "2025-10-26",
                    "amount": -1.2,
                    "category": "Food",
                    "method": "Contanti",
                    "description": "coffee",
                }
            ]
        }
    )

    result = tools["append_transactions"].call(payload)

    assert result["inserted"] == 1
    assert result["rows"][0]["description"] == "coffee"
    mock_sheet.add.assert_called_once()


@pytest.mark.parametrize(
    "bad_field",
    [
        {"date": "26-10-2025"},
        {"date": "2025-02-30"},
        {"category": "UnknownCategory"},
        {"method": "Crypto"},
    ],
)
def test_append_transactions_validation_error(
    tools: dict[str, Tool], bad_field: dict[str, str]
) -> None:
    tx = {
        "date": "2025-10-26",
        "amount": -5.0,
        "category": "Food",
        "method": "Contanti",
        "description": "snack",
        **bad_field,
    }
    with pytest.raises(ValidationError):
        tools["append_transactions"].call(json.dumps({"transactions": [tx]}))


def test_query_transactions_truncation(tools: dict[str, Tool], mock_sheet: MagicMock) -> None:
    mock_sheet.query.return_value = [{"amount": -1.0} for _ in range(MAX_ROWS + 5)]
    payload = json.dumps({"date_from": "2025-10-01", "date_to": "2025-10-31"})

    result = tools["query_transactions"].call(payload)

    assert result["count"] == MAX_ROWS + 5
    assert result["truncated"] is True
    assert len(result["rows"]) == MAX_ROWS


def test_sum_transactions(tools: dict[str, Tool], mock_sheet: MagicMock) -> None:
    mock_sheet.query.return_value = [
        {"amount": -1.2},
        {"amount": -2.4},
        {"amount": -10.05},
    ]
    payload = json.dumps({"date_from": "2025-10-01", "date_to": "2025-10-31", "category": "Food"})

    result = tools["sum_transactions"].call(payload)

    assert result == {"total": -13.65, "count": 3}
    mock_sheet.query.assert_called_once_with("2025-10-01", "2025-10-31", "Food")
