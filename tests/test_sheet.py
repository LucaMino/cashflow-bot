from unittest.mock import MagicMock

from gspread.utils import ValueInputOption, ValueRenderOption

from sheet import FIRST_COL, HEADER_ROW, LAST_COL, TransactionSheet, _iso


def test_iso_serial_and_string() -> None:
    # 45956 days after 1899-12-30 is 2025-10-26
    assert _iso(45956) == "2025-10-26"
    assert _iso(45956.0) == "2025-10-26"
    assert _iso("2025-10-26") == "2025-10-26"


def test_add_appends_rows_in_key_order() -> None:
    ws = MagicMock()
    sheet = TransactionSheet(ws)

    inserted = sheet.add(
        [
            {
                "date": "2025-10-26",
                "method": "Carta",
                "category": "Food",
                "description": "pizza",
                "amount": -12.5,
            }
        ]
    )

    assert inserted == 1
    ws.append_rows.assert_called_once_with(
        [["2025-10-26", "Carta", "Food", "pizza", -12.5]],
        value_input_option=ValueInputOption.user_entered,
        table_range=f"{FIRST_COL}{HEADER_ROW}",
    )


def test_query_filters_by_date_category_and_valid_amount() -> None:
    ws = MagicMock()
    ws.get.return_value = [
        ["date", "method", "category", "description", "amount"],
        [45955, "Contanti", "Food", "coffee", -1.2],  # 2025-10-25
        [45956, "Carta", "Food", "pizza", -12.5],  # 2025-10-26
        [45956, "Carta", "Transport", "bus", -2.0],  # 2025-10-26
        ["2025-10-27", "Carta", "Food", "lunch", -15.0],  # out of range
        ["", "", "", "", ""],  # empty row skipped
        [45956, "Contanti", "Food", "invalid", "N/A"],  # non-numeric amount skipped
    ]
    sheet = TransactionSheet(ws)

    all_in_range = sheet.query("2025-10-25", "2025-10-26")
    assert len(all_in_range) == 3
    ws.get.assert_called_once_with(
        f"{FIRST_COL}{HEADER_ROW}:{LAST_COL}",
        value_render_option=ValueRenderOption.unformatted,
    )

    only_food = sheet.query("2025-10-25", "2025-10-26", category="Food")
    assert len(only_food) == 2
    assert [r["description"] for r in only_food] == ["coffee", "pizza"]
