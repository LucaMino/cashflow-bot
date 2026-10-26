import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from llm import MAX_STEPS, run
from sheet import TransactionSheet
from tools import build_tools


def _llm_response(content: str | None = None, tool_calls: list[Any] | None = None) -> Any:
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> Any:
    fn = SimpleNamespace(name=name, arguments=json.dumps(arguments))
    return SimpleNamespace(id=call_id, function=fn)


def test_run_direct_reply_without_tools() -> None:
    sheet = MagicMock(spec=TransactionSheet)
    tools = build_tools(sheet, ["Food"], ["Contanti"])

    with patch("llm.litellm.completion", return_value=_llm_response("Hello!")) as mock_comp:
        reply = run("hi", tools, "test-model", "Europe/Rome")

    assert reply == "Hello!"
    assert mock_comp.call_count == 1
    sheet.add.assert_not_called()


def test_run_self_corrects_after_validation_error() -> None:
    sheet = MagicMock(spec=TransactionSheet)
    sheet.add.return_value = 1
    tools = build_tools(sheet, ["Food"], ["Contanti"])

    # Step 1: LLM passes invalid category "InvalidCat"
    bad_call = _tool_call(
        "call_1",
        "append_transactions",
        {
            "transactions": [
                {
                    "date": "2025-10-26",
                    "amount": -1.5,
                    "category": "InvalidCat",
                    "method": "Contanti",
                    "description": "coffee",
                }
            ]
        },
    )
    # Step 2: LLM sees validation error and retries with valid category "Food"
    good_call = _tool_call(
        "call_2",
        "append_transactions",
        {
            "transactions": [
                {
                    "date": "2025-10-26",
                    "amount": -1.5,
                    "category": "Food",
                    "method": "Contanti",
                    "description": "coffee",
                }
            ]
        },
    )

    responses = [
        _llm_response(tool_calls=[bad_call]),
        _llm_response(tool_calls=[good_call]),
        _llm_response(content="✅ -1.5 Food: coffee"),
    ]

    with patch("llm.litellm.completion", side_effect=responses) as mock_comp:
        reply = run("coffee 1.50", tools, "test-model", "Europe/Rome")

    assert reply == "✅ -1.5 Food: coffee"
    assert mock_comp.call_count == 3
    sheet.add.assert_called_once()

    # Check that the first tool result sent back to the LLM contained an error
    msgs_sent = mock_comp.call_args_list[0].kwargs["messages"]
    first_tool_msg = next(m for m in msgs_sent if isinstance(m, dict) and m.get("role") == "tool")
    assert "error" in json.loads(first_tool_msg["content"])


def test_run_stops_after_max_steps() -> None:
    sheet = MagicMock(spec=TransactionSheet)
    sheet.query.return_value = []
    tools = build_tools(sheet, ["Food"], ["Contanti"])

    endless_call = _tool_call(
        "call_loop",
        "sum_transactions",
        {"date_from": "2025-10-01", "date_to": "2025-10-31"},
    )

    with patch(
        "llm.litellm.completion",
        return_value=_llm_response(tool_calls=[endless_call]),
    ) as mock_comp:
        reply = run("total?", tools, "test-model", "Europe/Rome")

    assert "Sorry, I couldn't handle your request" in reply
    assert mock_comp.call_count == MAX_STEPS
