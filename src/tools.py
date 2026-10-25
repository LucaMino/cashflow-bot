from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, Field, WithJsonSchema

from config import settings
from sheet import TransactionSheet

CATEGORIES = settings.category_list
PAYMENT_METHODS = settings.payment_method_list

MAX_ROWS = 50


def _check_date(v: str) -> str:
    date.fromisoformat(v)  # ValueError -> ValidationError -> sent back to the model
    return v


def _check_category(v: str) -> str:
    if v not in CATEGORIES:
        raise ValueError(f"unknown category {v!r}, must be one of {CATEGORIES}")
    return v


def _check_method(v: str) -> str:
    if v not in PAYMENT_METHODS:
        raise ValueError(f"unknown payment method {v!r}, must be one of {PAYMENT_METHODS}")
    return v


IsoDate = Annotated[str, AfterValidator(_check_date)]

# validated at runtime, exposed to the model as an enum
Category = Annotated[
    str,
    AfterValidator(_check_category),
    WithJsonSchema({"type": "string", "enum": CATEGORIES}),
]

PaymentMethod = Annotated[
    str,
    AfterValidator(_check_method),
    WithJsonSchema({"type": "string", "enum": PAYMENT_METHODS}),
]


class TxInput(BaseModel):
    date: IsoDate = Field(description="Date YYYY-MM-DD")
    amount: float = Field(
        description="Decimal number with a dot. Negative = expense, positive = income"
    )
    category: Category
    method: PaymentMethod = Field(description="Payment method")
    description: str = Field(description="Short description, e.g. 'coffee'")


class AppendArgs(BaseModel):
    transactions: list[TxInput] = Field(description="One or more transactions found in the message")


class RangeArgs(BaseModel):
    date_from: IsoDate = Field(description="Period start YYYY-MM-DD, inclusive")
    date_to: IsoDate = Field(description="Period end YYYY-MM-DD, inclusive")
    category: Category | None = None


@dataclass
class Tool:
    name: str
    description: str
    args: type[BaseModel]
    fn: Callable[[Any], Any]

    def spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args.model_json_schema(),
            },
        }

    def call(self, raw_args: str) -> Any:
        return self.fn(self.args.model_validate_json(raw_args or "{}"))


def build_tools(sheet: TransactionSheet) -> dict[str, Tool]:
    def append(a: AppendArgs) -> dict[str, Any]:
        rows = [t.model_dump() for t in a.transactions]
        print(f"Appending {len(rows)} rows to the sheet: {rows}")
        return {"inserted": sheet.add(rows), "rows": rows}

    def query(a: RangeArgs) -> dict[str, Any]:
        rows = sheet.query(a.date_from, a.date_to, a.category)
        return {
            "count": len(rows),
            "truncated": len(rows) > MAX_ROWS,
            "rows": rows[:MAX_ROWS],
        }

    def total(a: RangeArgs) -> dict[str, Any]:
        rows = sheet.query(a.date_from, a.date_to, a.category)
        return {"total": round(sum(r["amount"] for r in rows), 2), "count": len(rows)}

    tools = [
        Tool(
            "append_transactions",
            "Record new transactions in the sheet. Use it when the user reports expenses or income.",
            AppendArgs,
            append,
        ),
        Tool(
            "query_transactions",
            f"List the transactions in a period (max {MAX_ROWS}). Use it to see the details.",
            RangeArgs,
            query,
        ),
        Tool(
            "sum_transactions",
            "Sum the amounts in a period, optionally by category. "
            "ALWAYS use it for totals: never add numbers up yourself.",
            RangeArgs,
            total,
        ),
    ]
    return {t.name: t for t in tools}
