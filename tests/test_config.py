from config import Settings


def test_settings_parsed_properties() -> None:
    s = Settings(
        tg_token="token",
        tg_webhook_secret="secret",
        tg_allowed_ids="111,222,333",
        webhook_url="https://example.com",
        llm_model="gemini/gemini-2.5-flash",
        sheet_id="sheet123",
        sheet_tab="Sheet1",
        categories=" Food , Transport , , Utilities ",
        payment_methods=" Cash , Card ",
        google_sa_json="{}",
    )

    assert s.allowed_ids == {111, 222, 333}
    assert s.category_list == ["Food", "Transport", "Utilities"]
    assert s.payment_method_list == ["Cash", "Card"]
