import json
from datetime import date, timedelta
from typing import Any

import gspread

# internal keys, in the same order as the columns
KEYS = ["date", "method", "category", "description", "amount"]

FIRST_COL, LAST_COL = "B", "F"   # <-- adjust: where the table starts and ends
HEADER_ROW = 1                   # <-- adjust: header row

SHEETS_EPOCH = date(1899, 12, 30)

def _iso(v: Any) -> str:
    # with UNFORMATTED_VALUE, real dates come back as serial numbers
    if isinstance(v, (int, float)):
        return (SHEETS_EPOCH + timedelta(days=int(v))).isoformat()
    return str(v)


class TransactionSheet:
    def __init__(self, ws: gspread.Worksheet) -> None:
        self.ws = ws

    def add(self, rows: list[dict[str, Any]]) -> int:
        values = [[r.get(k, "") for k in KEYS] for r in rows]
        self.ws.append_rows(
            values,
            value_input_option="USER_ENTERED",
            table_range=f"{FIRST_COL}{HEADER_ROW}",
        )
        return len(values)

    def query(
        self, date_from: str, date_to: str, category: str | None = None
    ) -> list[dict[str, Any]]:
        raw = self.ws.get(
            f"{FIRST_COL}{HEADER_ROW}:{LAST_COL}",
            value_render_option="UNFORMATTED_VALUE",
        )
        records = []
        for r in raw[1:]:
            if not any(r):
                continue
            rec = dict(zip(KEYS, list(r) + [""] * (len(KEYS) - len(r))))
            rec["date"] = _iso(rec["date"])
            records.append(rec)
        return [
            r
            for r in records
            if date_from <= r["date"] <= date_to
            and isinstance(r["amount"], (int, float))
            and (category is None or r["category"] == category)
        ]


def open_sheet(sa_json: str, sheet_id: str, tab: str) -> TransactionSheet:
    gc = gspread.service_account_from_dict(json.loads(sa_json))
    return TransactionSheet(gc.open_by_key(sheet_id).worksheet(tab))